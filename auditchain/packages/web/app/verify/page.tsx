"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { certsApi } from "@/lib/api";
import { verifyCertificatePublic, getBlockExplorerUrl, getIPFSUrl } from "@/lib/blockchain";
import type { Certificate } from "@/lib/types";
import { QRCodeSVG } from "qrcode.react";
import {
  Shield,
  CheckCircle,
  XCircle,
  Search,
  Award,
  ExternalLink,
  Clock,
} from "lucide-react";

/**
 * Public certificate verification page — no login required.
 * Supports search by certificate ID or model hash.
 */
function VerifyContent() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    certificate: Certificate & { audit?: { modelName?: string; trustScore?: number; organization?: { name: string } } };
    onChain: unknown;
    isValid: boolean;
  } | null>(null);

  const handleSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      // Try to parse as token ID number first
      const tokenId = parseInt(q);
      if (!isNaN(tokenId)) {
        const data = await certsApi.verify(tokenId);
        setResult(data);
      } else {
        // Try by model hash or cert ID
        const cert = await certsApi.lookup({ modelHash: q });
        if (cert.tokenId) {
          const data = await certsApi.verify(cert.tokenId);
          setResult(data);
        }
      }
    } catch {
      setError("Certificate not found. Please check the ID or model hash and try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const q = searchParams.get("q");
    if (q) handleSearch(q);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-white">
      {/* ── Header ──────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-400" />
          <span className="font-bold text-xl">AuditChain</span>
        </div>
        <span className="text-sm text-slate-400">Public Certificate Verification</span>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <Award className="h-12 w-12 text-indigo-400 mx-auto mb-4" />
          <h1 className="text-3xl font-bold mb-3">Verify AI Audit Certificate</h1>
          <p className="text-slate-400">
            Enter a certificate token ID or model hash to verify an audit certificate on the
            AuditChain blockchain registry.
          </p>
        </div>

        {/* ── Search ──────────────────────────────────── */}
        <form
          onSubmit={(e) => { e.preventDefault(); handleSearch(query); }}
          className="flex gap-3 mb-8"
        >
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Certificate token ID or model hash..."
              className="w-full bg-slate-800 border border-slate-600 rounded-xl pl-10 pr-4 py-4 text-sm placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-6 py-4 rounded-xl text-sm font-medium transition-colors"
          >
            {loading ? "Searching..." : "Verify"}
          </button>
        </form>

        {/* ── Error ───────────────────────────────────── */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex gap-3 mb-6">
            <XCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* ── Result ──────────────────────────────────── */}
        {result && (
          <div className="space-y-4">
            {/* Validity Banner */}
            <div
              className={`flex items-center gap-4 rounded-2xl p-5 ${
                result.isValid
                  ? "bg-green-500/10 border border-green-500/30"
                  : "bg-red-500/10 border border-red-500/30"
              }`}
            >
              {result.isValid ? (
                <CheckCircle className="h-8 w-8 text-green-400 flex-shrink-0" />
              ) : (
                <XCircle className="h-8 w-8 text-red-400 flex-shrink-0" />
              )}
              <div>
                <div className={`text-xl font-bold ${result.isValid ? "text-green-400" : "text-red-400"}`}>
                  {result.isValid ? "Certificate Valid" : "Certificate Revoked"}
                </div>
                <div className="text-slate-400 text-sm">
                  {result.isValid
                    ? "This certificate has been verified on the blockchain."
                    : "This certificate has been revoked and is no longer valid."}
                </div>
              </div>
            </div>

            {/* Certificate Details */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6">
              <h2 className="font-semibold mb-4">Certificate Details</h2>
              <div className="space-y-3 text-sm">
                <Detail label="Token ID" value={`#${result.certificate.tokenId}`} />
                <Detail label="Issued" value={new Date(result.certificate.issuedAt).toLocaleString()} />
                <Detail label="TX Hash" value={result.certificate.txHash} mono />
                <Detail label="IPFS Report" value={result.certificate.ipfsHash} mono />
              </div>

              <div className="flex gap-3 mt-5">
                <a
                  href={getBlockExplorerUrl(result.certificate.txHash)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm transition-colors"
                >
                  <ExternalLink className="h-4 w-4" /> View on Blockchain
                </a>
                <a
                  href={getIPFSUrl(result.certificate.ipfsHash)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm transition-colors"
                >
                  <ExternalLink className="h-4 w-4" /> View Report on IPFS
                </a>
              </div>
            </div>

            {/* QR Code */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 flex items-center gap-6">
              <QRCodeSVG
                value={typeof window !== "undefined" ? window.location.href : ""}
                size={80}
                bgColor="transparent"
                fgColor="#818cf8"
              />
              <div>
                <div className="font-medium mb-1">Share Verification URL</div>
                <p className="text-slate-400 text-sm">
                  Anyone can scan this QR code to verify this certificate independently.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── Empty State ──────────────────────────────── */}
        {!result && !loading && !error && (
          <div className="text-center text-slate-500">
            <Clock className="h-10 w-10 mx-auto mb-3 text-slate-600" />
            <p>Enter a certificate ID or model hash above to verify</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyContent />
    </Suspense>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-slate-400 flex-shrink-0">{label}</span>
      <span
        className={`text-slate-200 text-right truncate ${mono ? "font-mono text-xs" : ""}`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}
