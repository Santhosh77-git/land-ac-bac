# api/recommendations.py
#
# Recommendation rules + FastAPI router — all in one file.
#
# Functions (also importable directly):
#   generate_recommendations(data, explain_result) -> list[dict]
#
# FastAPI endpoints:
#   POST /recommendations
#   GET  /recommendations/rules

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.explanation import (
    explain_prediction,
    explain_with_narrative,
    get_model_info,
    get_feature_importance,
    SHAP_AVAILABLE,
)


# ============================================================
# RULE DEFINITIONS
# ============================================================
# Each rule:
#   trigger  : callable(data, explain_result) -> bool
#   category : str
#   priority : str   (Critical | High | Medium | Low)
#   message  : str   (may contain {field} placeholders)

_RULES = [

    # ── Administrative ───────────────────────────────────────

    {
        "id": "ADM-01",
        "trigger":  lambda d, _: d.get("pending_approvals", 0) >= 3,
        "category": "Administrative",
        "priority": "High",
        "message":  (
            "High number of pending approvals ({pending_approvals}). "
            "Escalate to senior officers and set a 15-day clearance deadline."
        ),
    },
    {
        "id": "ADM-02",
        "trigger":  lambda d, _: d.get("approval_delay_days", 0) >= 30,
        "category": "Administrative",
        "priority": "High",
        "message":  (
            "Approval delays exceed {approval_delay_days} days. "
            "Conduct an inter-departmental review meeting immediately."
        ),
    },
    {
        "id": "ADM-03",
        "trigger":  lambda d, _: str(d.get("administrative_bottleneck", "")).strip().lower() in ("yes", "high", "critical", "true", "1"),
        "category": "Administrative",
        "priority": "Critical",
        "message":  (
            "Administrative bottleneck detected. "
            "Assign a dedicated nodal officer to unblock pending processes."
        ),
    },
    {
        "id": "ADM-04",
        "trigger":  lambda d, _: d.get("coordination_delay_days", 0) >= 20,
        "category": "Administrative",
        "priority": "Medium",
        "message":  (
            "Inter-agency coordination delays are {coordination_delay_days} days. "
            "Schedule weekly coordination meetings with all agencies involved."
        ),
    },

    # ── Legal ────────────────────────────────────────────────

    {
        "id": "LEG-01",
        "trigger":  lambda d, _: d.get("legal_disputes", 0) >= 1,
        "category": "Legal",
        "priority": "High",
        "message":  (
            "{legal_disputes} active legal dispute(s) detected. "
            "Engage a dedicated legal team and pursue out-of-court settlements."
        ),
    },
    {
        "id": "LEG-02",
        "trigger":  lambda d, _: d.get("court_cases_pending", 0) >= 1,
        "category": "Legal",
        "priority": "High",
        "message":  (
            "{court_cases_pending} court case(s) pending. "
            "File for expedited hearings; monitor case progress weekly."
        ),
    },
    {
        "id": "LEG-03",
        "trigger":  lambda d, _: str(d.get("ownership_conflicts", "")).strip().lower() in ("yes", "high", "critical", "true", "1"),
        "category": "Legal",
        "priority": "Critical",
        "message":  (
            "Ownership conflicts present. "
            "Initiate joint verification surveys with revenue authorities immediately."
        ),
    },
    {
        "id": "LEG-04",
        "trigger":  lambda d, _: d.get("legal_resolution_pct", 100) < 50,
        "category": "Legal",
        "priority": "High",
        "message":  (
            "Legal resolution is only {legal_resolution_pct:.0f}%. "
            "Fast-track dispute resolution through District Legal Services Authority."
        ),
    },

    # ── Compensation ─────────────────────────────────────────

    {
        "id": "CMP-01",
        "trigger":  lambda d, _: d.get("compensation_completion_pct", 100) < 60,
        "category": "Compensation",
        "priority": "High",
        "message":  (
            "Compensation disbursement is only {compensation_completion_pct:.0f}% complete. "
            "Deploy additional disbursement camps and increase staffing."
        ),
    },
    {
        "id": "CMP-02",
        "trigger":  lambda d, _: d.get("compensation_pending_cases", 0) >= 50,
        "category": "Compensation",
        "priority": "High",
        "message":  (
            "{compensation_pending_cases} compensation cases pending. "
            "Prioritise high-value cases and implement bulk processing."
        ),
    },
    {
        "id": "CMP-03",
        "trigger":  lambda d, _: d.get("compensation_delay_days", 0) >= 45,
        "category": "Compensation",
        "priority": "Critical",
        "message":  (
            "Compensation delays of {compensation_delay_days} days are critically high. "
            "Invoke Section 80 of RFCTLARR Act for urgent payment processing."
        ),
    },

    # ── Documentation ────────────────────────────────────────

    {
        "id": "DOC-01",
        "trigger":  lambda d, _: d.get("documentation_completion_pct", 100) < 70,
        "category": "Documentation",
        "priority": "Medium",
        "message":  (
            "Documentation completion is {documentation_completion_pct:.0f}%. "
            "Assign dedicated data-entry teams and set a 30-day completion target."
        ),
    },
    {
        "id": "DOC-02",
        "trigger":  lambda d, _: d.get("missing_documents", 0) >= 10,
        "category": "Documentation",
        "priority": "Medium",
        "message":  (
            "{missing_documents} documents are missing. "
            "Issue notices to landowners and digitise records proactively."
        ),
    },
    {
        "id": "DOC-03",
        "trigger":  lambda d, _: d.get("ownership_verification_pct", 100) < 75,
        "category": "Documentation",
        "priority": "Medium",
        "message":  (
            "Ownership verification is only {ownership_verification_pct:.0f}%. "
            "Set up land record reconciliation camp with the local Tehsil office."
        ),
    },
    {
        "id": "DOC-04",
        "trigger":  lambda d, _: d.get("survey_completion_pct", 100) < 80,
        "category": "Documentation",
        "priority": "Medium",
        "message":  (
            "Survey progress is at {survey_completion_pct:.0f}%. "
            "Deploy drone survey teams to accelerate boundary demarcation."
        ),
    },

    # ── R&R (Resettlement & Rehabilitation) ──────────────────

    {
        "id": "RR-01",
        "trigger":  lambda d, _: d.get("rr_progress_pct", 100) < 40,
        "category": "R&R",
        "priority": "High",
        "message":  (
            "R&R progress is critically low at {rr_progress_pct:.0f}%. "
            "Convene a special R&R monitoring committee and set monthly milestones."
        ),
    },
    {
        "id": "RR-02",
        "trigger":  lambda d, _: d.get("rr_pending_cases", 0) >= 30,
        "category": "R&R",
        "priority": "High",
        "message":  (
            "{rr_pending_cases} R&R cases pending. "
            "Engage NGOs and social workers to accelerate family-level processing."
        ),
    },
    {
        "id": "RR-03",
        "trigger":  lambda d, _: d.get("stakeholder_responsiveness", 100) < 50,
        "category": "R&R",
        "priority": "Medium",
        "message":  (
            "Stakeholder responsiveness score is {stakeholder_responsiveness:.0f}/100. "
            "Conduct community consultation meetings and address grievances publicly."
        ),
    },

    # ── Possession & Handover ────────────────────────────────

    {
        "id": "POS-01",
        "trigger":  lambda d, _: d.get("possession_progress_pct", 100) < 30,
        "category": "Possession",
        "priority": "High",
        "message":  (
            "Possession progress is only {possession_progress_pct:.0f}%. "
            "Coordinate with district administration for physical possession drive."
        ),
    },
    {
        "id": "POS-02",
        "trigger":  lambda d, _: d.get("handover_progress_pct", 100) < 20,
        "category": "Possession",
        "priority": "High",
        "message":  (
            "Handover progress is {handover_progress_pct:.0f}%. "
            "Schedule a joint handover inspection with the executing agency within 2 weeks."
        ),
    },

    # ── Historical / Predictive ──────────────────────────────

    {
        "id": "HIS-01",
        "trigger":  lambda d, _: d.get("historical_district_delay_rate", 0) >= 0.60,
        "category": "Historical",
        "priority": "Medium",
        "message":  (
            "This district has a historical delay rate of "
            "{historical_district_delay_rate:.0%}. "
            "Proactively assign a district-level project monitor."
        ),
    },
    {
        "id": "HIS-02",
        "trigger":  lambda d, _: d.get("historical_agency_delay_rate", 0) >= 0.60,
        "category": "Historical",
        "priority": "Medium",
        "message":  (
            "The executing agency has a historical delay rate of "
            "{historical_agency_delay_rate:.0%}. "
            "Conduct a performance review and set strict milestone accountability."
        ),
    },
    {
        "id": "HIS-03",
        "trigger":  lambda d, _: (
            d.get("elapsed_acquisition_days", 0) /
            max(d.get("planned_acquisition_days", 1), 1)
        ) > 0.80 and d.get("days_remaining_to_target", 1) < 90,
        "category": "Historical",
        "priority": "Critical",
        "message":  (
            "Project has consumed over 80% of planned timeline with only "
            "{days_remaining_to_target:.0f} days remaining. "
            "Activate emergency intervention protocol."
        ),
    },
]

_PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


# ============================================================
# CORE FUNCTION (importable directly)
# ============================================================

def generate_recommendations(
    data: Dict[str, Any],
    explain_result: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Evaluate all rules against data and return sorted recommendations.

    Parameters
    ----------
    data           : dict   raw project feature values
    explain_result : dict   optional output from explain_prediction()

    Returns
    -------
    list of {"id": str, "category": str, "priority": str, "message": str}
    sorted Critical -> High -> Medium -> Low
    """
    if explain_result is None:
        explain_result = {}

    triggered: List[Dict[str, Any]] = []

    for rule in _RULES:
        try:
            if rule["trigger"](data, explain_result):
                try:
                    msg = rule["message"].format(**data)
                except (KeyError, ValueError):
                    msg = rule["message"]

                triggered.append({
                    "id":       rule.get("id"),
                    "category": rule["category"],
                    "priority": rule["priority"],
                    "message":  msg,
                })
        except Exception:
            continue

    triggered.sort(key=lambda r: _PRIORITY_ORDER.get(r["priority"], 99))
    return triggered


# ============================================================
# FASTAPI ROUTER
# ============================================================

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"],
)


# ── Input schema ─────────────────────────────────────────────

class RecommendInput(BaseModel):
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
    include_prediction: bool = True


# ── Endpoints ────────────────────────────────────────────────

@router.post("")
def get_recommendations(project: RecommendInput):
    """
    Generate priority-sorted actionable recommendations for a project.
    Also returns the ML prediction summary when include_prediction=True.
    """
    try:
        data = project.model_dump(exclude={"include_prediction"})

        explain_result = {}
        prediction_summary = None

        if project.include_prediction:
            try:
                explain_result = explain_prediction(data)
                prediction_summary = {
                    "delay_probability":    explain_result["delay_probability"],
                    "risk_category":        explain_result["risk_category"],
                    "predicted_delay_days": explain_result["predicted_delay_days"],
                }
            except Exception:
                pass  # recommendations still work without prediction

        recs = generate_recommendations(data, explain_result)

        return {
            "success":               True,
            "total_recommendations": len(recs),
            "prediction":            prediction_summary,
            "recommendations":       recs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
def get_recommendation_rules():
    """Return all available recommendation rules and categories."""
    return {
        "success": True,
        "total_rules": len(_RULES),
        "rules": [
            {
                "id": r.get("id"),
                "category": r["category"],
                "priority": r["priority"],
                "template": r["message"],
            }
            for r in _RULES
        ]
    }


# ============================================================
# STANDALONE EXECUTION / DEMO
# ============================================================

if __name__ == "__main__":
    import os
    import sys

    _CUR = os.path.dirname(os.path.abspath(__file__))
    _ROOT = os.path.dirname(_CUR)
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

    info = get_model_info()
    print("Model:", info["classifier"], "+", info["regressor"])
    print("SHAP:", info["shap_available"])
    print("Features:", info["number_of_features"])

    print("\nTop 5 features (classifier):")
    for f in get_feature_importance()[:5]:
        print("  {}: {}".format(f["feature"], f["importance"]))

    sample = {
        "project_type": "Highway", "state": "Maharashtra", "district": "Pune",
        "land_area_acres": 350.5, "affected_families": 420, "current_stage": "Award",
        "pending_approvals": 4, "approval_delay_days": 45, "pending_notifications": 2,
        "administrative_bottleneck": "Yes", "coordination_delay_days": 30,
        "legal_disputes": 1, "ownership_conflicts": "Yes", "court_cases_pending": 1,
        "legal_resolution_pct": 55.0, "compensation_completion_pct": 40.0,
        "compensation_pending_cases": 120, "compensation_delay_days": 60,
        "documentation_completion_pct": 65.0, "missing_documents": 18,
        "ownership_verification_pct": 70.0, "survey_completion_pct": 80.0,
        "rr_progress_pct": 30.0, "rr_pending_cases": 55,
        "stakeholder_responsiveness": 40.0, "possession_progress_pct": 20.0,
        "handover_progress_pct": 15.0, "historical_district_delay_rate": 0.72,
        "historical_agency_delay_rate": 0.65, "similar_project_avg_delay_days": 180,
        "planned_acquisition_days": 365, "elapsed_acquisition_days": 280,
        "days_remaining_to_target": 85,
    }

    result = explain_prediction(sample)
    print("\nDelay probability : {:.2%}".format(result["delay_probability"]))
    print("Risk category     : {}".format(result["risk_category"]))
    print("Predicted delay   : {} days".format(result["predicted_delay_days"]))
    if result["classifier_factors"]:
        print("\nTop SHAP factors:")
        for f in result["classifier_factors"][:5]:
            print("  {}: {} ({})".format(f["feature"], f["shap_value"], f["impact"]))
    else:
        print("\n(SHAP factors not available)")

    print("\nActionable Recommendations:")
    recs = generate_recommendations(sample, result)
    for r in recs[:5]:
        print("  [{}] {}: {}".format(r["priority"], r["category"], r["message"]))
