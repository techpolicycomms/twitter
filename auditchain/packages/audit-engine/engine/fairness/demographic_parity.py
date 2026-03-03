"""
Demographic Parity fairness check.

Demographic parity (also called statistical parity) requires that the
probability of receiving a positive outcome is equal across all groups:
    P(Ŷ=1 | A=0) ≈ P(Ŷ=1 | A=1)

A model passes if the difference in selection rates is below threshold (0.1).
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.10  # Maximum allowed difference in selection rates


class DemographicParityAnalyzer:
    """Analyzes whether a model exhibits demographic parity across sensitive groups."""

    def analyze(self, model: Any, test_data: dict) -> dict:
        """
        Compute demographic parity metrics.

        Args:
            model: A fitted sklearn estimator (must have predict method).
            test_data: Dict with keys 'X', 'y', 'sensitive'.

        Returns:
            Dict with value, pass/fail, threshold, and per-group selection rates.
        """
        X = test_data["X"]
        sensitive = test_data["sensitive"]

        predictions = model.predict(X)

        groups = np.unique(sensitive)
        selection_rates = {}
        for group in groups:
            mask = sensitive == group
            selection_rates[int(group)] = float(np.mean(predictions[mask]))

        if len(groups) < 2:
            logger.warning("Only one group found — demographic parity requires at least 2")
            return {"score": 70, "value": 1.0, "pass": True, "note": "Single group — N/A"}

        # Compute max parity gap across all group pairs
        rates = list(selection_rates.values())
        max_gap = max(rates) - min(rates)
        passed = max_gap <= PASS_THRESHOLD

        # Convert gap to a 0-100 score (lower gap = higher score)
        score = max(0, round(100 - (max_gap / PASS_THRESHOLD) * 40))

        result = {
            "score": score,
            "value": round(1 - max_gap, 4),  # 1.0 = perfect parity
            "max_gap": round(max_gap, 4),
            "pass": passed,
            "threshold": PASS_THRESHOLD,
            "selection_rates": {f"group_{k}": round(v, 4) for k, v in selection_rates.items()},
        }

        logger.info(f"Demographic parity: gap={max_gap:.4f}, pass={passed}")
        return result
