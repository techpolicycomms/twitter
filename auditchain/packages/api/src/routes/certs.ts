/**
 * Certificate routes: issue blockchain certificates, public verification
 */

import { Router, Request, Response } from "express";
import { param, body, validationResult } from "express-validator";
import { prisma } from "../lib/prisma";
import { logger } from "../lib/logger";
import { authMiddleware, requireRole } from "../middleware/auth";
import { mintCertificate, verifyCertificateOnChain } from "../services/blockchain";

export const certsRouter = Router();

// ── POST /api/certs/mint ─────────────────────────────────────
// Auditors and admins only: mint an NFT certificate for a completed audit
certsRouter.post(
  "/mint",
  authMiddleware,
  requireRole("ADMIN", "AUDITOR"),
  [body("auditId").notEmpty(), body("ipfsHash").notEmpty()],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    const { auditId, ipfsHash } = req.body;

    try {
      const audit = await prisma.audit.findUnique({
        where: { id: auditId },
        include: { certificate: true },
      });

      if (!audit) {
        res.status(404).json({ error: "Audit not found" });
        return;
      }

      if (audit.status !== "COMPLETED") {
        res.status(400).json({ error: "Audit must be completed before issuing a certificate" });
        return;
      }

      if (audit.certificate) {
        res.status(409).json({ error: "Certificate already issued for this audit" });
        return;
      }

      if (!audit.trustScore) {
        res.status(400).json({ error: "Audit has no trust score" });
        return;
      }

      // Mint NFT on-chain
      const { tokenId, txHash } = await mintCertificate({
        auditId,
        modelHash: audit.modelHash,
        auditScore: audit.trustScore,
        reportIPFSHash: ipfsHash,
      });

      // Store certificate in DB
      const certificate = await prisma.certificate.create({
        data: {
          tokenId,
          txHash,
          ipfsHash,
          auditId,
        },
      });

      logger.info(`Certificate minted: tokenId=${tokenId} for audit=${auditId}`);
      res.status(201).json(certificate);
    } catch (err) {
      logger.error("Mint certificate error:", err);
      res.status(500).json({ error: "Failed to mint certificate" });
    }
  }
);

// ── GET /api/certs/verify/:tokenId ──────────────────────────
// PUBLIC endpoint — anyone can verify a certificate
certsRouter.get(
  "/verify/:tokenId",
  [param("tokenId").isInt()],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    const tokenId = parseInt(req.params.tokenId);

    try {
      // Check DB first
      const certificate = await prisma.certificate.findUnique({
        where: { tokenId },
        include: {
          audit: {
            include: {
              organization: { select: { name: true, industry: true } },
            },
          },
        },
      });

      if (!certificate) {
        res.status(404).json({ error: "Certificate not found" });
        return;
      }

      // Also verify on-chain for full trust
      const onChainData = await verifyCertificateOnChain(tokenId).catch((e) => {
        logger.warn(`On-chain verification failed for tokenId ${tokenId}:`, e);
        return null;
      });

      res.json({
        certificate,
        onChain: onChainData,
        isValid: !certificate.isRevoked,
      });
    } catch (err) {
      logger.error("Verify certificate error:", err);
      res.status(500).json({ error: "Failed to verify certificate" });
    }
  }
);

// ── GET /api/certs/lookup ────────────────────────────────────
// PUBLIC — search by model hash
certsRouter.get("/lookup", async (req: Request, res: Response): Promise<void> => {
  const { modelHash, certId } = req.query;

  if (!modelHash && !certId) {
    res.status(400).json({ error: "Provide modelHash or certId query parameter" });
    return;
  }

  try {
    const where: Record<string, unknown> = {};
    if (certId) where.id = certId as string;
    if (modelHash) {
      const audit = await prisma.audit.findFirst({
        where: { modelHash: modelHash as string },
        include: { certificate: true },
      });
      if (!audit?.certificate) {
        res.status(404).json({ error: "No certificate found for this model hash" });
        return;
      }
      res.json(audit.certificate);
      return;
    }

    const cert = await prisma.certificate.findFirst({
      where,
      include: {
        audit: { include: { organization: { select: { name: true } } } },
      },
    });

    if (!cert) {
      res.status(404).json({ error: "Certificate not found" });
      return;
    }

    res.json(cert);
  } catch (err) {
    logger.error("Lookup certificate error:", err);
    res.status(500).json({ error: "Failed to lookup certificate" });
  }
});

// ── POST /api/certs/revoke/:tokenId ─────────────────────────
// Admin only: revoke a certificate
certsRouter.post(
  "/revoke/:tokenId",
  authMiddleware,
  requireRole("ADMIN"),
  [param("tokenId").isInt(), body("reason").notEmpty()],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    try {
      const tokenId = parseInt(req.params.tokenId);
      const { reason } = req.body;

      const cert = await prisma.certificate.update({
        where: { tokenId },
        data: {
          isRevoked: true,
          revokedAt: new Date(),
          revokedBy: req.user!.userId,
          revokeReason: reason,
        },
      });

      logger.info(`Certificate revoked: tokenId=${tokenId} by ${req.user!.userId}`);
      res.json(cert);
    } catch (err) {
      logger.error("Revoke certificate error:", err);
      res.status(500).json({ error: "Failed to revoke certificate" });
    }
  }
);
