/**
 * JWT authentication middleware.
 * Verifies the Bearer token on protected routes and attaches
 * the decoded user payload to req.user.
 */

import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import { logger } from "../lib/logger";

export interface JwtPayload {
  userId: string;
  email: string;
  role: "ADMIN" | "AUDITOR" | "CLIENT";
  orgId: string;
}

// Extend Express Request to include the decoded user
declare global {
  namespace Express {
    interface Request {
      user?: JwtPayload;
    }
  }
}

/**
 * Middleware that validates the JWT Bearer token.
 * Rejects with 401 if missing or invalid, 403 if expired.
 */
export function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    res.status(401).json({ error: "Missing or malformed Authorization header" });
    return;
  }

  const token = authHeader.split(" ")[1];

  try {
    const secret = process.env.JWT_SECRET;
    if (!secret) throw new Error("JWT_SECRET env variable is not set");

    const payload = jwt.verify(token, secret) as JwtPayload;
    req.user = payload;
    next();
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      res.status(403).json({ error: "Token expired" });
      return;
    }
    logger.warn("Invalid JWT token", { error: err });
    res.status(401).json({ error: "Invalid token" });
  }
}

/**
 * Role-based access control factory.
 * Usage: router.get('/admin', authMiddleware, requireRole('ADMIN'), handler)
 */
export function requireRole(...roles: Array<"ADMIN" | "AUDITOR" | "CLIENT">) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({ error: "Not authenticated" });
      return;
    }
    if (!roles.includes(req.user.role)) {
      res.status(403).json({ error: "Insufficient permissions" });
      return;
    }
    next();
  };
}
