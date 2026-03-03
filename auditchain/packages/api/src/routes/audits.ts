/**
 * Audit routes: CRUD for audit requests, file upload, status tracking
 */

import { Router, Request, Response } from "express";
import multer from "multer";
import { body, param, validationResult } from "express-validator";
import { createHash } from "crypto";
import { prisma } from "../lib/prisma";
import { logger } from "../lib/logger";
import { requireRole } from "../middleware/auth";
import { auditQueue } from "../services/auditEngine";

export const auditsRouter = Router();

// Multer config: store uploaded models in /tmp/uploads
const upload = multer({
  dest: "/tmp/uploads/",
  limits: { fileSize: 100 * 1024 * 1024 }, // 100 MB max
  fileFilter: (_req, file, cb) => {
    const allowed = [".pkl", ".pickle", ".onnx", ".joblib", ".h5"];
    const ext = "." + file.originalname.split(".").pop()?.toLowerCase();
    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error(`File type ${ext} not supported`));
    }
  },
});

// ── POST /api/audits ─────────────────────────────────────────
// Submit a new audit request with optional model file upload
auditsRouter.post(
  "/",
  upload.single("modelFile"),
  [
    body("modelName").notEmpty().trim(),
    body("modelType").isIn(["sklearn", "onnx", "api", "pytorch"]),
    body("modelVersion").optional().trim(),
    body("scope").isJSON(),
  ],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    try {
      const { modelName, modelType, modelVersion, scope } = req.body;
      const parsedScope = JSON.parse(scope);

      // Compute model hash from file contents or model name + timestamp
      let modelHash: string;
      if (req.file) {
        const fs = await import("fs");
        const fileBuffer = fs.readFileSync(req.file.path);
        modelHash = createHash("sha256").update(fileBuffer).digest("hex");
      } else {
        modelHash = createHash("sha256")
          .update(`${modelName}-${Date.now()}`)
          .digest("hex");
      }

      const audit = await prisma.audit.create({
        data: {
          modelHash,
          modelName,
          modelType,
          modelVersion,
          scope: parsedScope,
          orgId: req.user!.orgId,
          submittedById: req.user!.userId,
        },
      });

      // Enqueue the audit job
      await auditQueue.add(
        "run-audit",
        {
          auditId: audit.id,
          modelPath: req.file?.path,
          modelType,
          scope: parsedScope,
        },
        {
          attempts: 3,
          backoff: { type: "exponential", delay: 2000 },
        }
      );

      logger.info(`Audit submitted: ${audit.id} by user ${req.user!.userId}`);
      res.status(201).json(audit);
    } catch (err) {
      logger.error("Submit audit error:", err);
      res.status(500).json({ error: "Failed to submit audit" });
    }
  }
);

// ── GET /api/audits ──────────────────────────────────────────
// List audits for the current user's organization
auditsRouter.get("/", async (req: Request, res: Response): Promise<void> => {
  try {
    const { status, page = "1", limit = "20" } = req.query;
    const skip = (parseInt(page as string) - 1) * parseInt(limit as string);

    const where: Record<string, unknown> = { orgId: req.user!.orgId };
    if (status) where.status = status;

    // Admins and auditors see all org audits; clients see only their own
    if (req.user!.role === "CLIENT") {
      where.submittedById = req.user!.userId;
    }

    const [audits, total] = await Promise.all([
      prisma.audit.findMany({
        where,
        include: { certificate: true },
        orderBy: { submittedAt: "desc" },
        skip,
        take: parseInt(limit as string),
      }),
      prisma.audit.count({ where }),
    ]);

    res.json({ audits, total, page: parseInt(page as string), limit: parseInt(limit as string) });
  } catch (err) {
    logger.error("List audits error:", err);
    res.status(500).json({ error: "Failed to list audits" });
  }
});

// ── GET /api/audits/:id ──────────────────────────────────────
auditsRouter.get(
  "/:id",
  [param("id").notEmpty()],
  async (req: Request, res: Response): Promise<void> => {
    try {
      const audit = await prisma.audit.findUnique({
        where: { id: req.params.id },
        include: {
          certificate: true,
          organization: { select: { name: true } },
        },
      });

      if (!audit) {
        res.status(404).json({ error: "Audit not found" });
        return;
      }

      // Clients can only see their own org's audits
      if (req.user!.role === "CLIENT" && audit.orgId !== req.user!.orgId) {
        res.status(403).json({ error: "Access denied" });
        return;
      }

      res.json(audit);
    } catch (err) {
      logger.error("Get audit error:", err);
      res.status(500).json({ error: "Failed to get audit" });
    }
  }
);

// ── DELETE /api/audits/:id ───────────────────────────────────
// Only admins can delete audits
auditsRouter.delete(
  "/:id",
  requireRole("ADMIN"),
  async (req: Request, res: Response): Promise<void> => {
    try {
      await prisma.audit.delete({ where: { id: req.params.id } });
      res.json({ message: "Audit deleted" });
    } catch (err) {
      logger.error("Delete audit error:", err);
      res.status(500).json({ error: "Failed to delete audit" });
    }
  }
);
