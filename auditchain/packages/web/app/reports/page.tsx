"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { reportsApi } from "@/lib/api";
import type { Audit } from "@/lib/types";
import { Shield, Search, Download, Award, BarChart2, FileText } from "lucide-react";

/**
 * Reports library — searchable, filterable list of completed audit reports.
 */
export default function ReportsPage() {
  const [reports, setReports] = useState<Audit[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const LIMIT = 12;

  const fetchReports = async (p = 1, s = "") => {
    setLoading(true);
    try {
      const { reports: data, total: t } = await reportsApi.list({
        page: p,
        limit: LIMIT,
        search: s || undefined,
      });
      setReports(data);
      setTotal(t);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReports(); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchReports(1, search);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-600" />
            <span className="font-bold text-xl">Reports Library</span>
          </div>
          <nav className="flex items-center gap-6 text-sm">
            <Link href="/dashboard" className="text-slate-600 hover:text-slate-900">Dashboard</Link>
            <Link href="/reports" className="text-indigo-600 font-medium">Reports</Link>
            <Link href="/verify" className="text-slate-600 hover:text-slate-900">Verify</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Audit Reports</h1>
            <p className="text-slate-600 mt-1">{total} completed audits</p>
          </div>
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by model name..."
                className="border border-slate-300 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-56"
              />
            </div>
            <button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
              Search
            </button>
          </form>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-slate-100 rounded w-1/2 mb-4" />
                <div className="h-2 bg-slate-100 rounded mb-1" />
                <div className="h-2 bg-slate-100 rounded w-4/5" />
              </div>
            ))}
          </div>
        ) : reports.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <FileText className="h-12 w-12 mx-auto mb-4 text-slate-300" />
            <p>No reports found{search ? ` for "${search}"` : ""}.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reports.map((report) => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        )}

        {/* ── Pagination ───────────────────────────────── */}
        {total > LIMIT && (
          <div className="flex justify-center gap-2 mt-8">
            <button
              onClick={() => { setPage((p) => p - 1); fetchReports(page - 1, search); }}
              disabled={page === 1}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm disabled:opacity-50 hover:bg-slate-50"
            >
              Previous
            </button>
            <span className="px-4 py-2 text-sm text-slate-600">
              Page {page} of {Math.ceil(total / LIMIT)}
            </span>
            <button
              onClick={() => { setPage((p) => p + 1); fetchReports(page + 1, search); }}
              disabled={page >= Math.ceil(total / LIMIT)}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm disabled:opacity-50 hover:bg-slate-50"
            >
              Next
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function ReportCard({ report }: { report: Audit }) {
  const score = report.trustScore ?? 0;
  const scoreColor = score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-600" : "text-red-600";

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-900 truncate">{report.modelName}</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {report.organization?.name} · {new Date(report.completedAt!).toLocaleDateString()}
          </p>
        </div>
        {report.certificate && (
          <span title="Certified" className="text-indigo-600">
            <Award className="h-5 w-5" />
          </span>
        )}
      </div>

      {/* Score bar */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`text-2xl font-bold ${scoreColor}`}>{score}</div>
        <div className="flex-1">
          <div className="text-xs text-slate-500 mb-1">Trust Score</div>
          <div className="bg-slate-100 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${score >= 80 ? "bg-green-500" : score >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
      </div>

      {/* Scope badges */}
      <div className="flex gap-1 mb-4">
        {report.scope.fairness && <Badge>Fairness</Badge>}
        {report.scope.explainability && <Badge>Explain</Badge>}
        {report.scope.robustness && <Badge>Robust</Badge>}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Link
          href={`/audits/${report.id}`}
          className="flex-1 flex items-center justify-center gap-1 border border-slate-300 hover:bg-slate-50 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
        >
          <BarChart2 className="h-3.5 w-3.5" /> View
        </Link>
        <a
          href={reportsApi.getPdfUrl(report.id)}
          className="flex items-center justify-center gap-1 border border-slate-300 hover:bg-slate-50 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
        >
          <Download className="h-3.5 w-3.5" /> PDF
        </a>
      </div>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-indigo-50 text-indigo-700 text-xs px-2 py-0.5 rounded-full">
      {children}
    </span>
  );
}
