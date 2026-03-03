"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { auditsApi } from "@/lib/api";
import { Shield, Upload, ChevronRight, ChevronLeft } from "lucide-react";

const STEPS = [
  "Organization",
  "Model Upload",
  "Dataset Info",
  "Audit Scope",
  "Review",
];

/**
 * Multi-step audit submission form.
 */
export default function NewAuditPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    modelName: "",
    modelVersion: "",
    modelType: "sklearn" as "sklearn" | "onnx" | "api" | "pytorch",
    apiEndpoint: "",
    modelFile: null as File | null,
    datasetDescription: "",
    sensitiveAttributes: "",
    scope: { fairness: true, explainability: true, robustness: true },
  });

  const update = (key: keyof typeof form, value: unknown) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("modelName", form.modelName);
      formData.append("modelType", form.modelType);
      if (form.modelVersion) formData.append("modelVersion", form.modelVersion);
      if (form.modelFile) formData.append("modelFile", form.modelFile);
      formData.append("scope", JSON.stringify(form.scope));

      const audit = await auditsApi.submit(formData);
      router.push(`/audits/${audit.id}`);
    } catch (err) {
      setError("Failed to submit audit. Please try again.");
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-600" />
          <span className="font-bold text-xl">Submit New Audit</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10">
        {/* ── Step indicator ─────────────────────────────── */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((name, i) => (
            <div key={name} className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold
                  ${i < step ? "bg-green-500 text-white" : i === step ? "bg-indigo-600 text-white" : "bg-slate-200 text-slate-500"}`}
              >
                {i < step ? "✓" : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-0.5 w-8 ${i < step ? "bg-green-500" : "bg-slate-200"}`} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-5">{STEPS[step]}</h2>

          {/* Step 0: Organization */}
          {step === 0 && (
            <div className="space-y-4">
              <p className="text-slate-600 text-sm">
                Organization details are pulled from your account. You can update them in Settings.
              </p>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Model Name *</label>
                <input
                  value={form.modelName}
                  onChange={(e) => update("modelName", e.target.value)}
                  placeholder="e.g. Loan Approval Classifier v2"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Model Version</label>
                <input
                  value={form.modelVersion}
                  onChange={(e) => update("modelVersion", e.target.value)}
                  placeholder="e.g. 2.1.0"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
          )}

          {/* Step 1: Model Upload */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Model Type *</label>
                <select
                  value={form.modelType}
                  onChange={(e) => update("modelType", e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="sklearn">scikit-learn (pickle/joblib)</option>
                  <option value="onnx">ONNX</option>
                  <option value="pytorch">PyTorch</option>
                  <option value="api">API Endpoint</option>
                </select>
              </div>

              {form.modelType !== "api" ? (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Model File
                  </label>
                  <div
                    className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-400 transition-colors"
                    onClick={() => document.getElementById("model-file-input")?.click()}
                  >
                    <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
                    {form.modelFile ? (
                      <p className="text-sm text-slate-700 font-medium">{form.modelFile.name}</p>
                    ) : (
                      <>
                        <p className="text-sm text-slate-600">
                          Drop your model file here or click to browse
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                          Supports: .pkl, .pickle, .onnx, .joblib, .h5 (max 100MB)
                        </p>
                      </>
                    )}
                  </div>
                  <input
                    id="model-file-input"
                    type="file"
                    className="hidden"
                    accept=".pkl,.pickle,.onnx,.joblib,.h5"
                    onChange={(e) => update("modelFile", e.target.files?.[0] ?? null)}
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">API Endpoint URL</label>
                  <input
                    value={form.apiEndpoint}
                    onChange={(e) => update("apiEndpoint", e.target.value)}
                    placeholder="https://your-model-api.com/predict"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}
            </div>
          )}

          {/* Step 2: Dataset Info */}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Dataset Description
                </label>
                <textarea
                  value={form.datasetDescription}
                  onChange={(e) => update("datasetDescription", e.target.value)}
                  rows={4}
                  placeholder="Describe the training dataset (size, time range, collection method)..."
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Sensitive / Protected Attributes
                </label>
                <input
                  value={form.sensitiveAttributes}
                  onChange={(e) => update("sensitiveAttributes", e.target.value)}
                  placeholder="e.g. gender, race, age_group"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-xs text-slate-400 mt-1">
                  These attributes will be used for fairness analysis
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Audit Scope */}
          {step === 3 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600 mb-4">
                Select which analyses to include in the audit:
              </p>
              {[
                {
                  key: "fairness" as const,
                  label: "Fairness Analysis",
                  desc: "Demographic parity, equalized odds, disparate impact (35% of trust score)",
                },
                {
                  key: "explainability" as const,
                  label: "Explainability Analysis",
                  desc: "SHAP global feature importance, LIME local explanations (25% of trust score)",
                },
                {
                  key: "robustness" as const,
                  label: "Robustness Testing",
                  desc: "Adversarial inputs, edge cases, missing data handling (25% of trust score)",
                },
              ].map(({ key, label, desc }) => (
                <label
                  key={key}
                  className={`flex items-start gap-4 p-4 border rounded-xl cursor-pointer transition-colors
                    ${form.scope[key] ? "border-indigo-300 bg-indigo-50" : "border-slate-200"}`}
                >
                  <input
                    type="checkbox"
                    checked={form.scope[key]}
                    onChange={(e) =>
                      update("scope", { ...form.scope, [key]: e.target.checked })
                    }
                    className="mt-0.5"
                  />
                  <div>
                    <div className="font-medium text-slate-900">{label}</div>
                    <div className="text-sm text-slate-600">{desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* Step 4: Review */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="bg-slate-50 rounded-xl p-4 space-y-2 text-sm">
                <Row label="Model Name" value={form.modelName} />
                <Row label="Model Type" value={form.modelType} />
                {form.modelVersion && <Row label="Version" value={form.modelVersion} />}
                {form.modelFile && <Row label="Model File" value={form.modelFile.name} />}
                <Row
                  label="Audit Scope"
                  value={Object.entries(form.scope)
                    .filter(([, v]) => v)
                    .map(([k]) => k)
                    .join(", ")}
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* ── Navigation buttons ────────────────────────── */}
          <div className="flex gap-3 mt-6 pt-5 border-t border-slate-100">
            {step > 0 && (
              <button
                onClick={() => setStep((s) => s - 1)}
                className="flex items-center gap-1 px-4 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
            )}
            <div className="flex-1" />
            {step < STEPS.length - 1 ? (
              <button
                onClick={() => setStep((s) => s + 1)}
                disabled={step === 0 && !form.modelName}
                className="flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                Next <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {submitting ? "Submitting..." : "Submit Audit"}
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}
