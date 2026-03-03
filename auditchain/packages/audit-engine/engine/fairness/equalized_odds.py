"""
Equalized Odds fairness check.

Equalized Odds requires that the True Positive Rate (TPR) and
False Positive Rate (FPR) are equal across all sensitive groups:
    P(Ŷ=1 | A=0, Y=y) = P(Ŷ=1 | A=1, Y=y) for y in {0, 1}

A model passes if both TPR difference and FPR difference are below threshold.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.10  # Maximum allowed difference in TPR or FPR


class EqualizedOddsAnalyzer:
    """Analyzes whether a model satisfies equalized odds across sensitive groups."""

    def analyze(self, model: Any, test_data: dict) -> dict:
        """
        Compute equalized odds metrics.

        Args:
            model: A fitted sklearn estimator.
            test_data: Dict with keys 'X', 'y', 'sensitive'.

        Returns:
            Dict with TPR/FPR differences, pass/fail, and per-group breakdown.
        """
        X = test_data["X"]
        y = test_data["y"]
        sensitive = test_data["sensitive"]

        predictions = model.predict(X)
        groups = np.unique(sensitive)

        tpr_by_group: dict[int, float] = {}
        fpr_by_group: dict[int, float] = {}

        for group in groups:
            mask = sensitive == group
            y_g = y[mask]
            pred_g = predictions[mask]

            # True Positive Rate = TP / (TP + FN)
            positives = y_g == 1
            tpr = float(np.mean(pred_g[positives] == 1)) if positives.any() else 0.0

            # False Positive Rate = FP / (FP + TN)
            negatives = y_g == 0
            fpr = float(np.mean(pred_g[negatives] == 1)) if negatives.any() else 0.0

            tpr_by_group[int(group)] = round(tpr, 4)
            fpr_by_group[int(group)] = round(fpr, 4)

        if len(groups) < 2:
            return {"score": 70, "value": 1.0, "pass": True, "note": "Single group — N/A"}

        tpr_values = list(tpr_by_group.values())
        fpr_values = list(fpr_by_group.values())
        tpr_gap = max(tpr_values) - min(tpr_values)
        fpr_gap = max(fpr_values) - min(fpr_values)

        max_gap = max(tpr_gap, fpr_gap)
        passed = max_gap <= PASS_THRESHOLD

        score = max(0, round(100 - (max_gap / PASS_THRESHOLD) * 40))

        result = {
            "score": score,
            "value": round(1 - max_gap, 4),
            "tpr_gap": round(tpr_gap, 4),
            "fpr_gap": round(fpr_gap, 4),
            "pass": passed,
            "threshold": PASS_THRESHOLD,
            "tpr_by_group": {f"group_{k}": v for k, v in tpr_by_group.items()},
            "fpr_by_group": {f"group_{k}": v for k, v in fpr_by_group.items()},
        }

        logger.info(f"Equalized odds: tpr_gap={tpr_gap:.4f}, fpr_gap={fpr_gap:.4f}, pass={passed}")
        return result
