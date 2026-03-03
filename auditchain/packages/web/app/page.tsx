"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Search, FileCheck, Award, ChevronRight, CheckCircle } from "lucide-react";

/**
 * Landing page — explains the value prop, shows the 3-step flow,
 * and includes a public certificate verification search bar.
 */
export default function HomePage() {
  const router = useRouter();
  const [certQuery, setCertQuery] = useState("");

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    if (certQuery.trim()) {
      router.push(`/verify?q=${encodeURIComponent(certQuery.trim())}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-white">
      {/* ── Navigation ────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-400" />
          <span className="font-bold text-xl">AuditChain</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/verify" className="text-slate-300 hover:text-white text-sm">
            Verify Certificate
          </Link>
          <Link
            href="/login"
            className="bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="border border-indigo-500 hover:bg-indigo-500/10 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-6 py-24 text-center">
        <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/30 rounded-full px-4 py-1 mb-6 text-sm text-indigo-300">
          <CheckCircle className="h-4 w-4" />
          Blockchain-Certified AI Audits
        </div>
        <h1 className="text-5xl md:text-6xl font-bold mb-6 leading-tight">
          Independent Auditing
          <br />
          <span className="text-indigo-400">for Your AI Models</span>
        </h1>
        <p className="text-xl text-slate-300 mb-10 max-w-2xl mx-auto leading-relaxed">
          Submit your AI model for independent fairness, explainability, and robustness analysis.
          Receive a tamper-proof blockchain certificate proving your model meets ethical AI standards.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/register"
            className="bg-indigo-600 hover:bg-indigo-700 px-8 py-4 rounded-xl text-lg font-semibold transition-colors flex items-center justify-center gap-2"
          >
            Start Your Audit
            <ChevronRight className="h-5 w-5" />
          </Link>
          <Link
            href="/verify"
            className="border border-slate-600 hover:border-slate-400 px-8 py-4 rounded-xl text-lg font-semibold transition-colors"
          >
            Verify a Certificate
          </Link>
        </div>
      </section>

      {/* ── Certificate Verification Search ──────────────── */}
      <section className="max-w-2xl mx-auto px-6 mb-24">
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6">
          <h2 className="text-center text-lg font-semibold mb-4">
            Verify an Audit Certificate
          </h2>
          <form onSubmit={handleVerify} className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={certQuery}
                onChange={(e) => setCertQuery(e.target.value)}
                placeholder="Enter certificate ID or model hash..."
                className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-10 pr-4 py-3 text-sm placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="bg-indigo-600 hover:bg-indigo-700 px-5 py-3 rounded-lg text-sm font-medium transition-colors"
            >
              Verify
            </button>
          </form>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-6 mb-24">
        <h2 className="text-3xl font-bold text-center mb-12">How AuditChain Works</h2>
        <div className="grid md:grid-cols-3 gap-8">
          {[
            {
              step: "01",
              icon: FileCheck,
              title: "Submit Your Model",
              description:
                "Upload your AI model file (sklearn, ONNX, PyTorch) or provide an API endpoint. Include training data demographics for comprehensive fairness analysis.",
            },
            {
              step: "02",
              icon: Shield,
              title: "Independent Audit",
              description:
                "Our engine runs fairness checks (demographic parity, equalized odds), SHAP/LIME explainability analysis, and adversarial robustness testing.",
            },
            {
              step: "03",
              icon: Award,
              title: "Blockchain Certificate",
              description:
                "Receive a tamper-proof NFT certificate with your trust score on-chain. Anyone can publicly verify your model's audit status forever.",
            },
          ].map(({ step, icon: Icon, title, description }) => (
            <div
              key={step}
              className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 relative"
            >
              <div className="text-indigo-400 text-sm font-mono mb-3">Step {step}</div>
              <div className="bg-indigo-500/10 w-12 h-12 rounded-xl flex items-center justify-center mb-4">
                <Icon className="h-6 w-6 text-indigo-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">{title}</h3>
              <p className="text-slate-400 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Stats ────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-6 mb-24">
        <div className="grid md:grid-cols-4 gap-6">
          {[
            { label: "Models Audited", value: "500+" },
            { label: "Certificates Issued", value: "423" },
            { label: "Fairness Checks Run", value: "12,000+" },
            { label: "Organizations Served", value: "85" },
          ].map(({ label, value }) => (
            <div key={label} className="text-center bg-slate-800/30 border border-slate-700 rounded-xl p-6">
              <div className="text-3xl font-bold text-indigo-400 mb-1">{value}</div>
              <div className="text-slate-400 text-sm">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-slate-700 px-6 py-8 text-center text-slate-500 text-sm">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Shield className="h-4 w-4 text-indigo-400" />
          <span className="font-medium text-slate-400">AuditChain</span>
        </div>
        <p>Independent AI auditing for a trustworthy future.</p>
      </footer>
    </div>
  );
}
