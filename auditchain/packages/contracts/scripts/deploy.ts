/**
 * Deployment script for AuditChain smart contracts.
 * Deploys AuditCertificate and AuditRegistry to the configured network.
 *
 * Usage:
 *   npx hardhat run scripts/deploy.ts --network localhost
 *   npx hardhat run scripts/deploy.ts --network sepolia
 */

import { ethers } from "hardhat";

async function main(): Promise<void> {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);
  console.log(
    "Account balance:",
    ethers.formatEther(await ethers.provider.getBalance(deployer.address)),
    "ETH"
  );

  // ── Deploy AuditCertificate ─────────────────────────────
  console.log("\nDeploying AuditCertificate...");
  const AuditCertificateFactory = await ethers.getContractFactory("AuditCertificate");
  const auditCertificate = await AuditCertificateFactory.deploy(
    deployer.address, // admin
    deployer.address  // initial auditor
  );
  await auditCertificate.waitForDeployment();
  const certAddress = await auditCertificate.getAddress();
  console.log("AuditCertificate deployed to:", certAddress);

  // ── Deploy AuditRegistry ────────────────────────────────
  console.log("\nDeploying AuditRegistry...");
  const AuditRegistryFactory = await ethers.getContractFactory("AuditRegistry");
  const auditRegistry = await AuditRegistryFactory.deploy(deployer.address);
  await auditRegistry.waitForDeployment();
  const registryAddress = await auditRegistry.getAddress();
  console.log("AuditRegistry deployed to:", registryAddress);

  // ── Summary ─────────────────────────────────────────────
  console.log("\n=== Deployment Summary ===");
  console.log("Network:", (await ethers.provider.getNetwork()).name);
  console.log("AuditCertificate:", certAddress);
  console.log("AuditRegistry:   ", registryAddress);
  console.log("\nAdd these to your .env file:");
  console.log(`AUDIT_CERTIFICATE_ADDRESS=${certAddress}`);
  console.log(`AUDIT_REGISTRY_ADDRESS=${registryAddress}`);
  console.log(`NEXT_PUBLIC_AUDIT_CERTIFICATE_ADDRESS=${certAddress}`);
  console.log(`NEXT_PUBLIC_AUDIT_REGISTRY_ADDRESS=${registryAddress}`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("Deployment failed:", err);
    process.exit(1);
  });
