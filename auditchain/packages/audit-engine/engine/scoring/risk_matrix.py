"""
Risk matrix for categorizing audit findings.

Maps individual metric values to risk levels and generates
a structured risk assessment for the audit report.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class RiskLevel(str, Enum):
    """Risk classification levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskFinding:
    """A single risk finding from the audit."""

    category: str
    metric: str
    value: float
    risk_level: RiskLevel
    description: str
    recommendation: str


class RiskMatrix:
    """Evaluates audit results and produces a structured risk matrix."""

    def evaluate(
        self,
        fairness_result: dict,
        explain_result: dict,
        robust_result: dict,
    ) -> dict:
        """
        Evaluate all audit results and produce a risk matrix.

        Args:
            fairness_result: Output from fairness analysis.
            explain_result: Output from explainability analysis.
            robust_result: Output from robustness testing.

        Returns:
            Dict with findings list, overall risk level, and summary.
        """
        findings: List[RiskFinding] = []

        # ── Fairness checks ───────────────────────────────────
        if fairness_result:
            dp = fairness_result.get("demographic_parity", {})
            if dp and not dp.get("pass", True):
                findings.append(
                    RiskFinding(
                        category="Fairness",
                        metric="Demographic Parity",
                        value=dp.get("value", 0),
                        risk_level=RiskLevel.HIGH,
                        description=f"Demographic parity gap exceeds threshold: {dp.get('max_gap', 'N/A')}",
                        recommendation="Apply fairness-aware post-processing or re-train with fairness constraints",
                    )
                )

            di = fairness_result.get("disparate_impact", {})
            if di and not di.get("pass", True):
                findings.append(
                    RiskFinding(
                        category="Fairness",
                        metric="Disparate Impact",
                        value=di.get("value", 0),
                        risk_level=RiskLevel.CRITICAL if di.get("value", 1) < 0.5 else RiskLevel.HIGH,
                        description=f"Disparate impact ratio {di.get('value', 'N/A')} falls below 80% threshold",
                        recommendation="Investigate protected attribute proxies in training data",
                    )
                )

        # ── Explainability checks ─────────────────────────────
        if explain_result:
            exp_score = explain_result.get("score", 100)
            if exp_score < 50:
                findings.append(
                    RiskFinding(
                        category="Explainability",
                        metric="SHAP/LIME Clarity",
                        value=exp_score,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"Low explainability score ({exp_score}/100) — model decisions are opaque",
                        recommendation="Consider using interpretable model architectures or add SHAP post-hoc explanations",
                    )
                )

        # ── Robustness checks ─────────────────────────────────
        if robust_result:
            adv = robust_result.get("adversarial", {})
            adv_score = adv.get("score", 100)
            if adv_score < 60:
                findings.append(
                    RiskFinding(
                        category="Robustness",
                        metric="Adversarial Robustness",
                        value=adv_score,
                        risk_level=RiskLevel.HIGH,
                        description=f"Model is sensitive to small input perturbations (score: {adv_score}/100)",
                        recommendation="Apply adversarial training or input validation/sanitization",
                    )
                )

        # Compute overall risk level from findings
        overall_risk = self._aggregate_risk(findings)

        return {
            "overall_risk": overall_risk.value,
            "findings_count": len(findings),
            "findings": [
                {
                    "category": f.category,
                    "metric": f.metric,
                    "value": f.value,
                    "risk_level": f.risk_level.value,
                    "description": f.description,
                    "recommendation": f.recommendation,
                }
                for f in findings
            ],
        }

    def _aggregate_risk(self, findings: List[RiskFinding]) -> RiskLevel:
        """Aggregate findings into an overall risk level."""
        if not findings:
            return RiskLevel.LOW

        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }

        max_risk = max(findings, key=lambda f: risk_order[f.risk_level])
        return max_risk.risk_level
