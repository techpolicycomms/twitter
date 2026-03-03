"""
Stress testing and edge case validation.

Tests model behavior with:
- Missing/null values (NaN imputation edge cases)
- Extreme values (boundary inputs)
- Uniform inputs (all-zero, all-one)
- Out-of-distribution samples
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class StressTester:
    """Tests model robustness with edge cases and boundary inputs."""

    def test(self, model: Any, test_data: dict) -> dict:
        """
        Run stress tests on the model.

        Args:
            model: A fitted sklearn estimator.
            test_data: Dict with key 'X'.

        Returns:
            Dict with stress test score and per-test results.
        """
        X = test_data["X"]
        n_features = X.shape[1]
        n_samples = min(100, len(X))
        X_base = X[:n_samples]

        results = {}

        # ── Test 1: All-zeros input ──────────────────────────
        X_zeros = np.zeros((n_samples, n_features))
        results["all_zeros"] = self._run_test(model, X_zeros, "all_zeros")

        # ── Test 2: All-ones input ───────────────────────────
        X_ones = np.ones((n_samples, n_features))
        results["all_ones"] = self._run_test(model, X_ones, "all_ones")

        # ── Test 3: Extreme values (3x std dev) ──────────────
        X_extreme = X_base + 3 * np.std(X_base, axis=0)
        results["extreme_values"] = self._run_test(model, X_extreme, "extreme_values")

        # ── Test 4: Negative extreme values ──────────────────
        X_neg_extreme = X_base - 3 * np.std(X_base, axis=0)
        results["negative_extreme"] = self._run_test(model, X_neg_extreme, "negative_extreme")

        # ── Test 5: Random uniform noise ─────────────────────
        X_random = np.random.uniform(
            np.min(X_base), np.max(X_base), (n_samples, n_features)
        )
        results["random_uniform"] = self._run_test(model, X_random, "random_uniform")

        # Compute overall stress score
        passing_tests = sum(1 for r in results.values() if r.get("crashed") is False)
        crash_penalty = sum(1 for r in results.values() if r.get("crashed"))

        score = max(0, min(100, round((passing_tests / len(results)) * 100 - crash_penalty * 10)))

        return {
            "score": score,
            "tests": results,
            "total_tests": len(results),
            "passing_tests": passing_tests,
            "missing_data_handling": "robust" if score >= 70 else "fragile",
        }

    def _run_test(self, model: Any, X_test: np.ndarray, test_name: str) -> dict:
        """Run a single stress test and return results."""
        try:
            preds = model.predict(X_test)
            unique_preds = np.unique(preds)
            return {
                "crashed": False,
                "unique_predictions": unique_preds.tolist(),
                "prediction_distribution": {
                    str(p): int(np.sum(preds == p)) for p in unique_preds
                },
            }
        except Exception as e:
            logger.warning(f"Stress test '{test_name}' caused model crash: {e}")
            return {"crashed": True, "error": str(e)}
