"""
Main audit pipeline orchestrator.

Loads the submitted model and prepares test data for analysis modules.
Supports sklearn (pickle/joblib), ONNX, and demo mode (built-in sample model).
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


class AuditPipeline:
    """
    Orchestrates loading of model and test data for audit analysis modules.

    Attributes:
        audit_id: Unique identifier for this audit run.
        model: The loaded ML model object (sklearn estimator or ONNX session).
        test_data: Dict with 'X' (features) and 'y' (labels) and optional 'sensitive'.
    """

    def __init__(
        self,
        audit_id: str,
        model_path: Optional[str] = None,
        model_type: str = "sklearn",
    ) -> None:
        self.audit_id = audit_id
        self.model_type = model_type
        self.model: Any = None
        self.test_data: dict = {}

        logger.info(f"Initializing AuditPipeline for audit {audit_id}")
        self._load_model(model_path)
        self._prepare_test_data()

    def _load_model(self, model_path: Optional[str]) -> None:
        """Load model from disk or fall back to the built-in demo model."""
        if model_path and Path(model_path).exists():
            logger.info(f"Loading model from: {model_path}")
            if self.model_type in ("sklearn", "pickle"):
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
            elif self.model_type == "onnx":
                import onnxruntime as ort
                self.model = ort.InferenceSession(model_path)
            else:
                raise ValueError(f"Unsupported model type: {self.model_type}")
        else:
            logger.warning(
                f"No model file found at '{model_path}'. Using built-in demo model."
            )
            self.model = self._create_demo_model()

    def _create_demo_model(self) -> RandomForestClassifier:
        """
        Create a simple demo RandomForest classifier for testing purposes.
        Simulates a loan approval model with demographic features.
        """
        X, y = make_classification(
            n_samples=2000,
            n_features=10,
            n_informative=6,
            random_state=42,
        )
        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X, y)
        logger.info("Demo model created: RandomForestClassifier(n_estimators=100)")
        return clf

    def _prepare_test_data(self) -> None:
        """
        Prepare representative test data for fairness and robustness analysis.
        Uses a synthetic loan approval dataset with demographic attributes.
        """
        np.random.seed(42)
        n_samples = 500

        X, y = make_classification(
            n_samples=n_samples,
            n_features=10,
            n_informative=6,
            random_state=42,
        )

        # Simulate demographic groups (0 = majority, 1 = minority)
        sensitive_attr = np.random.binomial(1, 0.3, n_samples)

        feature_names = [
            "credit_score",
            "annual_income",
            "debt_to_income",
            "employment_years",
            "loan_amount",
            "num_credit_lines",
            "payment_history",
            "loan_purpose_enc",
            "state_enc",
            "age_group",
        ]

        df = pd.DataFrame(X, columns=feature_names)
        df["target"] = y
        df["sensitive"] = sensitive_attr

        self.test_data = {
            "X": X,
            "y": y,
            "sensitive": sensitive_attr,
            "feature_names": feature_names,
            "df": df,
        }

        logger.info(f"Test data prepared: {n_samples} samples, {X.shape[1]} features")
