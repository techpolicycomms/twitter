"""
Adversarial robustness testing.

Tests the model's resilience to small perturbations of input features.
A robust model should maintain consistent predictions when inputs are
slightly perturbed (within noise thresholds).
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

NOISE_LEVELS = [0.01, 0.05, 0.1, 0.2]  # Fraction of feature std dev


class AdversarialTester:
    """Tests model robustness against adversarial input perturbations."""

    def test(self, model: Any, test_data: dict) -> dict:
        """
        Run adversarial perturbation tests at multiple noise levels.

        Args:
            model: A fitted sklearn estimator.
            test_data: Dict with key 'X'.

        Returns:
            Dict with robustness score, per-noise-level consistency, and failure cases.
        """
        X = test_data["X"]
        n_samples = min(200, len(X))
        X_sample = X[:n_samples]

        original_preds = model.predict(X_sample)
        feature_stds = np.std(X_sample, axis=0)

        results_by_level = {}
        failure_cases = []
        total_flips = 0

        for noise_level in NOISE_LEVELS:
            noise = np.random.normal(0, noise_level * feature_stds, X_sample.shape)
            X_perturbed = X_sample + noise

            perturbed_preds = model.predict(X_perturbed)
            flips = np.sum(original_preds != perturbed_preds)
            flip_rate = float(flips / n_samples)

            results_by_level[f"noise_{noise_level}"] = {
                "flip_rate": round(flip_rate, 4),
                "flips": int(flips),
                "n_samples": n_samples,
            }

            total_flips += flips

            # Record high-confidence flips as failure cases
            for i in np.where(original_preds != perturbed_preds)[0][:3]:
                failure_cases.append(
                    {
                        "noise_level": noise_level,
                        "original_pred": int(original_preds[i]),
                        "perturbed_pred": int(perturbed_preds[i]),
                    }
                )

        # Score: low flip rate at small noise = high robustness
        small_noise_flip_rate = results_by_level["noise_0.01"]["flip_rate"]
        medium_noise_flip_rate = results_by_level["noise_0.05"]["flip_rate"]

        adversarial_score = max(
            0,
            min(100, round(100 - (small_noise_flip_rate * 200) - (medium_noise_flip_rate * 50))),
        )

        return {
            "score": adversarial_score,
            "adversarial_robustness": round(1 - (total_flips / (n_samples * len(NOISE_LEVELS))), 4),
            "results_by_noise_level": results_by_level,
            "failure_cases": failure_cases[:10],  # Return top 10 failures
            "total_samples_tested": n_samples,
        }
