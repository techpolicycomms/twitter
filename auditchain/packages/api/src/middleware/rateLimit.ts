/**
 * Rate limiting middleware using express-rate-limit.
 * Applies a general limit to all API routes to prevent abuse.
 */

import rateLimit from "express-rate-limit";

/** General rate limiter: 100 requests per minute per IP */
export const rateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "Too many requests. Please try again later.",
  },
});

/** Stricter limiter for auth endpoints: 10 requests per 15 minutes */
export const authRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "Too many authentication attempts. Please try again in 15 minutes.",
  },
});
