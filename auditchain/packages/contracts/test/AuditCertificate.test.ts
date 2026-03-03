/**
 * Hardhat tests for AuditCertificate and AuditRegistry contracts.
 * Covers: mint, verify, revoke, access control, registry queries.
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { AuditCertificate, AuditRegistry } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("AuditCertificate", () => {
  let cert: AuditCertificate;
  let registry: AuditRegistry;
  let admin: SignerWithAddress;
  let auditor: SignerWithAddress;
  let stranger: SignerWithAddress;

  const AUDITOR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("AUDITOR_ROLE"));
  const sampleAuditId = ethers.encodeBytes32String("audit-001");
  const sampleModelHash = ethers.encodeBytes32String("modelhash-abc");
  const sampleScore = 85;
  const sampleIPFS = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG";

  beforeEach(async () => {
    [admin, auditor, stranger] = await ethers.getSigners();

    const CertFactory = await ethers.getContractFactory("AuditCertificate");
    cert = await CertFactory.deploy(admin.address, auditor.address);

    const RegFactory = await ethers.getContractFactory("AuditRegistry");
    registry = await RegFactory.deploy(auditor.address);
  });

  // ── Minting ───────────────────────────────────────────────

  describe("mintCertificate", () => {
    it("should allow an auditor to mint a certificate", async () => {
      const tx = await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);

      await expect(tx)
        .to.emit(cert, "CertificateMinted")
        .withArgs(1, sampleAuditId, auditor.address, sampleScore);

      expect(await cert.totalSupply()).to.equal(1);
    });

    it("should store correct certificate data", async () => {
      await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);

      const data = await cert.getCertificateData(1);
      expect(data.auditId).to.equal(sampleAuditId);
      expect(data.modelHash).to.equal(sampleModelHash);
      expect(data.auditScore).to.equal(sampleScore);
      expect(data.auditorAddress).to.equal(auditor.address);
      expect(data.reportIPFSHash).to.equal(sampleIPFS);
      expect(data.isRevoked).to.be.false;
    });

    it("should revert if score > 100", async () => {
      await expect(
        cert.connect(auditor).mintCertificate(sampleAuditId, sampleModelHash, 101, sampleIPFS)
      ).to.be.revertedWith("AuditCertificate: score must be 0-100");
    });

    it("should revert if IPFS hash is empty", async () => {
      await expect(
        cert.connect(auditor).mintCertificate(sampleAuditId, sampleModelHash, sampleScore, "")
      ).to.be.revertedWith("AuditCertificate: IPFS hash required");
    });

    it("should revert if certificate already exists for auditId", async () => {
      await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);

      await expect(
        cert.connect(auditor).mintCertificate(sampleAuditId, sampleModelHash, 90, sampleIPFS)
      ).to.be.revertedWith("AuditCertificate: certificate already exists for this audit");
    });

    it("should revert if caller lacks AUDITOR_ROLE", async () => {
      await expect(
        cert
          .connect(stranger)
          .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS)
      ).to.be.reverted;
    });
  });

  // ── Verification ──────────────────────────────────────────

  describe("isValid", () => {
    it("should return true for a minted, non-revoked certificate", async () => {
      await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);

      expect(await cert.isValid(1)).to.be.true;
    });

    it("should return false for a non-existent token", async () => {
      expect(await cert.isValid(999)).to.be.false;
    });
  });

  // ── Revocation ────────────────────────────────────────────

  describe("revokeCertificate", () => {
    beforeEach(async () => {
      await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);
    });

    it("should allow auditor to revoke a certificate", async () => {
      await expect(cert.connect(auditor).revokeCertificate(1))
        .to.emit(cert, "CertificateRevoked")
        .withArgs(1, auditor.address);

      expect(await cert.isValid(1)).to.be.false;
      const data = await cert.getCertificateData(1);
      expect(data.isRevoked).to.be.true;
    });

    it("should revert on double revocation", async () => {
      await cert.connect(auditor).revokeCertificate(1);
      await expect(cert.connect(auditor).revokeCertificate(1)).to.be.revertedWith(
        "AuditCertificate: certificate already revoked"
      );
    });

    it("should revert if stranger tries to revoke", async () => {
      await expect(cert.connect(stranger).revokeCertificate(1)).to.be.reverted;
    });
  });

  // ── Access Control ────────────────────────────────────────

  describe("Access Control", () => {
    it("admin can grant AUDITOR_ROLE to a new address", async () => {
      await cert.connect(admin).grantRole(AUDITOR_ROLE, stranger.address);

      // Now stranger can mint
      const newAuditId = ethers.encodeBytes32String("audit-002");
      await expect(
        cert
          .connect(stranger)
          .mintCertificate(newAuditId, sampleModelHash, sampleScore, sampleIPFS)
      ).to.not.be.reverted;
    });

    it("admin can revoke AUDITOR_ROLE", async () => {
      await cert.connect(admin).revokeRole(AUDITOR_ROLE, auditor.address);

      await expect(
        cert
          .connect(auditor)
          .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS)
      ).to.be.reverted;
    });
  });

  // ── Non-transferability ───────────────────────────────────

  describe("Non-transferability", () => {
    it("should revert on transfer attempt", async () => {
      await cert
        .connect(auditor)
        .mintCertificate(sampleAuditId, sampleModelHash, sampleScore, sampleIPFS);

      await expect(
        cert
          .connect(auditor)
          .transferFrom(auditor.address, stranger.address, 1)
      ).to.be.revertedWith("AuditCertificate: certificates are non-transferable");
    });
  });
});

// ── AuditRegistry Tests ───────────────────────────────────────

describe("AuditRegistry", () => {
  let registry: AuditRegistry;
  let owner: SignerWithAddress;
  let registrar: SignerWithAddress;
  let org: SignerWithAddress;
  let stranger: SignerWithAddress;

  const modelHash = ethers.encodeBytes32String("model-hash-xyz");
  const auditId = "audit-uuid-001";

  beforeEach(async () => {
    [owner, registrar, org, stranger] = await ethers.getSigners();

    const RegFactory = await ethers.getContractFactory("AuditRegistry");
    registry = await RegFactory.deploy(registrar.address);
  });

  it("should register an audit and emit event", async () => {
    await expect(
      registry.connect(registrar).registerAudit(modelHash, org.address, auditId)
    )
      .to.emit(registry, "AuditRegistered")
      .withArgs(modelHash, org.address, auditId, expect.anything());

    expect(await registry.totalAudits()).to.equal(1);
  });

  it("should return audit history by model hash", async () => {
    await registry.connect(registrar).registerAudit(modelHash, org.address, auditId);

    const history = await registry.getAuditHistory(modelHash);
    expect(history.length).to.equal(1);
    expect(history[0].auditId).to.equal(auditId);
  });

  it("should return org audits", async () => {
    await registry.connect(registrar).registerAudit(modelHash, org.address, auditId);

    const orgAudits = await registry.getOrgAudits(org.address);
    expect(orgAudits.length).to.equal(1);
  });

  it("should revert if non-registrar tries to register", async () => {
    await expect(
      registry.connect(stranger).registerAudit(modelHash, org.address, auditId)
    ).to.be.revertedWith("AuditRegistry: caller is not an authorized registrar");
  });

  it("owner can add new registrars", async () => {
    await registry.connect(owner).addRegistrar(stranger.address);
    await expect(
      registry.connect(stranger).registerAudit(modelHash, org.address, auditId)
    ).to.not.be.reverted;
  });
});
