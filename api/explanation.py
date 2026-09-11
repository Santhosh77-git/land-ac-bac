# api/explanation.py
#
# Explainability logic + FastAPI router — all in one file.
#
# Functions (also importable directly):
#   get_model_info()               -> dict
#   get_feature_importance()       -> list[dict]
#   explain_prediction(data)       -> dict
#   explain_with_narrative(data)   -> dict
#
# FastAPI endpoints:
#   GET  /explain/model-info
#   GET  /explain/feature-importance
#   POST /explain/predict
#   POST /explain/narrative

import os
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


# ============================================================
# SKLEARN COMPATIBILITY PATCH
# Models may have been pickled with sklearn 1.6; patch missing
# internal classes so they load cleanly on sklearn 1.9+.
# ============================================================

try:
    import sklearn.compose._column_transformer as _sct
    if not hasattr(_sct, "_RemainderColsList"):
        class _RemainderColsList(list):
            """Compatibility shim for sklearn <1.7 pickled models."""
        _sct._RemainderColsList = _RemainderColsList
except Exception:
    pass


# ============================================================
# PATHS
# ============================================================

_BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
_MODEL_DIR = os.path.join(_BASE_DIR, "models")

_CLASSIFIER_PATH = os.path.join(_MODEL_DIR, "delay_classifier.pkl")
_REGRESSOR_PATH  = os.path.join(_MODEL_DIR, "delay_regressor.pkl")
_FEATURES_PATH   = os.path.join(_MODEL_DIR, "feature_columns.pkl")
_METADATA_PATH   = os.path.join(_MODEL_DIR, "model_metadata.json")


# ============================================================
# LOAD MODELS (once, at import time)
# ============================================================

try:
    _classifier   = joblib.load(_CLASSIFIER_PATH)
    _regressor    = joblib.load(_REGRESSOR_PATH)
    _feature_cols = joblib.load(_FEATURES_PATH)

    with open(_METADATA_PATH, "r", encoding="utf-8") as _f:
        _metadata = json.load(_f)

    _MODELS_LOADED = True
    _load_error: Optional[str] = None

except Exception as _e:
    _MODELS_LOADED = False
    _load_error    = str(_e)
    _classifier    = None
    _regressor     = None
    _feature_cols  = []
    _metadata      = {}


# ============================================================
# SHAP & XGBOOST AVAILABILITY
# ============================================================

try:
    import xgboost as _xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

try:
    import shap as _shap  # noqa: F401
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

# Public exports
SHAP_AVAILABLE = _SHAP_AVAILABLE or _XGB_AVAILABLE


# ============================================================
# HELPERS
# ============================================================

_CATEGORICAL_COLS = [
    "project_type", "state", "district",
    "current_stage", "administrative_bottleneck",
    "ownership_conflicts"
]


def _get_orig_feature(enc_name: str) -> str:
    """Map one-hot encoded or passthrough feature names back to the original 33 raw features."""
    name_str = str(enc_name)
    if name_str.startswith("numerical__"):
        return name_str[len("numerical__"):]
    if name_str.startswith("categorical__"):
        clean = name_str[len("categorical__"):]
        for col in _CATEGORICAL_COLS:
            if clean.startswith(col + "_"):
                return col
    return name_str


def _get_risk_level(probability: float) -> str:
    if probability >= 0.80:
        return "Critical"
    elif probability >= 0.60:
        return "High"
    elif probability >= 0.40:
        return "Medium"
    return "Low"


def _compute_shap_factors(pipeline: Any, input_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Compute SHAP factors for an XGBoost sklearn Pipeline.
    Falls back gracefully if booster prediction fails.
    """
    if pipeline is None:
        return []

    try:
        preproc = pipeline.named_steps.get("preprocessor")
        xgb_model = pipeline.named_steps.get("model")
        if preproc is None or xgb_model is None:
            return []

        transformed = preproc.transform(input_df)
        names = preproc.get_feature_names_out()

        if _XGB_AVAILABLE and hasattr(xgb_model, "get_booster"):
            booster = xgb_model.get_booster()
            dmat = _xgb.DMatrix(transformed)
            contribs = booster.predict(dmat, pred_contribs=True)
            # contribs has shape (1, n_features + 1), last element is bias
            row_contribs = contribs[0][:-1]
            feature_shap: Dict[str, float] = defaultdict(float)
            for enc_name, val in zip(names, row_contribs):
                orig_col = _get_orig_feature(enc_name)
                feature_shap[orig_col] += float(val)

            factors = sorted(
                [
                    {
                        "feature": feat,
                        "shap_value": round(val, 6),
                        "impact": "increases risk" if val > 0 else "decreases risk",
                    }
                    for feat, val in feature_shap.items()
                ],
                key=lambda x: abs(x["shap_value"]),
                reverse=True,
            )
            return factors
    except Exception:
        pass

    return []


# ============================================================
# CORE FUNCTIONS (importable directly)
# ============================================================

def get_model_info() -> Dict[str, Any]:
    """
    Return metadata about the loaded models.
    """
    if not _MODELS_LOADED:
        raise RuntimeError(f"Models not loaded: {_load_error}")

    return {
        "classifier":         _metadata.get("classifier", type(_classifier).__name__ if _classifier else "Unknown"),
        "regressor":          _metadata.get("regressor",  type(_regressor).__name__ if _regressor else "Unknown"),
        "number_of_features": _metadata.get("number_of_features", len(_feature_cols)),
        "features":           _feature_cols,
        "shap_available":     SHAP_AVAILABLE,
        "risk_thresholds":    _metadata.get("risk_thresholds", {}),
    }


def get_feature_importance() -> List[Dict[str, Any]]:
    """
    Return classifier feature importances aggregated by original features,
    sorted descending.
    """
    if not _MODELS_LOADED:
        raise RuntimeError(f"Models not loaded: {_load_error}")

    try:
        xgb_model = _classifier.named_steps.get("model", _classifier)
        preproc = _classifier.named_steps.get("preprocessor")

        if hasattr(xgb_model, "feature_importances_") and preproc is not None:
            names = preproc.get_feature_names_out()
            raw_imps = xgb_model.feature_importances_
            agg_imps: Dict[str, float] = defaultdict(float)
            for name, imp in zip(names, raw_imps):
                agg_imps[_get_orig_feature(name)] += float(imp)

            ranked = sorted(
                [{"feature": feat, "importance": round(float(imp), 6)} for feat, imp in agg_imps.items()],
                key=lambda x: x["importance"],
                reverse=True,
            )
            return ranked
        elif hasattr(xgb_model, "feature_importances_"):
            ranked = sorted(
                zip(_feature_cols, xgb_model.feature_importances_),
                key=lambda x: x[1],
                reverse=True,
            )
            return [{"feature": feat, "importance": round(float(imp), 6)} for feat, imp in ranked]
    except Exception:
        pass

    return []


def explain_prediction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run classifier + regressor on data and return risk assessment and factors.
    """
    if not _MODELS_LOADED:
        raise RuntimeError(f"Models not loaded: {_load_error}")

    input_df = pd.DataFrame([data])

    missing = [c for c in _feature_cols if c not in input_df.columns]
    if missing:
        raise ValueError(f"Missing features: {missing}")

    input_df = input_df[_feature_cols]

    # Classify
    delay_prob = float(_classifier.predict_proba(input_df)[0][1])

    # Regress
    delay_days = max(float(_regressor.predict(input_df)[0]), 0.0)

    # SHAP explanations
    clf_factors = _compute_shap_factors(_classifier, input_df)
    reg_factors = _compute_shap_factors(_regressor, input_df)

    # If factors are empty, provide fallback based on top feature importances
    if not clf_factors:
        imps = get_feature_importance()
        clf_factors = [
            {
                "feature": f["feature"],
                "shap_value": round(f["importance"] * (1.0 if delay_prob >= 0.5 else -1.0), 6),
                "impact": "increases risk" if delay_prob >= 0.5 else "decreases risk",
            }
            for f in imps[:10]
        ]

    return {
        "delay_probability":    round(delay_prob, 4),
        "risk_category":        _get_risk_level(delay_prob),
        "predicted_delay_days": round(delay_days, 2),
        "risk_score":           round(delay_prob * 100),
        "classifier_factors":   clf_factors,
        "regressor_factors":    reg_factors,
    }


def _get_severity(shap_val: float) -> str:
    abs_v = abs(shap_val)
    if abs_v >= 0.20:
        return "CRITICAL"
    elif abs_v >= 0.10:
        return "HIGH"
    elif abs_v >= 0.04:
        return "MEDIUM"
    return "LOW"


def _format_clean_name(feature_name: str) -> str:
    return feature_name.replace("_", " ").title()


def _generate_xai_narrative(feat: str, val: Any, shap_val: float, impact: str) -> str:
    clean = _format_clean_name(feat)
    if shap_val > 0.15:
        return f"{clean} (value: {val}) is critically driving up the delay probability."
    elif shap_val > 0:
        return f"{clean} (value: {val}) moderately contributes to project delay risk."
    elif shap_val < -0.15:
        return f"{clean} (value: {val}) provides strong positive progress, mitigating delay risk."
    else:
        return f"{clean} (value: {val}) helps keep the overall delay risk low."


def explain_with_narrative(data: Dict[str, Any], top_n: int = 8) -> Dict[str, Any]:
    """
    Enhanced explainability with human-readable narratives, severity scores,
    and formatted explanations.
    """
    base_result = explain_prediction(data)

    enriched_clf: List[Dict[str, Any]] = []
    for f in base_result.get("classifier_factors", [])[:top_n]:
        feat = f["feature"]
        val = data.get(feat, "N/A")
        sv = f["shap_value"]
        impact = f["impact"]
        severity = _get_severity(sv)
        clean = _format_clean_name(feat)
        shap_explanation = (
            f"{clean} ({val}) {'increased' if sv > 0 else 'decreased'} the delay risk score by {abs(sv):.4f}."
        )
        xai_explanation = _generate_xai_narrative(feat, val, sv, impact)

        enriched_clf.append({
            "feature": feat,
            "clean_feature": clean,
            "feature_value": val,
            "shap_value": sv,
            "impact": impact,
            "severity": severity,
            "shap_explanation": shap_explanation,
            "xai_explanation": xai_explanation,
        })

    enriched_reg: List[Dict[str, Any]] = []
    for f in base_result.get("regressor_factors", [])[:top_n]:
        feat = f["feature"]
        val = data.get(feat, "N/A")
        sv = f["shap_value"]
        impact = f["impact"]
        severity = _get_severity(sv)
        clean = _format_clean_name(feat)
        shap_explanation = (
            f"{clean} ({val}) {'added' if sv > 0 else 'reduced'} expected delay by {abs(sv):.1f} days."
        )
        xai_explanation = (
            f"{clean} (value: {val}) is {'increasing' if sv > 0 else 'reducing'} the delay by {abs(sv):.1f} days."
        )

        enriched_reg.append({
            "feature": feat,
            "clean_feature": clean,
            "feature_value": val,
            "shap_value": sv,
            "impact": impact,
            "severity": severity,
            "shap_explanation": shap_explanation,
            "xai_explanation": xai_explanation,
        })

    return {
        "delay_probability":    base_result["delay_probability"],
        "risk_category":        base_result["risk_category"],
        "predicted_delay_days": base_result["predicted_delay_days"],
        "risk_score":           base_result["risk_score"],
        "classifier_factors":   enriched_clf,
        "regressor_factors":    enriched_reg,
    }


# ============================================================
# FASTAPI ROUTER
# ============================================================

router = APIRouter(
    prefix="/explain",
    tags=["Explanation"],
)


# ── Input schema ─────────────────────────────────────────────

class ExplainInput(BaseModel):
    project_type: str
    state: str
    district: str
    land_area_acres: float = Field(gt=0)
    affected_families: int = Field(ge=0)
    current_stage: str
    pending_approvals: int = Field(ge=0)
    approval_delay_days: float = Field(ge=0)
    pending_notifications: int = Field(ge=0)
    administrative_bottleneck: str
    coordination_delay_days: float = Field(ge=0)
    legal_disputes: int = Field(ge=0)
    ownership_conflicts: str
    court_cases_pending: int = Field(ge=0)
    legal_resolution_pct: float = Field(ge=0, le=100)
    compensation_completion_pct: float = Field(ge=0, le=100)
    compensation_pending_cases: int = Field(ge=0)
    compensation_delay_days: float = Field(ge=0)
    documentation_completion_pct: float = Field(ge=0, le=100)
    missing_documents: int = Field(ge=0)
    ownership_verification_pct: float = Field(ge=0, le=100)
    survey_completion_pct: float = Field(ge=0, le=100)
    rr_progress_pct: float = Field(ge=0, le=100)
    rr_pending_cases: int = Field(ge=0)
    stakeholder_responsiveness: float = Field(ge=0, le=100)
    possession_progress_pct: float = Field(ge=0, le=100)
    handover_progress_pct: float = Field(ge=0, le=100)
    historical_district_delay_rate: float = Field(ge=0, le=1)
    historical_agency_delay_rate: float = Field(ge=0, le=1)
    similar_project_avg_delay_days: float = Field(ge=0)
    planned_acquisition_days: float = Field(gt=0)
    elapsed_acquisition_days: float = Field(ge=0)
    days_remaining_to_target: float = Field(ge=0)


# ── Endpoints ────────────────────────────────────────────────

@router.get("/model-info")
def model_info_endpoint():
    """Return metadata about the loaded ML models."""
    try:
        return {"success": True, "model_info": get_model_info()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-importance")
def feature_importance_endpoint():
    """Return classifier feature importances sorted descending."""
    try:
        return {"success": True, "feature_importance": get_feature_importance()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
def explain_prediction_endpoint(project: ExplainInput):
    """Run full prediction + SHAP explanation for a single project."""
    try:
        result = explain_prediction(project.model_dump())
        return {"success": True, "explanation": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/narrative")
def explain_narrative_endpoint(project: ExplainInput, top_n: int = 8):
    """Run prediction + narrative XAI explanation with severity indicators."""
    try:
        result = explain_with_narrative(project.model_dump(), top_n=top_n)
        return {"success": True, "narrative_explanation": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
