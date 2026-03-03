"""
Disparate Impact Ratio fairness check.

Disparate impact (also called the 4/5ths rule) compares the selection rate
of a protected group to the selection rate of the reference group:
    DIR = P(Ŷ=1 | A=minority) / P(Ŷ=1 | A=majority)

A model passes if DIR >= 0.8 (i.e., minority selection rate is at least
80% of majority selection rate).
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.80  # 80% rule (4/5ths rule)


class DisparateImpactAnalyzer:
    """Analyzes the disparate impact ratio across sensitive groups."""

    def analyze(self, model: Any, test_data: dict) -> dict:
        """
        Compute the disparate impact ratio.

        Args:
            model: A fitted sklearn estimator.
            test_data: Dict with keys 'X', 'y', 'sensitive'.

        Returns:
            Dict with DIR value, pass/fail, and per-group selection rates.
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
            return {
                "score": 70,
                "value": 1.0,
                "pass": True,
                "note": "Single group — DIR N/A",
            }

        # Identify reference group (highest selection rate) and protected group (lowest)
        min_group = min(selection_rates, key=selection_rates.get)  # type: ignore
        max_group = max(selection_rates, key=selection_rates.get)  # type: ignore

        min_rate = selection_rates[min_group]
        max_rate = selection_rates[max_group]

        # Avoid division by zero
        if max_rate == 0:
            dir_value = 1.0
        else:
            dir_value = min_rate / max_rate

        passed = dir_value >= PASS_THRESHOLD

        # Score: 100 if dir >= 1.0, scales down to 0 as dir approaches 0
        score = max(0, min(100, round(dir_value * 100)))

        result = {
            "score": score,
            "value": round(dir_value, 4),
            "pass": passed,
            "threshold": PASS_THRESHOLD,
            "selection_rates": {f"group_{k}": round(v, 4) for k, v in selection_rates.items()},
            "reference_group": f"group_{max_group}",
            "protected_group": f"group_{min_group}",
        }

        logger.info(f"Disparate impact ratio: {dir_value:.4f}, pass={passed}")
        return result
