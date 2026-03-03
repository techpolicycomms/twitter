/**
 * Database seed script — populates demo data for development.
 * Run with: npm run seed
 */

import bcrypt from "bcryptjs";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main(): Promise<void> {
  console.log("Seeding AuditChain database...");

  // ── Organizations ─────────────────────────────────────────
  const fintech = await prisma.organization.upsert({
    where: { id: "org-fintech-demo" },
    update: {},
    create: {
      id: "org-fintech-demo",
      name: "FinTech Capital AI",
      industry: "Financial Services",
    },
  });

  const healthcare = await prisma.organization.upsert({
    where: { id: "org-health-demo" },
    update: {},
    create: {
      id: "org-health-demo",
      name: "MedAI Solutions",
      industry: "Healthcare",
    },
  });

  const auditFirm = await prisma.organization.upsert({
    where: { id: "org-auditchain" },
    update: {},
    create: {
      id: "org-auditchain",
      name: "AuditChain Inc",
      industry: "AI Auditing",
    },
  });

  // ── Users ─────────────────────────────────────────────────
  const passwordHash = await bcrypt.hash("Demo1234!", 12);

  await prisma.user.upsert({
    where: { email: "admin@auditchain.io" },
    update: {},
    create: {
      email: "admin@auditchain.io",
      passwordHash,
      role: "ADMIN",
      firstName: "Alice",
      lastName: "Admin",
      orgId: auditFirm.id,
    },
  });

  await prisma.user.upsert({
    where: { email: "auditor@auditchain.io" },
    update: {},
    create: {
      email: "auditor@auditchain.io",
      passwordHash,
      role: "AUDITOR",
      firstName: "Bob",
      lastName: "Auditor",
      walletAddress: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
      orgId: auditFirm.id,
    },
  });

  await prisma.user.upsert({
    where: { email: "client@fintech.ai" },
    update: {},
    create: {
      email: "client@fintech.ai",
      passwordHash,
      role: "CLIENT",
      firstName: "Carol",
      lastName: "Client",
      orgId: fintech.id,
    },
  });

  // ── Demo Audits ───────────────────────────────────────────
  const completedAudit = await prisma.audit.upsert({
    where: { id: "audit-demo-completed" },
    update: {},
    create: {
      id: "audit-demo-completed",
      modelName: "Loan Approval Classifier v2",
      modelType: "sklearn",
      modelHash: "a1b2c3d4e5f6789012345678901234567890abcdef0123456789abcdef012345",
      scope: { fairness: true, explainability: true, robustness: true },
      status: "COMPLETED",
      trustScore: 82,
      fairnessResult: {
        score: 85,
        demographic_parity: { value: 0.92, pass: true, threshold: 0.8 },
        equalized_odds: { value: 0.88, pass: true },
        disparate_impact: { value: 0.91, pass: true, threshold: 0.8 },
        summary: "Model demonstrates fair treatment across demographic groups",
      },
      explainResult: {
        score: 78,
        top_features: [
          { name: "credit_score", importance: 0.34 },
          { name: "annual_income", importance: 0.22 },
          { name: "debt_to_income", importance: 0.18 },
          { name: "employment_years", importance: 0.14 },
          { name: "loan_amount", importance: 0.12 },
        ],
        explanation_quality: "good",
      },
      robustResult: {
        score: 80,
        adversarial_robustness: 0.79,
        missing_data_handling: "robust",
        edge_case_failures: 3,
        total_tests: 200,
        summary: "Model handles edge cases well with minor adversarial vulnerabilities",
      },
      orgId: fintech.id,
      submittedById: "placeholder",
      submittedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
      startedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000 + 5000),
      completedAt: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000),
    },
  });

  await prisma.audit.upsert({
    where: { id: "audit-demo-pending" },
    update: {},
    create: {
      id: "audit-demo-pending",
      modelName: "Patient Risk Predictor v1",
      modelType: "onnx",
      modelHash: "b2c3d4e5f67890123456789012345678901234567890abcdef0123456789abcd",
      scope: { fairness: true, explainability: true, robustness: false },
      status: "PENDING",
      orgId: healthcare.id,
      submittedById: "placeholder",
    },
  });

  // Add a certificate for the completed audit
  await prisma.certificate.upsert({
    where: { auditId: "audit-demo-completed" },
    update: {},
    create: {
      tokenId: 1,
      txHash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
      ipfsHash: "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
      auditId: "audit-demo-completed",
    },
  });

  console.log("Database seeded successfully!");
  console.log("\nDemo credentials:");
  console.log("  Admin:   admin@auditchain.io / Demo1234!");
  console.log("  Auditor: auditor@auditchain.io / Demo1234!");
  console.log("  Client:  client@fintech.ai / Demo1234!");
}

main()
  .catch((err) => {
    console.error("Seed failed:", err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
