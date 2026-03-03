// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IAuditCertificate
 * @notice Interface for the AuditChain NFT certificate contract.
 */
interface IAuditCertificate {
    /// @notice Data stored for each audit certificate
    struct CertificateData {
        bytes32 auditId;
        bytes32 modelHash;
        uint8 auditScore;
        uint256 timestamp;
        address auditorAddress;
        string reportIPFSHash;
        bool isRevoked;
    }

    /// @notice Emitted when a new certificate is minted
    event CertificateMinted(
        uint256 indexed tokenId,
        bytes32 indexed auditId,
        address indexed auditor,
        uint8 auditScore
    );

    /// @notice Emitted when a certificate is revoked
    event CertificateRevoked(uint256 indexed tokenId, address indexed revokedBy);

    /**
     * @notice Mint a new audit certificate NFT.
     * @param auditId   Unique identifier for the audit (bytes32)
     * @param modelHash SHA-256 hash of the audited model
     * @param auditScore Composite trust score 0-100
     * @param reportIPFSHash IPFS CID of the full PDF report
     * @return tokenId The token ID of the newly minted certificate
     */
    function mintCertificate(
        bytes32 auditId,
        bytes32 modelHash,
        uint8 auditScore,
        string calldata reportIPFSHash
    ) external returns (uint256 tokenId);

    /**
     * @notice Revoke a certificate (e.g., fraud discovered post-audit).
     * @param tokenId The token ID to revoke
     */
    function revokeCertificate(uint256 tokenId) external;

    /**
     * @notice Get all metadata for a certificate.
     * @param tokenId The token ID to query
     */
    function getCertificateData(uint256 tokenId)
        external
        view
        returns (CertificateData memory);

    /**
     * @notice Check if a certificate is active (not revoked).
     * @param tokenId The token ID to check
     */
    function isValid(uint256 tokenId) external view returns (bool);
}
