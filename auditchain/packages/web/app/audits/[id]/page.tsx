"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { auditsApi, certsApi } from "@/lib/api";
import type { Audit } from "@/lib/types";
import { io } from "socket.io-client";
import {
  Shield,
  CheckCircle,
  XCircle,
  Clock,
  Award,
  Download,
  BarChart2,
  AlertTriangle,
  Zap,
} from "lucide-react";
import { getBlockExplorerUrl } from "@/lib/blockchain";

/**
 * Audit detail page with:
 * - Real-time progress tracker via WebSocket
 * - Results tabs: Fairness | Explainability | Robustness | Overall
 * - "Issue Certificate" button
 * - PDF download
 */
export default function AuditDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"fairness" | "explainability" | "robustness" | "overall">("overall");
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [minting, setMinting] = useState(false);

  useEffect(() => {
    if (!id) return;

    auditsApi.get(id).then((data) => {
      setAudit(data);
      setLoading(false);
      if (data.status === "COMPLETED") setProgress(100);
    });

    // Subscribe to real-time progress via WebSocket
    const ws_url = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:3001";
    const socket = io(ws_url);
    socket.emit("subscribe:audit", id);

    socket.on("audit:progress", ({ progress: p, message }: { progress: number; message: string }) => {
      setProgress(p);
      setProgressMsg(message);
    });

    socket.on("audit:completed", () => {
      auditsApi.get(id).then(setAudit);
      setProgress(100);
    });

    socket.on("audit:failed", ({ error }: { error: string }) => {
      setProgressMsg(`Failed: ${error}`);
      auditsApi.get(id).then(setAudit);
    });

    return () => { socket.disconnect(); };
  }, [id]);

  const handleMintCert = async () => {
    if (!audit || minting) return;
    setMinting(true);
    try {
      const cert = await certsApi.mint(audit.id, "QmPlaceholderIPFSHash");
      setAudit((prev) => prev ? { ...prev, certificate: cert } : prev);
    } catch (err) {
      console.error("Mint failed:", err);
    } finally {
      setMinting(false);
    }
  };

  if (loading) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">Loading audit...</div>;
  if (!audit) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-red-500">Audit not found</div>;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center gap-4">
          <Shield className="h-6 w-6 text-indigo-600" />
          <div>
            <h1 className="font-bold text-lg">{audit.modelName}</h1>
            <p className="text-xs text-slate-500">{audit.id}</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {audit.status === "COMPLETED" && !audit.certificate && (
              <button
                onClick={handleMintCert}
                disabled={minting}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                <Award className="h-4 w-4" />
                {minting ? "Minting..." : "Issue Certificate"}
              </button>
            )}
            {audit.status === "COMPLETED" && (
              <a
                href={`/api/reports/${audit.id}/pdf`}
                className="flex items-center gap-2 border border-slate-300 hover:bg-slate-50 px-4 py-2 rounded-lg text-sm"
              >
                <Download className="h-4 w-4" />
                Download PDF
              </a>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* ── Status + Progress ───────────────────────────── */}
        {(audit.status === "RUNNING" || audit.status === "PENDING") && (
          <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <Clock className="h-5 w-5 text-yellow-500 animate-pulse" />
              <span className="font-medium">Audit in Progress</span>
              <span className="ml-auto text-sm text-slate-500">{progress}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 mb-2">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            {progressMsg && <p className="text-sm text-slate-600">{progressMsg}</p>}
          </div>
        )}

        {/* ── Certificate Banner ─────────────────────────── */}
        {audit.certificate && (
          <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl p-5 mb-6 flex items-center gap-4">
            <Award className="h-8 w-8 flex-shrink-0" />
            <div className="flex-1">
              <div className="font-semibold">Blockchain Certificate Issued</div>
              <div className="text-indigo-200 text-sm">Token #{audit.certificate.tokenId}</div>
            </div>
            <a
              href={getBlockExplorerUrl(audit.certificate.txHash)}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              View on Chain
            </a>
          </div>
        )}

        {/* ── Trust Score Card ────────────────────────────── */}
        {audit.trustScore !== null && audit.trustScore !== undefined && (
          <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6 flex items-center gap-6">
            <div className="text-center">
              <div
                className={`text-5xl font-bold ${
                  audit.trustScore >= 80 ? "text-green-600" : audit.trustScore >= 60 ? "text-yellow-600" : "text-red-600"
                }`}
              >
                {audit.trustScore}
              </div>
              <div className="text-slate-500 text-sm">Trust Score</div>
            </div>
            <div className="flex-1">
              <div className="text-sm text-slate-500 mb-1">Overall Assessment</div>
              <div className="font-medium">
                {audit.trustScore >= 80 ? "Excellent — Model meets ethical AI standards" :
                 audit.trustScore >= 60 ? "Good — Minor issues found, remediation suggested" :
                 "Needs Improvement — Significant concerns identified"}
              </div>
            </div>
          </div>
        )}

        {/* ── Results Tabs ────────────────────────────────── */}
        {audit.status === "COMPLETED" && (
          <div className="bg-white border border-slate-200 rounded-xl">
            <div className="flex border-b border-slate-200">
              {(["overall", "fairness", "explainability", "robustness"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 px-4 py-3 text-sm font-medium capitalize transition-colors
                    ${activeTab === tab ? "text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50" : "text-slate-600 hover:text-slate-900"}`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="p-6">
              {activeTab === "fairness" && <FairnessTab result={audit.fairnessResult} />}
              {activeTab === "explainability" && <ExplainTab result={audit.explainResult} />}
              {activeTab === "robustness" && <RobustTab result={audit.robustResult} />}
              {activeTab === "overall" && (
                <div className="space-y-4">
                  <ScoreRow label="Fairness" score={audit.fairnessResult?.score} icon={<Shield className="h-4 w-4" />} />
                  <ScoreRow label="Explainability" score={audit.explainResult?.score} icon={<BarChart2 className="h-4 w-4" />} />
                  <ScoreRow label="Robustness" score={audit.robustResult?.score} icon={<Zap className="h-4 w-4" />} />
                </div>
              )}
            </div>
          </div>
        )}

        {audit.status === "FAILED" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex gap-4">
            <XCircle className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <div className="font-medium text-red-900 mb-1">Audit Failed</div>
              <div className="text-sm text-red-700">{audit.errorMessage || "An error occurred during the audit."}</div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function ScoreRow({ label, score, icon }: { label: string; score?: number; icon: React.ReactNode }) {
  const s = score ?? 0;
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2 w-40 text-slate-600 text-sm">
        {icon}
        {label}
      </div>
      <div className="flex-1 bg-slate-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${s >= 80 ? "bg-green-500" : s >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
          style={{ width: `${s}%` }}
        />
      </div>
      <div className="w-12 text-right text-sm font-medium">{s}/100</div>
    </div>
  );
}

function FairnessTab({ result }: { result?: Audit["fairnessResult"] }) {
  if (!result) return <p className="text-slate-500">No fairness data available</p>;
  return (
    <div className="space-y-4">
      <p className="text-slate-600 text-sm">{result.summary}</p>
      {[
        { label: "Demographic Parity", data: result.demographic_parity },
        { label: "Equalized Odds", data: result.equalized_odds },
        { label: "Disparate Impact", data: result.disparate_impact },
      ].map(({ label, data }) => (
        <div key={label} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
          <span className="text-sm font-medium">{label}</span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">{data.value?.toFixed(3)}</span>
            {data.pass ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ExplainTab({ result }: { result?: Audit["explainResult"] }) {
  if (!result) return <p className="text-slate-500">No explainability data available</p>;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-600">Quality:</span>
        <span className="text-sm font-medium capitalize">{result.explanation_quality}</span>
      </div>
      {result.shap?.summary_plot_b64 && (
        <img
          src={`data:image/png;base64,${result.shap.summary_plot_b64}`}
          alt="SHAP Feature Importance"
          className="w-full rounded-lg border border-slate-200"
        />
      )}
      <div>
        <h3 className="text-sm font-semibold mb-2">Top Features (SHAP)</h3>
        {result.shap?.top_features?.map((f) => (
          <div key={f.name} className="flex items-center gap-3 mb-1">
            <span className="text-xs text-slate-600 w-40 truncate">{f.name}</span>
            <div className="flex-1 bg-slate-100 rounded-full h-1.5">
              <div
                className="bg-indigo-500 h-1.5 rounded-full"
                style={{ width: `${Math.min(f.importance * 300, 100)}%` }}
              />
            </div>
            <span className="text-xs text-slate-500">{f.importance.toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RobustTab({ result }: { result?: Audit["robustResult"] }) {
  if (!result) return <p className="text-slate-500">No robustness data available</p>;
  return (
    <div className="space-y-4">
      <p className="text-slate-600 text-sm">{result.summary}</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-lg font-bold">{(result.adversarial_robustness * 100).toFixed(0)}%</div>
          <div className="text-xs text-slate-500">Adversarial Robustness</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-lg font-bold capitalize">{result.missing_data_handling}</div>
          <div className="text-xs text-slate-500">Missing Data Handling</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-lg font-bold">{result.edge_case_failures}</div>
          <div className="text-xs text-slate-500">Edge Case Failures</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-lg font-bold">{result.total_tests}</div>
          <div className="text-xs text-slate-500">Total Tests Run</div>
        </div>
      </div>
    </div>
  );
}
