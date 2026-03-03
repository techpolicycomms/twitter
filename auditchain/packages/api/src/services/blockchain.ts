/**
 * Blockchain service: interacts with deployed AuditCertificate smart contract
 * using ethers.js to mint and verify NFT certificates.
 */

import { ethers } from "ethers";
import { logger } from "../lib/logger";

// ABI for the AuditCertificate contract (minimal subset needed)
const AUDIT_CERTIFICATE_ABI = [
  "function mintCertificate(bytes32 auditId, bytes32 modelHash, uint8 auditScore, string calldata reportIPFSHash) external returns (uint256)",
  "function getCertificateData(uint256 tokenId) external view returns (bytes32 auditId, bytes32 modelHash, uint8 auditScore, uint256 timestamp, address auditorAddress, string memory reportIPFSHash)",
  "function isValid(uint256 tokenId) external view returns (bool)",
  "function revokeCertificate(uint256 tokenId) external",
  "event CertificateMinted(uint256 indexed tokenId, bytes32 indexed auditId, address indexed auditor)",
];

/**
 * Get a connected ethers provider and signer.
 */
function getProviderAndSigner(): {
  provider: ethers.JsonRpcProvider;
  signer: ethers.Wallet;
} {
  const rpcUrl = process.env.BLOCKCHAIN_RPC_URL || "http://localhost:8545";
  const privateKey = process.env.AUDITOR_PRIVATE_KEY;

  if (!privateKey) {
    throw new Error("AUDITOR_PRIVATE_KEY environment variable is not set");
  }

  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const signer = new ethers.Wallet(privateKey, provider);
  return { provider, signer };
}

/**
 * Get the AuditCertificate contract instance.
 */
function getCertificateContract(signer: ethers.Wallet): ethers.Contract {
  const address = process.env.AUDIT_CERTIFICATE_ADDRESS;
  if (!address) {
    throw new Error("AUDIT_CERTIFICATE_ADDRESS environment variable is not set");
  }
  return new ethers.Contract(address, AUDIT_CERTIFICATE_ABI, signer);
}

/**
 * Mint a new NFT certificate on-chain for a completed audit.
 * @returns The token ID and transaction hash of the minted certificate.
 */
export async function mintCertificate(params: {
  auditId: string;
  modelHash: string;
  auditScore: number;
  reportIPFSHash: string;
}): Promise<{ tokenId: number; txHash: string }> {
  const { auditId, modelHash, auditScore, reportIPFSHash } = params;
  logger.info(`Minting certificate for audit: ${auditId}`);

  const { signer } = getProviderAndSigner();
  const contract = getCertificateContract(signer);

  // Convert string IDs to bytes32
  const auditIdBytes = ethers.encodeBytes32String(auditId.substring(0, 31));
  const modelHashBytes = ethers.zeroPadValue(
    ethers.hexlify(ethers.toUtf8Bytes(modelHash.substring(0, 32))),
    32
  );

  const tx = await contract.mintCertificate(
    auditIdBytes,
    modelHashBytes,
    Math.min(Math.max(auditScore, 0), 100), // Clamp to 0-100
    reportIPFSHash
  );

  logger.info(`Certificate mint tx submitted: ${tx.hash}`);
  const receipt = await tx.wait();

  // Extract tokenId from emitted event
  const mintEvent = receipt.logs
    .map((log: ethers.Log) => {
      try {
        return contract.interface.parseLog(log);
      } catch {
        return null;
      }
    })
    .find((e: ethers.LogDescription | null) => e?.name === "CertificateMinted");

  if (!mintEvent) {
    throw new Error("CertificateMinted event not found in transaction receipt");
  }

  const tokenId = Number(mintEvent.args.tokenId);
  logger.info(`Certificate minted successfully: tokenId=${tokenId}, tx=${tx.hash}`);

  return { tokenId, txHash: tx.hash };
}

/**
 * Verify a certificate on-chain by token ID.
 * Returns certificate metadata and validity status.
 */
export async function verifyCertificateOnChain(tokenId: number): Promise<{
  auditId: string;
  modelHash: string;
  auditScore: number;
  timestamp: number;
  auditorAddress: string;
  reportIPFSHash: string;
  isValid: boolean;
}> {
  const { signer } = getProviderAndSigner();
  const contract = getCertificateContract(signer);

  const [data, valid] = await Promise.all([
    contract.getCertificateData(tokenId),
    contract.isValid(tokenId),
  ]);

  return {
    auditId: ethers.decodeBytes32String(data.auditId),
    modelHash: ethers.toUtf8String(data.modelHash),
    auditScore: Number(data.auditScore),
    timestamp: Number(data.timestamp),
    auditorAddress: data.auditorAddress,
    reportIPFSHash: data.reportIPFSHash,
    isValid: valid,
  };
}
