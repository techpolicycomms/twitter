/**
 * Authentication routes: register, login, refresh, logout
 */

import { Router, Request, Response } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { body, validationResult } from "express-validator";
import { prisma } from "../lib/prisma";
import { logger } from "../lib/logger";
import { authRateLimiter } from "../middleware/rateLimit";
import { authMiddleware, JwtPayload } from "../middleware/auth";

export const authRouter = Router();

const SALT_ROUNDS = 12;

/** Generate a short-lived access token */
function generateAccessToken(payload: JwtPayload): string {
  const secret = process.env.JWT_SECRET!;
  return jwt.sign(payload, secret, {
    expiresIn: process.env.JWT_EXPIRES_IN || "15m",
  });
}

/** Generate a long-lived refresh token */
function generateRefreshToken(userId: string): string {
  const secret = process.env.JWT_REFRESH_SECRET!;
  return jwt.sign({ userId }, secret, {
    expiresIn: process.env.JWT_REFRESH_EXPIRES_IN || "7d",
  });
}

// ── POST /api/auth/register ─────────────────────────────────
authRouter.post(
  "/register",
  authRateLimiter,
  [
    body("email").isEmail().normalizeEmail(),
    body("password").isLength({ min: 8 }),
    body("orgName").notEmpty().trim(),
    body("industry").notEmpty().trim(),
    body("firstName").optional().trim(),
    body("lastName").optional().trim(),
  ],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    const { email, password, orgName, industry, firstName, lastName } = req.body;

    try {
      // Check if user already exists
      const existing = await prisma.user.findUnique({ where: { email } });
      if (existing) {
        res.status(409).json({ error: "Email already registered" });
        return;
      }

      const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

      // Create org + user in a transaction
      const user = await prisma.$transaction(async (tx) => {
        const org = await tx.organization.create({
          data: { name: orgName, industry },
        });
        return tx.user.create({
          data: {
            email,
            passwordHash,
            firstName,
            lastName,
            orgId: org.id,
            role: "CLIENT",
          },
          select: {
            id: true,
            email: true,
            role: true,
            orgId: true,
            organization: { select: { name: true } },
          },
        });
      });

      logger.info(`New user registered: ${email}`);

      const payload: JwtPayload = {
        userId: user.id,
        email: user.email,
        role: user.role,
        orgId: user.orgId,
      };
      const accessToken = generateAccessToken(payload);
      const refreshToken = generateRefreshToken(user.id);

      // Store refresh token
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + 7);
      await prisma.refreshToken.create({
        data: { token: refreshToken, userId: user.id, expiresAt },
      });

      res.status(201).json({ accessToken, refreshToken, user });
    } catch (err) {
      logger.error("Register error:", err);
      res.status(500).json({ error: "Failed to register user" });
    }
  }
);

// ── POST /api/auth/login ────────────────────────────────────
authRouter.post(
  "/login",
  authRateLimiter,
  [body("email").isEmail().normalizeEmail(), body("password").notEmpty()],
  async (req: Request, res: Response): Promise<void> => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      res.status(400).json({ errors: errors.array() });
      return;
    }

    const { email, password } = req.body;

    try {
      const user = await prisma.user.findUnique({
        where: { email },
        include: { organization: { select: { name: true } } },
      });

      if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
        res.status(401).json({ error: "Invalid email or password" });
        return;
      }

      const payload: JwtPayload = {
        userId: user.id,
        email: user.email,
        role: user.role,
        orgId: user.orgId,
      };
      const accessToken = generateAccessToken(payload);
      const refreshToken = generateRefreshToken(user.id);

      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + 7);
      await prisma.refreshToken.create({
        data: { token: refreshToken, userId: user.id, expiresAt },
      });

      logger.info(`User logged in: ${email}`);
      res.json({
        accessToken,
        refreshToken,
        user: {
          id: user.id,
          email: user.email,
          role: user.role,
          orgId: user.orgId,
          organization: user.organization,
        },
      });
    } catch (err) {
      logger.error("Login error:", err);
      res.status(500).json({ error: "Failed to login" });
    }
  }
);

// ── POST /api/auth/refresh ──────────────────────────────────
authRouter.post("/refresh", async (req: Request, res: Response): Promise<void> => {
  const { refreshToken } = req.body;
  if (!refreshToken) {
    res.status(400).json({ error: "Refresh token required" });
    return;
  }

  try {
    const secret = process.env.JWT_REFRESH_SECRET!;
    const decoded = jwt.verify(refreshToken, secret) as { userId: string };

    // Validate the token exists in DB (single-use rotation)
    const storedToken = await prisma.refreshToken.findUnique({
      where: { token: refreshToken },
      include: { user: true },
    });

    if (!storedToken || storedToken.expiresAt < new Date()) {
      res.status(401).json({ error: "Invalid or expired refresh token" });
      return;
    }

    // Rotate: delete old, issue new
    await prisma.refreshToken.delete({ where: { token: refreshToken } });

    const user = storedToken.user;
    const payload: JwtPayload = {
      userId: user.id,
      email: user.email,
      role: user.role,
      orgId: user.orgId,
    };

    const newAccessToken = generateAccessToken(payload);
    const newRefreshToken = generateRefreshToken(user.id);

    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7);
    await prisma.refreshToken.create({
      data: { token: newRefreshToken, userId: user.id, expiresAt },
    });

    res.json({ accessToken: newAccessToken, refreshToken: newRefreshToken });
  } catch (err) {
    logger.warn("Token refresh failed:", err);
    res.status(401).json({ error: "Invalid refresh token" });
  }
});

// ── POST /api/auth/logout ───────────────────────────────────
authRouter.post("/logout", authMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { refreshToken } = req.body;
  if (refreshToken) {
    await prisma.refreshToken
      .delete({ where: { token: refreshToken } })
      .catch(() => {});
  }
  res.json({ message: "Logged out successfully" });
});

// ── GET /api/auth/me ────────────────────────────────────────
authRouter.get("/me", authMiddleware, async (req: Request, res: Response): Promise<void> => {
  try {
    const user = await prisma.user.findUnique({
      where: { id: req.user!.userId },
      select: {
        id: true,
        email: true,
        role: true,
        firstName: true,
        lastName: true,
        walletAddress: true,
        orgId: true,
        organization: { select: { id: true, name: true, industry: true } },
        createdAt: true,
      },
    });
    if (!user) {
      res.status(404).json({ error: "User not found" });
      return;
    }
    res.json(user);
  } catch (err) {
    logger.error("Get me error:", err);
    res.status(500).json({ error: "Failed to get user" });
  }
});
