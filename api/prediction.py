# api/prediction.py

import os
import json
import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/predict",
    tags=["Prediction"]
)


# ============================================================
# MODEL PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

CLASSIFIER_PATH = os.path.join(
    MODEL_DIR,
    "delay_classifier.pkl"
)

REGRESSOR_PATH = os.path.join(
    MODEL_DIR,
    "delay_regressor.pkl"
)

FEATURES_PATH = os.path.join(
    MODEL_DIR,
    "feature_columns.pkl"
)

METADATA_PATH = os.path.join(
    MODEL_DIR,
    "model_metadata.json"
)


# ============================================================
# LOAD MODELS
# ============================================================

try:
    import sklearn.compose._column_transformer as _sct
    if not hasattr(_sct, "_RemainderColsList"):
        class _RemainderColsList(list):
            """Compatibility shim for sklearn <1.7 pickled models."""
        _sct._RemainderColsList = _RemainderColsList
except Exception:
    pass

try:

    classifier_model = joblib.load(
        CLASSIFIER_PATH
    )

    regressor_model = joblib.load(
        REGRESSOR_PATH
    )

    feature_columns = joblib.load(
        FEATURES_PATH
    )

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        model_metadata = json.load(f)

except Exception as e:

    raise RuntimeError(
        f"Model loading failed: {e}"
    )


# ============================================================
# INPUT SCHEMA
# ============================================================

class ProjectInput(BaseModel):

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

    coordination_delay_days: float = Field(
        ge=0
    )

    legal_disputes: int = Field(ge=0)

    ownership_conflicts: str

    court_cases_pending: int = Field(
        ge=0
    )

    legal_resolution_pct: float = Field(
        ge=0,
        le=100
    )

    compensation_completion_pct: float = Field(
        ge=0,
        le=100
    )

    compensation_pending_cases: int = Field(
        ge=0
    )

    compensation_delay_days: float = Field(
        ge=0
    )

    documentation_completion_pct: float = Field(
        ge=0,
        le=100
    )

    missing_documents: int = Field(
        ge=0
    )

    ownership_verification_pct: float = Field(
        ge=0,
        le=100
    )

    survey_completion_pct: float = Field(
        ge=0,
        le=100
    )

    rr_progress_pct: float = Field(
        ge=0,
        le=100
    )

    rr_pending_cases: int = Field(
        ge=0
    )

    stakeholder_responsiveness: float = Field(
        ge=0,
        le=100
    )

    possession_progress_pct: float = Field(
        ge=0,
        le=100
    )

    handover_progress_pct: float = Field(
        ge=0,
        le=100
    )

    historical_district_delay_rate: float = Field(
        ge=0,
        le=1
    )

    historical_agency_delay_rate: float = Field(
        ge=0,
        le=1
    )

    similar_project_avg_delay_days: float = Field(
        ge=0
    )

    planned_acquisition_days: float = Field(
        gt=0
    )

    elapsed_acquisition_days: float = Field(
        ge=0
    )

    days_remaining_to_target: float = Field(
        ge=0
    )


# ============================================================
# RISK LEVEL FUNCTION
# ============================================================

def get_risk_level(
    probability: float
) -> str:

    if probability >= 0.80:
        return "Critical"

    elif probability >= 0.60:
        return "High"

    elif probability >= 0.40:
        return "Medium"

    return "Low"


# ============================================================
# POST /predict
# ============================================================

@router.post("")
def predict_project(
    project: ProjectInput
):

    try:

        # Convert request to dictionary
        data = project.model_dump()

        # Create DataFrame
        input_df = pd.DataFrame(
            [data]
        )

        # ----------------------------------------------------
        # Verify feature columns
        # ----------------------------------------------------

        missing_features = [
            feature
            for feature in feature_columns
            if feature not in input_df.columns
        ]

        if missing_features:

            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Missing required features",
                    "missing_features": missing_features
                }
            )

        # ----------------------------------------------------
        # IMPORTANT:
        # EXACT SAME FEATURE ORDER USED DURING TRAINING
        # ----------------------------------------------------

        input_df = input_df[
            feature_columns
        ]

        # ----------------------------------------------------
        # CLASSIFICATION
        # ----------------------------------------------------

        delay_probability = float(
            classifier_model.predict_proba(
                input_df
            )[0][1]
        )

        # ----------------------------------------------------
        # REGRESSION
        # ----------------------------------------------------

        expected_delay_days = float(
            regressor_model.predict(
                input_df
            )[0]
        )

        expected_delay_days = max(
            expected_delay_days,
            0
        )

        # ----------------------------------------------------
        # RISK SCORE
        # ----------------------------------------------------

        risk_score = round(
            delay_probability * 100
        )

        risk_level = get_risk_level(
            delay_probability
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "success": True,

            "prediction": {
                "delay_probability": round(
                    delay_probability,
                    4
                ),

                "delay_probability_percent": round(
                    delay_probability * 100,
                    2
                ),

                "risk_score": risk_score,

                "risk_level": risk_level,

                "expected_delay_days": round(
                    expected_delay_days,
                    2
                )
            },

            "model": {
                "classification": "XGBClassifier",
                "regression": "XGBRegressor"
            }
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )