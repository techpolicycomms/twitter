// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AuditRegistry
 * @notice A public on-chain registry of all AI model audits performed via AuditChain.
 *         Anyone can query the audit history for any model hash or organization.
 *         Only authorized registrars (the AuditChain platform) can write new entries.
 */
contract AuditRegistry is Ownable {
    // ── Events ───────────────────────────────────────────────

    event AuditRegistered(
        bytes32 indexed modelHash,
        address indexed orgAddress,
        string auditId,
        uint256 timestamp
    );

    event CertificateIssued(
        bytes32 indexed modelHash,
        uint256 indexed tokenId,
        uint8 auditScore,
        uint256 timestamp
    );

    event CertificateRevoked(
        uint256 indexed tokenId,
        address indexed revokedBy,
        uint256 timestamp
    );

    // ── Structs ──────────────────────────────────────────────

    struct AuditRecord {
        string auditId;          // Off-chain UUID
        bytes32 modelHash;       // SHA-256 of the model
        address orgAddress;      // Organization's wallet
        uint8 auditScore;        // 0 if pending, 0-100 when complete
        uint256 certificateTokenId; // NFT token ID (0 if not yet issued)
        bool isComplete;
        uint256 registeredAt;
        uint256 completedAt;
    }

    // ── Storage ──────────────────────────────────────────────

    /// @notice All audit records by internal index
    AuditRecord[] public audits;

    /// @notice modelHash → list of audit indices
    mapping(bytes32 => uint256[]) private _modelAudits;

    /// @notice orgAddress → list of audit indices
    mapping(address => uint256[]) private _orgAudits;

    /// @notice Authorized addresses that can register audits (platform contracts/wallets)
    mapping(address => bool) public registrars;

    // ── Modifiers ────────────────────────────────────────────

    modifier onlyRegistrar() {
        require(registrars[msg.sender], "AuditRegistry: caller is not an authorized registrar");
        _;
    }

    // ── Constructor ──────────────────────────────────────────

    constructor(address initialRegistrar) Ownable(msg.sender) {
        registrars[initialRegistrar] = true;
    }

    // ── Admin Functions ──────────────────────────────────────

    /**
     * @notice Grant registrar role to an address.
     */
    function addRegistrar(address registrar) external onlyOwner {
        registrars[registrar] = true;
    }

    /**
     * @notice Revoke registrar role from an address.
     */
    function removeRegistrar(address registrar) external onlyOwner {
        registrars[registrar] = false;
    }

    // ── Write Functions ──────────────────────────────────────

    /**
     * @notice Register a new audit in the registry.
     * @param modelHash   SHA-256 hash of the model being audited
     * @param orgAddress  The organization's wallet address
     * @param auditId     The off-chain UUID of the audit
     * @return index      The storage index of the new audit record
     */
    function registerAudit(
        bytes32 modelHash,
        address orgAddress,
        string calldata auditId
    ) external onlyRegistrar returns (uint256 index) {
        index = audits.length;

        audits.push(
            AuditRecord({
                auditId: auditId,
                modelHash: modelHash,
                orgAddress: orgAddress,
                auditScore: 0,
                certificateTokenId: 0,
                isComplete: false,
                registeredAt: block.timestamp,
                completedAt: 0
            })
        );

        _modelAudits[modelHash].push(index);
        _orgAudits[orgAddress].push(index);

        emit AuditRegistered(modelHash, orgAddress, auditId, block.timestamp);
        return index;
    }

    /**
     * @notice Record that a certificate was issued for an audit.
     * @param auditIndex      The storage index of the audit record
     * @param auditScore      The final composite trust score
     * @param certificateTokenId The NFT token ID of the issued certificate
     */
    function recordCertificate(
        uint256 auditIndex,
        uint8 auditScore,
        uint256 certificateTokenId
    ) external onlyRegistrar {
        require(auditIndex < audits.length, "AuditRegistry: invalid audit index");

        AuditRecord storage record = audits[auditIndex];
        record.auditScore = auditScore;
        record.certificateTokenId = certificateTokenId;
        record.isComplete = true;
        record.completedAt = block.timestamp;

        emit CertificateIssued(record.modelHash, certificateTokenId, auditScore, block.timestamp);
    }

    /**
     * @notice Record a certificate revocation.
     * @param tokenId The NFT token ID that was revoked
     */
    function recordRevocation(uint256 tokenId) external onlyRegistrar {
        emit CertificateRevoked(tokenId, msg.sender, block.timestamp);
    }

    // ── Query Functions ──────────────────────────────────────

    /**
     * @notice Get the full audit history for a given model hash.
     * @param modelHash SHA-256 hash of the model
     * @return records Array of audit records for this model
     */
    function getAuditHistory(bytes32 modelHash)
        external
        view
        returns (AuditRecord[] memory records)
    {
        uint256[] memory indices = _modelAudits[modelHash];
        records = new AuditRecord[](indices.length);
        for (uint256 i = 0; i < indices.length; i++) {
            records[i] = audits[indices[i]];
        }
    }

    /**
     * @notice Get all audits for a given organization.
     * @param orgAddress The organization's wallet address
     * @return records Array of audit records for this organization
     */
    function getOrgAudits(address orgAddress)
        external
        view
        returns (AuditRecord[] memory records)
    {
        uint256[] memory indices = _orgAudits[orgAddress];
        records = new AuditRecord[](indices.length);
        for (uint256 i = 0; i < indices.length; i++) {
            records[i] = audits[indices[i]];
        }
    }

    /**
     * @notice Get the total number of audits registered.
     */
    function totalAudits() external view returns (uint256) {
        return audits.length;
    }
}
