"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { auditsApi } from "@/lib/api";
import type { Audit } from "@/lib/types";
import {
  Shield,
  PlusCircle,
  CheckCircle,
  Clock,
  XCircle,
  Award,
  Activity,
} from "lucide-react";

/**
 * Client dashboard — shows overview cards, recent activity,
 * and a quick-start "Submit New Audit" CTA.
 */
export default function DashboardPage() {
  const [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    completed: 0,
    certs: 0,
  });

  useEffect(() => {
    auditsApi
      .list({ limit: 10 })
      .then(({ audits: data, total }) => {
        setAudits(data);
        setStats({
          total,
          active: data.filter((a) => a.status === "RUNNING" || a.status === "PENDING").length,
          completed: data.filter((a) => a.status === "COMPLETED").length,
          certs: data.filter((a) => a.certificate).length,
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Top bar ─────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-600" />
            <span className="font-bold text-xl text-slate-900">AuditChain</span>
          </div>
          <nav className="flex items-center gap-6 text-sm">
            <Link href="/dashboard" className="text-indigo-600 font-medium">Dashboard</Link>
            <Link href="/audits/new" className="text-slate-600 hover:text-slate-900">New Audit</Link>
            <Link href="/reports" className="text-slate-600 hover:text-slate-900">Reports</Link>
            <Link href="/verify" className="text-slate-600 hover:text-slate-900">Verify</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
            <p className="text-slate-600 mt-1">Manage your AI model audits</p>
          </div>
          <Link
            href="/audits/new"
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            <PlusCircle className="h-4 w-4" />
            Submit New Audit
          </Link>
        </div>

        {/* ── Stats Cards ─────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Audits", value: stats.total, icon: Activity, color: "text-blue-600 bg-blue-50" },
            { label: "Active", value: stats.active, icon: Clock, color: "text-yellow-600 bg-yellow-50" },
            { label: "Completed", value: stats.completed, icon: CheckCircle, color: "text-green-600 bg-green-50" },
            { label: "Certificates", value: stats.certs, icon: Award, color: "text-indigo-600 bg-indigo-50" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white border border-slate-200 rounded-xl p-5">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{value}</div>
              <div className="text-sm text-slate-600">{label}</div>
            </div>
          ))}
        </div>

        {/* ── Recent Audits ────────────────────────────── */}
        <div className="bg-white border border-slate-200 rounded-xl">
          <div className="px-6 py-4 border-b border-slate-200">
            <h2 className="font-semibold text-slate-900">Recent Audits</h2>
          </div>

          {loading ? (
            <div className="p-8 text-center text-slate-500">Loading audits...</div>
          ) : audits.length === 0 ? (
            <div className="p-12 text-center">
              <Shield className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 mb-4">No audits yet. Submit your first AI model for audit.</p>
              <Link
                href="/audits/new"
                className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                <PlusCircle className="h-4 w-4" />
                Submit Audit
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {audits.map((audit) => (
                <Link
                  key={audit.id}
                  href={`/audits/${audit.id}`}
                  className="flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <StatusIcon status={audit.status} />
                    <div>
                      <div className="font-medium text-slate-900">{audit.modelName}</div>
                      <div className="text-sm text-slate-500">
                        {audit.modelType} · {new Date(audit.submittedAt).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {audit.trustScore && (
                      <span className="text-sm font-semibold text-slate-700">
                        {audit.trustScore}/100
                      </span>
                    )}
                    {audit.certificate && (
                      <span className="flex items-center gap-1 text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full">
                        <Award className="h-3 w-3" />
                        Certified
                      </span>
                    )}
                    <StatusBadge status={audit.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function StatusIcon({ status }: { status: Audit["status"] }) {
  const iconProps = { className: "h-5 w-5" };
  switch (status) {
    case "COMPLETED":
      return <CheckCircle {...iconProps} className="h-5 w-5 text-green-500" />;
    case "RUNNING":
    case "PENDING":
      return <Clock {...iconProps} className="h-5 w-5 text-yellow-500" />;
    case "FAILED":
      return <XCircle {...iconProps} className="h-5 w-5 text-red-500" />;
  }
}

function StatusBadge({ status }: { status: Audit["status"] }) {
  const styles: Record<Audit["status"], string> = {
    COMPLETED: "bg-green-50 text-green-700",
    RUNNING: "bg-yellow-50 text-yellow-700",
    PENDING: "bg-slate-100 text-slate-600",
    FAILED: "bg-red-50 text-red-700",
  };
  return (
    <span className={`text-xs px-2 py-1 rounded-full font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}
