"""
AuditChain Audit Engine — FastAPI wrapper.

Exposes endpoints for:
- /analyze/fairness    — IBM AIF360-based fairness metrics
- /analyze/explainability — SHAP + LIME explanations
- /analyze/robustness  — adversarial and edge-case testing
- /health              — liveness probe
"""

import logging
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.pipeline import AuditPipeline
from engine.fairness.demographic_parity import DemographicParityAnalyzer
from engine.fairness.equalized_odds import EqualizedOddsAnalyzer
from engine.fairness.disparate_impact import DisparateImpactAnalyzer
from engine.explainability.shap_explainer import ShapExplainer
from engine.explainability.lime_explainer import LimeExplainer
from engine.robustness.adversarial import AdversarialTester
from engine.robustness.stress_test import StressTester
from engine.scoring.trust_score import TrustScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AuditChain Audit Engine",
    description="Python-based AI model auditing engine with fairness, explainability, and robustness analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    """Request payload for analysis endpoints."""

    audit_id: str
    model_path: Optional[str] = None
    model_type: str  # sklearn, onnx, api
    scope: dict


@app.get("/health")
async def health() -> dict:
    """Liveness probe — returns OK if the engine is running."""
    return {"status": "ok", "service": "audit-engine"}


@app.post("/analyze/fairness")
async def analyze_fairness(request: AnalysisRequest) -> dict:
    """
    Run fairness analysis on the submitted model.

    Checks demographic parity, equalized odds, and disparate impact ratio.
    Returns JSON with metrics and pass/fail per check.
    """
    logger.info(f"Fairness analysis requested for audit: {request.audit_id}")

    try:
        pipeline = AuditPipeline(
            audit_id=request.audit_id,
            model_path=request.model_path,
            model_type=request.model_type,
        )

        dp_result = DemographicParityAnalyzer().analyze(pipeline.model, pipeline.test_data)
        eo_result = EqualizedOddsAnalyzer().analyze(pipeline.model, pipeline.test_data)
        di_result = DisparateImpactAnalyzer().analyze(pipeline.model, pipeline.test_data)

        # Composite fairness score
        scores = [dp_result["score"], eo_result["score"], di_result["score"]]
        composite_score = round(sum(scores) / len(scores))

        return {
            "audit_id": request.audit_id,
            "score": composite_score,
            "demographic_parity": dp_result,
            "equalized_odds": eo_result,
            "disparate_impact": di_result,
            "summary": _fairness_summary(composite_score),
        }

    except Exception as e:
        logger.error(f"Fairness analysis failed for {request.audit_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/explainability")
async def analyze_explainability(request: AnalysisRequest) -> dict:
    """
    Generate SHAP and LIME explanations for the model.

    Returns global feature importance, local explanations,
    and base64-encoded visualization plots.
    """
    logger.info(f"Explainability analysis requested for audit: {request.audit_id}")

    try:
        pipeline = AuditPipeline(
            audit_id=request.audit_id,
            model_path=request.model_path,
            model_type=request.model_type,
        )

        shap_result = ShapExplainer().explain(pipeline.model, pipeline.test_data)
        lime_result = LimeExplainer().explain(pipeline.model, pipeline.test_data)

        composite_score = round((shap_result["score"] + lime_result["score"]) / 2)

        return {
            "audit_id": request.audit_id,
            "score": composite_score,
            "shap": shap_result,
            "lime": lime_result,
            "explanation_quality": _quality_label(composite_score),
        }

    except Exception as e:
        logger.error(f"Explainability analysis failed for {request.audit_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/robustness")
async def analyze_robustness(request: AnalysisRequest) -> dict:
    """
    Run robustness tests: adversarial inputs, edge cases, missing data handling.

    Returns a robustness score and a list of failure cases.
    """
    logger.info(f"Robustness analysis requested for audit: {request.audit_id}")

    try:
        pipeline = AuditPipeline(
            audit_id=request.audit_id,
            model_path=request.model_path,
            model_type=request.model_type,
        )

        adversarial_result = AdversarialTester().test(pipeline.model, pipeline.test_data)
        stress_result = StressTester().test(pipeline.model, pipeline.test_data)

        composite_score = round(
            (adversarial_result["score"] * 0.6 + stress_result["score"] * 0.4)
        )

        return {
            "audit_id": request.audit_id,
            "score": composite_score,
            "adversarial": adversarial_result,
            "stress_test": stress_result,
            "summary": _robustness_summary(composite_score),
        }

    except Exception as e:
        logger.error(f"Robustness analysis failed for {request.audit_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-model")
async def upload_model(
    audit_id: str = Form(...),
    model_file: UploadFile = File(...),
) -> dict:
    """
    Upload a model file for analysis.
    Saves to disk and returns the file path for subsequent analysis calls.
    """
    upload_dir = Path("/app/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(model_file.filename or "model.pkl").suffix
    file_path = upload_dir / f"{audit_id}{suffix}"

    content = await model_file.read()
    file_path.write_bytes(content)

    logger.info(f"Model uploaded for audit {audit_id}: {file_path}")
    return {"audit_id": audit_id, "model_path": str(file_path)}


# ── Helper functions ──────────────────────────────────────────


def _fairness_summary(score: int) -> str:
    """Return a human-readable fairness summary based on score."""
    if score >= 80:
        return "Model demonstrates fair treatment across demographic groups"
    elif score >= 60:
        return "Model shows moderate fairness issues requiring attention"
    else:
        return "Model exhibits significant fairness concerns — remediation recommended"


def _quality_label(score: int) -> str:
    """Return explainability quality label."""
    if score >= 80:
        return "excellent"
    elif score >= 65:
        return "good"
    elif score >= 50:
        return "moderate"
    else:
        return "poor"


def _robustness_summary(score: int) -> str:
    """Return a human-readable robustness summary."""
    if score >= 80:
        return "Model handles edge cases and adversarial inputs robustly"
    elif score >= 60:
        return "Model shows acceptable robustness with some vulnerabilities"
    else:
        return "Model is vulnerable to adversarial inputs — hardening recommended"


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
