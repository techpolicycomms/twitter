import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AuditChain — AI Model Auditing Platform",
  description:
    "Independent AI/ML model auditing with blockchain-certified results. Submit your model for fairness, explainability, and robustness analysis.",
  keywords: ["AI auditing", "fairness", "explainability", "blockchain", "SHAP", "model audit"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
