// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "./interfaces/IAuditCertificate.sol";

/**
 * @title AuditCertificate
 * @notice ERC-721 NFT representing a tamper-proof audit certificate.
 *         Each token corresponds to a completed AI model audit with an
 *         immutable record of the audit score, model hash, and report.
 *
 *         Roles:
 *         - DEFAULT_ADMIN_ROLE: Can grant/revoke other roles
 *         - AUDITOR_ROLE: Can mint and revoke certificates
 */
contract AuditCertificate is ERC721URIStorage, AccessControl, IAuditCertificate {
    using Counters for Counters.Counter;

    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    Counters.Counter private _tokenIdCounter;

    /// @notice Maps tokenId → certificate data
    mapping(uint256 => CertificateData) private _certificates;

    /// @notice Maps auditId → tokenId (to prevent duplicate certificates)
    mapping(bytes32 => uint256) private _auditToCertificate;

    // ── Constructor ──────────────────────────────────────────

    /**
     * @param admin The address that receives DEFAULT_ADMIN_ROLE
     * @param initialAuditor The first address granted AUDITOR_ROLE
     */
    constructor(address admin, address initialAuditor) ERC721("AuditChain Certificate", "AUDIT") {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(AUDITOR_ROLE, initialAuditor);
    }

    // ── Core Functions ───────────────────────────────────────

    /**
     * @inheritdoc IAuditCertificate
     * @dev Only callable by addresses with AUDITOR_ROLE.
     *      Reverts if a certificate already exists for the given auditId.
     */
    function mintCertificate(
        bytes32 auditId,
        bytes32 modelHash,
        uint8 auditScore,
        string calldata reportIPFSHash
    ) external override onlyRole(AUDITOR_ROLE) returns (uint256 tokenId) {
        require(auditScore <= 100, "AuditCertificate: score must be 0-100");
        require(bytes(reportIPFSHash).length > 0, "AuditCertificate: IPFS hash required");
        require(
            _auditToCertificate[auditId] == 0,
            "AuditCertificate: certificate already exists for this audit"
        );

        _tokenIdCounter.increment();
        tokenId = _tokenIdCounter.current();

        _certificates[tokenId] = CertificateData({
            auditId: auditId,
            modelHash: modelHash,
            auditScore: auditScore,
            timestamp: block.timestamp,
            auditorAddress: msg.sender,
            reportIPFSHash: reportIPFSHash,
            isRevoked: false
        });

        _auditToCertificate[auditId] = tokenId;

        // Mint the NFT to the auditor (owner of the cert is the auditing org)
        _safeMint(msg.sender, tokenId);

        emit CertificateMinted(tokenId, auditId, msg.sender, auditScore);
        return tokenId;
    }

    /**
     * @inheritdoc IAuditCertificate
     * @dev Only callable by addresses with AUDITOR_ROLE.
     *      The NFT is NOT burned — revoked certs remain on-chain as evidence.
     */
    function revokeCertificate(uint256 tokenId) external override onlyRole(AUDITOR_ROLE) {
        require(_exists(tokenId), "AuditCertificate: certificate does not exist");
        require(
            !_certificates[tokenId].isRevoked,
            "AuditCertificate: certificate already revoked"
        );

        _certificates[tokenId].isRevoked = true;
        emit CertificateRevoked(tokenId, msg.sender);
    }

    /**
     * @inheritdoc IAuditCertificate
     */
    function getCertificateData(uint256 tokenId)
        external
        view
        override
        returns (CertificateData memory)
    {
        require(_exists(tokenId), "AuditCertificate: certificate does not exist");
        return _certificates[tokenId];
    }

    /**
     * @inheritdoc IAuditCertificate
     */
    function isValid(uint256 tokenId) external view override returns (bool) {
        if (!_exists(tokenId)) return false;
        return !_certificates[tokenId].isRevoked;
    }

    /**
     * @notice Get the tokenId for a given auditId.
     * @param auditId The audit bytes32 identifier
     * @return tokenId (0 if no certificate exists)
     */
    function getTokenByAuditId(bytes32 auditId) external view returns (uint256) {
        return _auditToCertificate[auditId];
    }

    /**
     * @notice Total number of certificates minted.
     */
    function totalSupply() external view returns (uint256) {
        return _tokenIdCounter.current();
    }

    // ── Required overrides ───────────────────────────────────

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721URIStorage, AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    /**
     * @dev Block token transfers after mint — certificates are non-transferable.
     *      Each certificate is permanently associated with an audit.
     */
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256, /* tokenId */
        uint256 /* batchSize */
    ) internal pure override {
        require(from == address(0) || to == address(0), "AuditCertificate: certificates are non-transferable");
    }
}
