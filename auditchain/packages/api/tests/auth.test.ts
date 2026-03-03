/**
 * Jest tests for authentication routes.
 */

import request from "supertest";
import app from "../src/index";
import { prisma } from "../src/lib/prisma";

describe("Auth Routes", () => {
  const testEmail = `test-${Date.now()}@example.com`;
  const testPassword = "TestPass123!";

  afterAll(async () => {
    // Cleanup test user
    await prisma.user.deleteMany({ where: { email: testEmail } });
    await prisma.$disconnect();
  });

  describe("POST /api/auth/register", () => {
    it("should register a new user and return tokens", async () => {
      const res = await request(app).post("/api/auth/register").send({
        email: testEmail,
        password: testPassword,
        orgName: "Test Org",
        industry: "Technology",
        firstName: "Test",
        lastName: "User",
      });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty("accessToken");
      expect(res.body).toHaveProperty("refreshToken");
      expect(res.body.user.email).toBe(testEmail);
      expect(res.body.user.role).toBe("CLIENT");
    });

    it("should reject registration with an existing email", async () => {
      const res = await request(app).post("/api/auth/register").send({
        email: testEmail,
        password: testPassword,
        orgName: "Another Org",
        industry: "Finance",
      });
      expect(res.status).toBe(409);
    });

    it("should reject invalid email", async () => {
      const res = await request(app).post("/api/auth/register").send({
        email: "not-an-email",
        password: testPassword,
        orgName: "Test",
        industry: "Tech",
      });
      expect(res.status).toBe(400);
    });
  });

  describe("POST /api/auth/login", () => {
    it("should login with valid credentials", async () => {
      const res = await request(app).post("/api/auth/login").send({
        email: testEmail,
        password: testPassword,
      });

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty("accessToken");
      expect(res.body.user.email).toBe(testEmail);
    });

    it("should reject invalid password", async () => {
      const res = await request(app).post("/api/auth/login").send({
        email: testEmail,
        password: "WrongPassword!",
      });
      expect(res.status).toBe(401);
    });

    it("should reject non-existent user", async () => {
      const res = await request(app).post("/api/auth/login").send({
        email: "nobody@example.com",
        password: "AnyPassword!",
      });
      expect(res.status).toBe(401);
    });
  });

  describe("GET /api/auth/me", () => {
    let accessToken: string;

    beforeAll(async () => {
      const res = await request(app).post("/api/auth/login").send({
        email: testEmail,
        password: testPassword,
      });
      accessToken = res.body.accessToken;
    });

    it("should return the current user", async () => {
      const res = await request(app)
        .get("/api/auth/me")
        .set("Authorization", `Bearer ${accessToken}`);

      expect(res.status).toBe(200);
      expect(res.body.email).toBe(testEmail);
    });

    it("should reject unauthenticated request", async () => {
      const res = await request(app).get("/api/auth/me");
      expect(res.status).toBe(401);
    });
  });

  describe("GET /health", () => {
    it("should return ok status", async () => {
      const res = await request(app).get("/health");
      expect(res.status).toBe(200);
      expect(res.body.status).toBe("ok");
    });
  });
});
