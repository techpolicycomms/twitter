"""
Composite Trust Score calculator.

Combines individual module scores into a single 0-100 trust score:
- Fairness:         35%
- Explainability:   25%
- Robustness:       25%
- Documentation:    15%
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

WEIGHTS = {
    "fairness": 0.35,
    "explainability": 0.25,
    "robustness": 0.25,
    "documentation": 0.15,
}


@dataclass
class TrustScoreInput:
    """Input data for trust score computation."""

    fairness_score: float
    explainability_score: float
    robustness_score: float
    documentation_score: float = 70.0  # Default if not assessed


class TrustScorer:
    """Computes the composite AuditChain trust score."""

    def compute(self, inputs: TrustScoreInput) -> dict:
        """
        Compute the weighted trust score.

        Args:
            inputs: TrustScoreInput with individual module scores.

        Returns:
            Dict with composite score, letter grade, breakdown, and risk level.
        """
        composite = (
            inputs.fairness_score * WEIGHTS["fairness"]
            + inputs.explainability_score * WEIGHTS["explainability"]
            + inputs.robustness_score * WEIGHTS["robustness"]
            + inputs.documentation_score * WEIGHTS["documentation"]
        )
        composite = round(composite)

        return {
            "score": composite,
            "grade": self._grade(composite),
            "risk_level": self._risk_level(composite),
            "breakdown": {
                "fairness": {
                    "score": inputs.fairness_score,
                    "weight": WEIGHTS["fairness"],
                    "contribution": round(inputs.fairness_score * WEIGHTS["fairness"], 1),
                },
                "explainability": {
                    "score": inputs.explainability_score,
                    "weight": WEIGHTS["explainability"],
                    "contribution": round(inputs.explainability_score * WEIGHTS["explainability"], 1),
                },
                "robustness": {
                    "score": inputs.robustness_score,
                    "weight": WEIGHTS["robustness"],
                    "contribution": round(inputs.robustness_score * WEIGHTS["robustness"], 1),
                },
                "documentation": {
                    "score": inputs.documentation_score,
                    "weight": WEIGHTS["documentation"],
                    "contribution": round(inputs.documentation_score * WEIGHTS["documentation"], 1),
                },
            },
        }

    def _grade(self, score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _risk_level(self, score: int) -> str:
        """Convert score to risk classification."""
        if score >= 80:
            return "LOW"
        elif score >= 65:
            return "MEDIUM"
        elif score >= 50:
            return "HIGH"
        else:
            return "CRITICAL"
