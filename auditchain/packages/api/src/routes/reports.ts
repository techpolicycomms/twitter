/**
 * Report routes: get audit reports, download PDF, export data
 */

import { Router, Request, Response } from "express";
import { param } from "express-validator";
import { prisma } from "../lib/prisma";
import { logger } from "../lib/logger";
import { authMiddleware } from "../middleware/auth";
import { generatePdfReport } from "../services/reportGen";

export const reportsRouter = Router();

// ── GET /api/reports ─────────────────────────────────────────
// List all completed audit reports (paginated, filterable)
reportsRouter.get("/", authMiddleware, async (req: Request, res: Response): Promise<void> => {
  try {
    const { page = "1", limit = "20", search } = req.query;
    const skip = (parseInt(page as string) - 1) * parseInt(limit as string);

    const where: Record<string, unknown> = {
      status: "COMPLETED",
      orgId: req.user!.role === "CLIENT" ? req.user!.orgId : undefined,
    };

    if (search) {
      where.modelName = { contains: search as string, mode: "insensitive" };
    }

    // Remove undefined values
    Object.keys(where).forEach((k) => where[k] === undefined && delete where[k]);

    const [audits, total] = await Promise.all([
      prisma.audit.findMany({
        where,
        include: {
          certificate: true,
          organization: { select: { name: true } },
        },
        orderBy: { completedAt: "desc" },
        skip,
        take: parseInt(limit as string),
      }),
      prisma.audit.count({ where }),
    ]);

    res.json({ reports: audits, total, page: parseInt(page as string), limit: parseInt(limit as string) });
  } catch (err) {
    logger.error("List reports error:", err);
    res.status(500).json({ error: "Failed to list reports" });
  }
});

// ── GET /api/reports/:auditId ────────────────────────────────
// Get full report data for a specific audit
reportsRouter.get(
  "/:auditId",
  authMiddleware,
  [param("auditId").notEmpty()],
  async (req: Request, res: Response): Promise<void> => {
    try {
      const audit = await prisma.audit.findUnique({
        where: { id: req.params.auditId },
        include: {
          certificate: true,
          organization: { select: { name: true, industry: true } },
        },
      });

      if (!audit) {
        res.status(404).json({ error: "Report not found" });
        return;
      }

      if (req.user!.role === "CLIENT" && audit.orgId !== req.user!.orgId) {
        res.status(403).json({ error: "Access denied" });
        return;
      }

      res.json(audit);
    } catch (err) {
      logger.error("Get report error:", err);
      res.status(500).json({ error: "Failed to get report" });
    }
  }
);

// ── GET /api/reports/:auditId/pdf ────────────────────────────
// Generate and stream a PDF report for download
reportsRouter.get(
  "/:auditId/pdf",
  authMiddleware,
  async (req: Request, res: Response): Promise<void> => {
    try {
      const audit = await prisma.audit.findUnique({
        where: { id: req.params.auditId },
        include: {
          certificate: true,
          organization: { select: { name: true, industry: true } },
        },
      });

      if (!audit) {
        res.status(404).json({ error: "Audit not found" });
        return;
      }

      if (audit.status !== "COMPLETED") {
        res.status(400).json({ error: "Report not yet available — audit is not complete" });
        return;
      }

      res.setHeader("Content-Type", "application/pdf");
      res.setHeader(
        "Content-Disposition",
        `attachment; filename="auditchain-report-${audit.id}.pdf"`
      );

      const pdfStream = await generatePdfReport(audit as Parameters<typeof generatePdfReport>[0]);
      pdfStream.pipe(res);
    } catch (err) {
      logger.error("PDF generation error:", err);
      res.status(500).json({ error: "Failed to generate PDF" });
    }
  }
);

// ── GET /api/reports/:auditId/export ─────────────────────────
// Export report as JSON or CSV
reportsRouter.get(
  "/:auditId/export",
  authMiddleware,
  async (req: Request, res: Response): Promise<void> => {
    const { format = "json" } = req.query;

    try {
      const audit = await prisma.audit.findUnique({
        where: { id: req.params.auditId },
        include: { certificate: true },
      });

      if (!audit) {
        res.status(404).json({ error: "Audit not found" });
        return;
      }

      if (format === "csv") {
        // Flatten top-level audit fields for CSV
        const csvData = [
          ["field", "value"],
          ["audit_id", audit.id],
          ["model_name", audit.modelName],
          ["model_hash", audit.modelHash],
          ["status", audit.status],
          ["trust_score", String(audit.trustScore ?? "")],
          ["submitted_at", audit.submittedAt.toISOString()],
          ["completed_at", audit.completedAt?.toISOString() ?? ""],
        ]
          .map((row) => row.join(","))
          .join("\n");

        res.setHeader("Content-Type", "text/csv");
        res.setHeader(
          "Content-Disposition",
          `attachment; filename="auditchain-report-${audit.id}.csv"`
        );
        res.send(csvData);
      } else {
        res.setHeader("Content-Type", "application/json");
        res.setHeader(
          "Content-Disposition",
          `attachment; filename="auditchain-report-${audit.id}.json"`
        );
        res.json(audit);
      }
    } catch (err) {
      logger.error("Export report error:", err);
      res.status(500).json({ error: "Failed to export report" });
    }
  }
);
