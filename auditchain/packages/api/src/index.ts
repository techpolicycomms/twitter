/**
 * AuditChain API Server
 * Entry point for the Express + Socket.io backend
 */

import express from "express";
import { createServer } from "http";
import { Server as SocketIOServer } from "socket.io";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";

import { authRouter } from "./routes/auth";
import { auditsRouter } from "./routes/audits";
import { reportsRouter } from "./routes/reports";
import { certsRouter } from "./routes/certs";
import { authMiddleware } from "./middleware/auth";
import { rateLimiter } from "./middleware/rateLimit";
import { logger } from "./lib/logger";

// ── Startup env var validation ──────────────────────────────
const REQUIRED_ENV_VARS = [
  "DATABASE_URL",
  "JWT_SECRET",
  "JWT_REFRESH_SECRET",
  "REDIS_URL",
  "AUDIT_ENGINE_URL",
];

const missingVars = REQUIRED_ENV_VARS.filter((v) => !process.env[v]);
if (missingVars.length > 0) {
  console.error(`[startup] Missing required environment variables: ${missingVars.join(", ")}`);
  process.exit(1);
}

const app = express();
const httpServer = createServer(app);

// Socket.IO for real-time audit progress updates
export const io = new SocketIOServer(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL || "http://localhost:3000",
    methods: ["GET", "POST"],
  },
});

// ── Middleware ──────────────────────────────────────────────
app.use(helmet());
app.use(
  cors({
    origin: process.env.FRONTEND_URL || "http://localhost:3000",
    credentials: true,
  })
);
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true }));
app.use(morgan("combined", { stream: { write: (msg) => logger.info(msg.trim()) } }));
app.use(rateLimiter);

// ── Health check ────────────────────────────────────────────
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// ── Routes ──────────────────────────────────────────────────
app.use("/api/auth", authRouter);
app.use("/api/audits", authMiddleware, auditsRouter);
app.use("/api/reports", reportsRouter); // some endpoints are public
app.use("/api/certs", certsRouter);     // verify endpoint is public

// ── Socket.IO ───────────────────────────────────────────────
io.on("connection", (socket) => {
  logger.info(`WebSocket client connected: ${socket.id}`);

  // Allow clients to subscribe to a specific audit's progress
  socket.on("subscribe:audit", (auditId: string) => {
    socket.join(`audit:${auditId}`);
    logger.info(`Socket ${socket.id} subscribed to audit:${auditId}`);
  });

  socket.on("disconnect", () => {
    logger.info(`WebSocket client disconnected: ${socket.id}`);
  });
});

// ── Global error handler ────────────────────────────────────
app.use(
  (
    err: Error,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction
  ) => {
    logger.error("Unhandled error:", err);
    res.status(500).json({
      error: "Internal server error",
      message: process.env.NODE_ENV === "development" ? err.message : undefined,
    });
  }
);

// ── Start server ────────────────────────────────────────────
const PORT = process.env.PORT || 3001;
httpServer.listen(PORT, () => {
  logger.info(`AuditChain API running on port ${PORT}`);
  logger.info(`Environment: ${process.env.NODE_ENV || "development"}`);
});

export default app;
