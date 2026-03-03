"""
SHAP (SHapley Additive exPlanations) explainability module.

Computes global feature importance using SHAP values and generates
a summary plot encoded as base64 for inclusion in audit reports.
"""

import base64
import io
import logging
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
import numpy as np
import shap

logger = logging.getLogger(__name__)

MAX_BACKGROUND_SAMPLES = 100
MAX_EXPLAIN_SAMPLES = 50


class ShapExplainer:
    """Generates SHAP-based global and local explanations for ML models."""

    def explain(self, model: Any, test_data: dict) -> dict:
        """
        Compute SHAP values and generate feature importance visualization.

        Args:
            model: A fitted sklearn estimator.
            test_data: Dict with keys 'X', 'feature_names'.

        Returns:
            Dict with top_features list, base64 plot, and quality score.
        """
        X = test_data["X"]
        feature_names = test_data.get("feature_names", [f"feature_{i}" for i in range(X.shape[1])])

        # Use a subsample for speed
        background = shap.sample(X, min(MAX_BACKGROUND_SAMPLES, len(X)))
        explain_data = X[:MAX_EXPLAIN_SAMPLES]

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(explain_data)

            # For binary classifiers, shap_values is a list [class0, class1]
            if isinstance(shap_values, list):
                shap_vals = shap_values[1]  # Use positive class
            else:
                shap_vals = shap_values

            mean_abs_shap = np.abs(shap_vals).mean(axis=0)
            feature_importance = sorted(
                zip(feature_names, mean_abs_shap.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )

            top_features = [
                {"name": name, "importance": round(float(imp), 4)}
                for name, imp in feature_importance[:10]
            ]

            # Generate summary bar plot
            plot_b64 = self._generate_summary_plot(feature_importance[:10])

            # Score based on Gini concentration (higher = more explainable)
            score = self._compute_explainability_score(mean_abs_shap)

            return {
                "score": score,
                "method": "shap_tree_explainer",
                "top_features": top_features,
                "summary_plot_b64": plot_b64,
                "samples_analyzed": len(explain_data),
            }

        except Exception as e:
            logger.warning(f"TreeExplainer failed, falling back to KernelExplainer: {e}")
            return self._fallback_explain(model, background, explain_data, feature_names)

    def _generate_summary_plot(self, feature_importance: list) -> str:
        """Generate a horizontal bar plot of feature importances and return as base64."""
        names = [fi[0] for fi in feature_importance]
        values = [fi[1] for fi in feature_importance]

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.barh(names[::-1], values[::-1], color="#4a4a8a")
        ax.set_xlabel("Mean |SHAP Value|")
        ax.set_title("Global Feature Importance (SHAP)")
        ax.bar_label(bars, fmt="%.3f", padding=3)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    def _compute_explainability_score(self, shap_values: np.ndarray) -> int:
        """
        Score based on how concentrated the model's reliance is on a few features.
        A well-explainable model relies on a small number of meaningful features.
        """
        total = shap_values.sum()
        if total == 0:
            return 50

        # Normalized cumulative importance of top-3 features
        sorted_vals = np.sort(shap_values)[::-1]
        top3_ratio = sorted_vals[:3].sum() / total

        # Higher concentration in meaningful features = more explainable
        score = min(100, int(top3_ratio * 100) + 20)
        return score

    def _fallback_explain(
        self, model: Any, background: np.ndarray, explain_data: np.ndarray, feature_names: list
    ) -> dict:
        """Fallback to KernelExplainer for non-tree models."""
        try:
            explainer = shap.KernelExplainer(model.predict_proba, background[:20])
            shap_values = explainer.shap_values(explain_data[:10], nsamples=50)
            if isinstance(shap_values, list):
                shap_vals = shap_values[1]
            else:
                shap_vals = shap_values

            mean_abs = np.abs(shap_vals).mean(axis=0)
            top_features = sorted(
                zip(feature_names, mean_abs.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )

            return {
                "score": 65,
                "method": "shap_kernel_explainer",
                "top_features": [
                    {"name": n, "importance": round(float(v), 4)} for n, v in top_features[:10]
                ],
                "summary_plot_b64": None,
                "samples_analyzed": len(explain_data[:10]),
            }
        except Exception as e:
            logger.error(f"SHAP fallback also failed: {e}")
            return {"score": 40, "method": "shap_failed", "error": str(e), "top_features": []}
