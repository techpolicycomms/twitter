/**
 * ethers.js blockchain integration for AuditChain frontend.
 * Handles wallet connection and on-chain certificate verification.
 */

import { ethers } from "ethers";

const AUDIT_CERTIFICATE_ABI = [
  "function getCertificateData(uint256 tokenId) external view returns (tuple(bytes32 auditId, bytes32 modelHash, uint8 auditScore, uint256 timestamp, address auditorAddress, string reportIPFSHash, bool isRevoked))",
  "function isValid(uint256 tokenId) external view returns (bool)",
  "function totalSupply() external view returns (uint256)",
];

export interface OnChainCertificate {
  auditId: string;
  modelHash: string;
  auditScore: number;
  timestamp: number;
  auditorAddress: string;
  reportIPFSHash: string;
  isRevoked: boolean;
  isValid: boolean;
}

/**
 * Connect to the user's MetaMask wallet and return the provider + signer.
 * Throws if MetaMask is not installed.
 */
export async function connectWallet(): Promise<{
  provider: ethers.BrowserProvider;
  signer: ethers.JsonRpcSigner;
  address: string;
}> {
  if (typeof window === "undefined" || !window.ethereum) {
    throw new Error("MetaMask is not installed. Please install MetaMask to use blockchain features.");
  }

  const provider = new ethers.BrowserProvider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  const signer = await provider.getSigner();
  const address = await signer.getAddress();

  return { provider, signer, address };
}

/**
 * Get a read-only provider for public blockchain queries (no wallet needed).
 */
function getReadProvider(): ethers.JsonRpcProvider {
  const rpcUrl =
    process.env.NEXT_PUBLIC_BLOCKCHAIN_RPC_URL || "http://localhost:8545";
  return new ethers.JsonRpcProvider(rpcUrl);
}

/**
 * Verify a certificate on-chain without requiring a wallet connection.
 * Suitable for the public /verify page.
 */
export async function verifyCertificatePublic(
  tokenId: number
): Promise<OnChainCertificate | null> {
  const contractAddress = process.env.NEXT_PUBLIC_AUDIT_CERTIFICATE_ADDRESS;
  if (!contractAddress) {
    console.warn("NEXT_PUBLIC_AUDIT_CERTIFICATE_ADDRESS is not set");
    return null;
  }

  try {
    const provider = getReadProvider();
    const contract = new ethers.Contract(
      contractAddress,
      AUDIT_CERTIFICATE_ABI,
      provider
    );

    const [data, valid] = await Promise.all([
      contract.getCertificateData(tokenId),
      contract.isValid(tokenId),
    ]);

    return {
      auditId: ethers.decodeBytes32String(data.auditId),
      modelHash: ethers.toUtf8String(data.modelHash).replace(/\0/g, ""),
      auditScore: Number(data.auditScore),
      timestamp: Number(data.timestamp),
      auditorAddress: data.auditorAddress,
      reportIPFSHash: data.reportIPFSHash,
      isRevoked: data.isRevoked,
      isValid: valid,
    };
  } catch (err) {
    console.error("On-chain verification failed:", err);
    return null;
  }
}

/**
 * Get the block explorer URL for a transaction.
 */
export function getBlockExplorerUrl(txHash: string): string {
  const baseUrl =
    process.env.NEXT_PUBLIC_BLOCK_EXPLORER_URL || "https://sepolia.etherscan.io";
  return `${baseUrl}/tx/${txHash}`;
}

/**
 * Get the IPFS gateway URL for a CID.
 */
export function getIPFSUrl(cid: string): string {
  return `https://ipfs.io/ipfs/${cid}`;
}

// Extend Window type for MetaMask
declare global {
  interface Window {
    ethereum?: ethers.Eip1193Provider;
  }
}
