"""
LIME (Local Interpretable Model-agnostic Explanations) module.

Generates local explanations for individual predictions showing which
features most influenced a specific model decision.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class LimeExplainer:
    """Generates LIME-based local explanations for ML models."""

    def explain(self, model: Any, test_data: dict) -> dict:
        """
        Generate LIME explanations for a sample of predictions.

        Args:
            model: A fitted sklearn estimator with predict_proba method.
            test_data: Dict with keys 'X', 'feature_names'.

        Returns:
            Dict with local explanations for sample instances and a quality score.
        """
        from lime.lime_tabular import LimeTabularExplainer

        X = test_data["X"]
        feature_names = test_data.get(
            "feature_names", [f"feature_{i}" for i in range(X.shape[1])]
        )

        try:
            explainer = LimeTabularExplainer(
                training_data=X,
                feature_names=feature_names,
                mode="classification",
                random_state=42,
            )

            # Explain 5 sample instances
            n_samples = min(5, len(X))
            sample_indices = np.random.choice(len(X), n_samples, replace=False)
            local_explanations = []

            for idx in sample_indices:
                instance = X[idx]
                try:
                    if hasattr(model, "predict_proba"):
                        predict_fn = model.predict_proba
                    else:
                        # Wrap predict for binary output
                        def predict_fn(x: np.ndarray) -> np.ndarray:
                            preds = model.predict(x)
                            return np.column_stack([1 - preds, preds])

                    explanation = explainer.explain_instance(
                        instance,
                        predict_fn,
                        num_features=6,
                        num_samples=100,
                    )

                    local_explanations.append(
                        {
                            "instance_index": int(idx),
                            "features": [
                                {
                                    "feature": feat,
                                    "weight": round(float(weight), 4),
                                    "direction": "positive" if weight > 0 else "negative",
                                }
                                for feat, weight in explanation.as_list()
                            ],
                            "prediction_probability": round(
                                float(explanation.predict_proba[1]), 4
                            ),
                        }
                    )
                except Exception as e:
                    logger.warning(f"LIME failed for instance {idx}: {e}")
                    continue

            score = self._compute_score(local_explanations)

            return {
                "score": score,
                "method": "lime_tabular",
                "local_explanations": local_explanations,
                "samples_explained": len(local_explanations),
            }

        except Exception as e:
            logger.error(f"LIME explainer failed: {e}")
            return {
                "score": 40,
                "method": "lime_failed",
                "error": str(e),
                "local_explanations": [],
            }

    def _compute_score(self, explanations: list) -> int:
        """
        Score based on the consistency and clarity of LIME explanations.
        Higher score when explanations have clear, high-weight features.
        """
        if not explanations:
            return 40

        # Average the max absolute weight across explanations
        avg_max_weight = np.mean(
            [max(abs(f["weight"]) for f in exp["features"]) if exp["features"] else 0
             for exp in explanations]
        )

        # Normalize: weight > 0.3 is considered very explanatory
        score = min(100, int(avg_max_weight / 0.3 * 80) + 20)
        return score
