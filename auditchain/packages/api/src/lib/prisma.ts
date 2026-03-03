/**
 * Prisma client singleton — reuse the same instance across the app
 * to avoid exhausting the database connection pool.
 */

import { PrismaClient } from "@prisma/client";
import { logger } from "./logger";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma =
  globalForPrisma.prisma ||
  new PrismaClient({
    log: [
      { level: "warn", emit: "event" },
      { level: "error", emit: "event" },
    ],
  });

prisma.$on("warn", (e) => logger.warn(e.message));
prisma.$on("error", (e) => logger.error(e.message));

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
