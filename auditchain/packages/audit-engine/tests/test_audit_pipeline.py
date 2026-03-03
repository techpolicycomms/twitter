"""
Pytest tests for the AuditChain audit engine.

Tests the full pipeline including fairness, explainability, robustness, and scoring.
Uses a pre-trained sklearn RandomForest classifier (demo mode).
"""

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification

from engine.pipeline import AuditPipeline
from engine.fairness.demographic_parity import DemographicParityAnalyzer
from engine.fairness.equalized_odds import EqualizedOddsAnalyzer
from engine.fairness.disparate_impact import DisparateImpactAnalyzer
from engine.explainability.shap_explainer import ShapExplainer
from engine.robustness.adversarial import AdversarialTester
from engine.robustness.stress_test import StressTester
from engine.scoring.trust_score import TrustScorer, TrustScoreInput
from engine.scoring.risk_matrix import RiskMatrix


@pytest.fixture(scope="module")
def demo_model() -> RandomForestClassifier:
    """Create a small demo RandomForest model for testing."""
    X, y = make_classification(n_samples=500, n_features=8, random_state=42)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture(scope="module")
def test_data(demo_model: RandomForestClassifier) -> dict:
    """Create test data compatible with the audit pipeline format."""
    np.random.seed(42)
    n = 200
    X, y = make_classification(n_samples=n, n_features=8, random_state=99)
    sensitive = np.random.binomial(1, 0.3, n)
    feature_names = [f"feature_{i}" for i in range(8)]

    return {
        "X": X,
        "y": y,
        "sensitive": sensitive,
        "feature_names": feature_names,
    }


# ── AuditPipeline tests ───────────────────────────────────────

class TestAuditPipeline:
    def test_demo_mode_creates_model(self) -> None:
        """Pipeline should create a demo model when no model_path is provided."""
        pipeline = AuditPipeline(audit_id="test-001", model_path=None)
        assert pipeline.model is not None
        assert hasattr(pipeline.model, "predict")

    def test_test_data_has_required_keys(self) -> None:
        """Pipeline should prepare test data with X, y, sensitive, and feature_names."""
        pipeline = AuditPipeline(audit_id="test-002")
        assert "X" in pipeline.test_data
        assert "y" in pipeline.test_data
        assert "sensitive" in pipeline.test_data
        assert "feature_names" in pipeline.test_data

    def test_test_data_shapes_consistent(self) -> None:
        """X, y, and sensitive arrays should have matching lengths."""
        pipeline = AuditPipeline(audit_id="test-003")
        X = pipeline.test_data["X"]
        y = pipeline.test_data["y"]
        sensitive = pipeline.test_data["sensitive"]
        assert len(X) == len(y) == len(sensitive)


# ── Fairness tests ────────────────────────────────────────────

class TestDemographicParity:
    def test_returns_required_keys(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = DemographicParityAnalyzer().analyze(demo_model, test_data)
        assert "score" in result
        assert "value" in result
        assert "pass" in result
        assert "threshold" in result

    def test_score_in_valid_range(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = DemographicParityAnalyzer().analyze(demo_model, test_data)
        assert 0 <= result["score"] <= 100

    def test_value_between_zero_and_one(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = DemographicParityAnalyzer().analyze(demo_model, test_data)
        assert 0 <= result["value"] <= 1.0


class TestEqualizedOdds:
    def test_returns_tpr_and_fpr_gaps(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = EqualizedOddsAnalyzer().analyze(demo_model, test_data)
        assert "tpr_gap" in result
        assert "fpr_gap" in result
        assert 0 <= result["score"] <= 100

    def test_pass_is_boolean(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = EqualizedOddsAnalyzer().analyze(demo_model, test_data)
        assert isinstance(result["pass"], bool)


class TestDisparateImpact:
    def test_returns_dir_value(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = DisparateImpactAnalyzer().analyze(demo_model, test_data)
        assert "value" in result
        assert result["value"] >= 0

    def test_threshold_is_08(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = DisparateImpactAnalyzer().analyze(demo_model, test_data)
        assert result["threshold"] == 0.80


# ── Explainability tests ──────────────────────────────────────

class TestShapExplainer:
    def test_returns_top_features(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = ShapExplainer().explain(demo_model, test_data)
        assert "top_features" in result
        assert len(result["top_features"]) > 0

    def test_score_in_valid_range(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = ShapExplainer().explain(demo_model, test_data)
        assert 0 <= result["score"] <= 100

    def test_feature_importance_is_numeric(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = ShapExplainer().explain(demo_model, test_data)
        for feat in result["top_features"]:
            assert isinstance(feat["importance"], float)
            assert feat["importance"] >= 0


# ── Robustness tests ──────────────────────────────────────────

class TestAdversarialTester:
    def test_returns_score_and_failures(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = AdversarialTester().test(demo_model, test_data)
        assert "score" in result
        assert "failure_cases" in result
        assert 0 <= result["score"] <= 100

    def test_results_by_noise_level(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = AdversarialTester().test(demo_model, test_data)
        assert "results_by_noise_level" in result
        assert len(result["results_by_noise_level"]) == 4  # 4 noise levels


class TestStressTester:
    def test_runs_all_tests(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = StressTester().test(demo_model, test_data)
        assert result["total_tests"] == 5
        assert "tests" in result

    def test_score_in_valid_range(self, demo_model: RandomForestClassifier, test_data: dict) -> None:
        result = StressTester().test(demo_model, test_data)
        assert 0 <= result["score"] <= 100


# ── Scoring tests ─────────────────────────────────────────────

class TestTrustScorer:
    def test_weighted_score_calculation(self) -> None:
        scorer = TrustScorer()
        inputs = TrustScoreInput(
            fairness_score=80.0,
            explainability_score=70.0,
            robustness_score=90.0,
            documentation_score=60.0,
        )
        result = scorer.compute(inputs)
        expected = round(80 * 0.35 + 70 * 0.25 + 90 * 0.25 + 60 * 0.15)
        assert result["score"] == expected

    def test_grade_assignment(self) -> None:
        scorer = TrustScorer()
        test_cases = [(95, "A"), (85, "B"), (75, "C"), (65, "D"), (45, "F")]
        for score, expected_grade in test_cases:
            inputs = TrustScoreInput(score, score, score, score)
            result = scorer.compute(inputs)
            assert result["grade"] == expected_grade, f"Score {score} should be grade {expected_grade}"

    def test_risk_levels(self) -> None:
        scorer = TrustScorer()
        assert scorer._risk_level(85) == "LOW"
        assert scorer._risk_level(70) == "MEDIUM"
        assert scorer._risk_level(55) == "HIGH"
        assert scorer._risk_level(30) == "CRITICAL"


class TestRiskMatrix:
    def test_returns_findings_list(self) -> None:
        matrix = RiskMatrix()
        result = matrix.evaluate(
            fairness_result={"demographic_parity": {"pass": True, "value": 0.95}},
            explain_result={"score": 80},
            robust_result={"adversarial": {"score": 85}},
        )
        assert "findings" in result
        assert "overall_risk" in result

    def test_clean_model_has_low_risk(self) -> None:
        matrix = RiskMatrix()
        result = matrix.evaluate(
            fairness_result={"demographic_parity": {"pass": True}},
            explain_result={"score": 90},
            robust_result={"adversarial": {"score": 90}},
        )
        assert result["overall_risk"] == "LOW"
        assert result["findings_count"] == 0
