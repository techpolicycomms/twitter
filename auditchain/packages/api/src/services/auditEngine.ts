/**
 * Audit engine orchestrator.
 * Creates a Bull queue that sends audit jobs to the Python audit engine
 * and updates the database + WebSocket clients with progress.
 */

import Bull from "bull";
import axios from "axios";
import { prisma } from "../lib/prisma";
import { logger } from "../lib/logger";
import { io } from "../index";

export interface AuditJobData {
  auditId: string;
  modelPath?: string;
  modelType: string;
  scope: {
    fairness: boolean;
    explainability: boolean;
    robustness: boolean;
  };
}

/** Bull queue backed by Redis for async audit job processing */
export const auditQueue = new Bull<AuditJobData>("audit-jobs", {
  redis: process.env.REDIS_URL || "redis://localhost:6379",
  defaultJobOptions: {
    removeOnComplete: 100,
    removeOnFail: 50,
  },
});

const AUDIT_ENGINE_URL = process.env.AUDIT_ENGINE_URL || "http://localhost:8001";

/**
 * Emit a progress event to all WebSocket clients subscribed to this audit.
 */
function emitProgress(auditId: string, progress: number, message: string): void {
  io.to(`audit:${auditId}`).emit("audit:progress", { auditId, progress, message });
}

/**
 * Process an audit job:
 * 1. Mark audit as RUNNING
 * 2. Call Python audit engine
 * 3. Store results and compute trust score
 * 4. Mark audit as COMPLETED or FAILED
 */
auditQueue.process("run-audit", async (job) => {
  const { auditId, modelPath, modelType, scope } = job.data;
  logger.info(`Processing audit job: ${auditId}`);

  try {
    // Mark as running
    await prisma.audit.update({
      where: { id: auditId },
      data: { status: "RUNNING", startedAt: new Date() },
    });
    emitProgress(auditId, 5, "Audit started");

    // Prepare request payload for Python engine
    const payload = {
      audit_id: auditId,
      model_path: modelPath,
      model_type: modelType,
      scope,
    };

    emitProgress(auditId, 15, "Sending model to audit engine...");

    // Run fairness analysis
    let fairnessResult = null;
    if (scope.fairness) {
      emitProgress(auditId, 25, "Running fairness analysis...");
      const resp = await axios.post(`${AUDIT_ENGINE_URL}/analyze/fairness`, payload, {
        timeout: 300_000, // 5 min
      });
      fairnessResult = resp.data;
      emitProgress(auditId, 45, "Fairness analysis complete");
    }

    // Run explainability analysis
    let explainResult = null;
    if (scope.explainability) {
      emitProgress(auditId, 55, "Running explainability analysis (SHAP/LIME)...");
      const resp = await axios.post(`${AUDIT_ENGINE_URL}/analyze/explainability`, payload, {
        timeout: 300_000,
      });
      explainResult = resp.data;
      emitProgress(auditId, 70, "Explainability analysis complete");
    }

    // Run robustness tests
    let robustResult = null;
    if (scope.robustness) {
      emitProgress(auditId, 78, "Running robustness tests...");
      const resp = await axios.post(`${AUDIT_ENGINE_URL}/analyze/robustness`, payload, {
        timeout: 300_000,
      });
      robustResult = resp.data;
      emitProgress(auditId, 90, "Robustness testing complete");
    }

    // Compute composite trust score
    emitProgress(auditId, 95, "Computing trust score...");
    const trustScore = computeTrustScore({ fairnessResult, explainResult, robustResult });

    // Save results
    await prisma.audit.update({
      where: { id: auditId },
      data: {
        status: "COMPLETED",
        fairnessResult: fairnessResult ?? undefined,
        explainResult: explainResult ?? undefined,
        robustResult: robustResult ?? undefined,
        trustScore,
        completedAt: new Date(),
      },
    });

    emitProgress(auditId, 100, "Audit complete!");
    io.to(`audit:${auditId}`).emit("audit:completed", { auditId, trustScore });
    logger.info(`Audit completed: ${auditId}, score: ${trustScore}`);
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    logger.error(`Audit failed: ${auditId}`, err);

    await prisma.audit.update({
      where: { id: auditId },
      data: { status: "FAILED", errorMessage },
    });

    io.to(`audit:${auditId}`).emit("audit:failed", { auditId, error: errorMessage });
    throw err; // Let Bull handle the retry
  }
});

/**
 * Computes a weighted composite trust score (0-100).
 * Weights: fairness 35%, explainability 25%, robustness 25%, docs 15%
 */
function computeTrustScore(results: {
  fairnessResult: { score?: number } | null;
  explainResult: { score?: number } | null;
  robustResult: { score?: number } | null;
}): number {
  const { fairnessResult, explainResult, robustResult } = results;

  const fairnessScore = fairnessResult?.score ?? 70;
  const explainScore = explainResult?.score ?? 70;
  const robustScore = robustResult?.score ?? 70;
  const docsScore = 70; // Default doc score; extend with real doc analysis

  return Math.round(
    fairnessScore * 0.35 +
    explainScore * 0.25 +
    robustScore * 0.25 +
    docsScore * 0.15
  );
}

// Log queue events
auditQueue.on("failed", (job, err) => {
  logger.error(`Job ${job.id} failed after ${job.attemptsMade} attempts:`, err);
});

auditQueue.on("completed", (job) => {
  logger.info(`Job ${job.id} completed successfully`);
});
