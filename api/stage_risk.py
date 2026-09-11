# api/stage_risk.py

from fastapi import APIRouter, HTTPException

from api.projects import projects_store


router = APIRouter(
    prefix="/projects",
    tags=["Stage Risk"]
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clamp(value: float, minimum=0, maximum=100):
    """
    Keep a score between 0 and 100.
    """
    return max(
        minimum,
        min(maximum, value)
    )


def inverse_percentage(value: float):
    """
    Convert a progress percentage into a risk component.

    Example:
    90% completion -> 10 risk
    40% completion -> 60 risk
    """
    return 100 - value


def calculate_stage_risks(project):
    """
    Calculate stage-wise risk based on the project's
    current operational indicators.

    This is a transparent prototype stage-risk engine.
    """

    # ========================================================
    # ADMINISTRATIVE RISK
    # ========================================================

    administrative_risk = (
        0.25 * min(
            project["pending_approvals"] * 10,
            100
        )
        +
        0.25 * min(
            project["approval_delay_days"] * 1.5,
            100
        )
        +
        0.15 * min(
            project["pending_notifications"] * 15,
            100
        )
        +
        0.20 * project[
            "administrative_bottleneck_score"
        ]
        if "administrative_bottleneck_score" in project
        else 0
    )

    # If only the categorical field exists, use a mapping.
    if "administrative_bottleneck_score" not in project:

        admin_mapping = {
            "Low": 20,
            "Medium": 45,
            "High": 70,
            "Critical": 90
        }

        admin_score = admin_mapping.get(
            project["administrative_bottleneck"],
            50
        )

        administrative_risk = (
            0.30 * min(
                project["pending_approvals"] * 10,
                100
            )
            +
            0.25 * min(
                project["approval_delay_days"] * 1.5,
                100
            )
            +
            0.15 * min(
                project["pending_notifications"] * 15,
                100
            )
            +
            0.20 * admin_score
            +
            0.10 * min(
                project["coordination_delay_days"] * 2,
                100
            )
        )

    administrative_risk = clamp(
        administrative_risk
    )

    # ========================================================
    # LEGAL RISK
    # ========================================================

    ownership_mapping = {
        "None": 0,
        "Low": 25,
        "Medium": 55,
        "High": 90
    }

    ownership_risk = ownership_mapping.get(
        project["ownership_conflicts"],
        50
    )

    legal_risk = (
        0.30 * min(
            project["legal_disputes"] * 8,
            100
        )
        +
        0.20 * min(
            project["court_cases_pending"] * 12,
            100
        )
        +
        0.20 * ownership_risk
        +
        0.30 * inverse_percentage(
            project["legal_resolution_pct"]
        )
    )

    legal_risk = clamp(
        legal_risk
    )

    # ========================================================
    # COMPENSATION RISK
    # ========================================================

    compensation_risk = (
        0.40 * inverse_percentage(
            project["compensation_completion_pct"]
        )
        +
        0.20 * min(
            project["compensation_pending_cases"] * 2,
            100
        )
        +
        0.20 * min(
            project["compensation_delay_days"] * 1.5,
            100
        )
        +
        0.20 * min(
            project["affected_families"] / 2,
            100
        )
    )

    compensation_risk = clamp(
        compensation_risk
    )

    # ========================================================
    # R&R RISK
    # ========================================================

    rr_risk = (
        0.55 * inverse_percentage(
            project["rr_progress_pct"]
        )
        +
        0.30 * min(
            project["rr_pending_cases"] * 3,
            100
        )
        +
        0.15 * (
            100
            if project["rr_progress_pct"] < 30
            else 50
            if project["rr_progress_pct"] < 60
            else 10
        )
    )

    rr_risk = clamp(
        rr_risk
    )

    # ========================================================
    # POSSESSION RISK
    # ========================================================

    possession_risk = (
        0.35 * inverse_percentage(
            project["possession_progress_pct"]
        )
        +
        0.25 * inverse_percentage(
            project["handover_progress_pct"]
        )
        +
        0.20 * inverse_percentage(
            project["compensation_completion_pct"]
        )
        +
        0.10 * inverse_percentage(
            project["documentation_completion_pct"]
        )
        +
        0.10 * inverse_percentage(
            project["legal_resolution_pct"]
        )
    )

    possession_risk = clamp(
        possession_risk
    )

    return {
        "administrative": round(
            administrative_risk
        ),
        "legal": round(
            legal_risk
        ),
        "compensation": round(
            compensation_risk
        ),
        "rr": round(
            rr_risk
        ),
        "possession": round(
            possession_risk
        )
    }


# ============================================================
# GET /projects/{project_id}/stage-risk
# ============================================================

@router.get("/{project_id}/stage-risk")
def get_stage_risk(
    project_id: str
):

    project = projects_store.get(
        project_id
    )

    if not project:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )

    # Calculate stage risks
    stage_risk = calculate_stage_risks(
        project
    )

    # Find highest-risk stage
    highest_stage = max(
        stage_risk,
        key=stage_risk.get
    )

    highest_score = stage_risk[
        highest_stage
    ]

    # Human-readable stage name
    stage_names = {
        "administrative": "Administrative",
        "legal": "Legal / Objection",
        "compensation": "Compensation",
        "rr": "Rehabilitation & Resettlement",
        "possession": "Possession / Handover"
    }

    return {
        "success": True,

        "project_id": project_id,

        "current_stage": project[
            "current_stage"
        ],

        "stage_risk": stage_risk,

        "highest_risk_stage": {
            "stage": stage_names[
                highest_stage
            ],
            "risk_score": highest_score
        }
    }# api/stage_risk.py

from fastapi import APIRouter, HTTPException

from api.projects import projects_store


router = APIRouter(
    prefix="/projects",
    tags=["Stage Risk"]
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clamp(value: float, minimum=0, maximum=100):
    """
    Keep a score between 0 and 100.
    """
    return max(
        minimum,
        min(maximum, value)
    )


def inverse_percentage(value: float):
    """
    Convert a progress percentage into a risk component.

    Example:
    90% completion -> 10 risk
    40% completion -> 60 risk
    """
    return 100 - value


def calculate_stage_risks(project):
    """
    Calculate stage-wise risk based on the project's
    current operational indicators.

    This is a transparent prototype stage-risk engine.
    """

    # ========================================================
    # ADMINISTRATIVE RISK
    # ========================================================

    administrative_risk = (
        0.25 * min(
            project["pending_approvals"] * 10,
            100
        )
        +
        0.25 * min(
            project["approval_delay_days"] * 1.5,
            100
        )
        +
        0.15 * min(
            project["pending_notifications"] * 15,
            100
        )
        +
        0.20 * project[
            "administrative_bottleneck_score"
        ]
        if "administrative_bottleneck_score" in project
        else 0
    )

    # If only the categorical field exists, use a mapping.
    if "administrative_bottleneck_score" not in project:

        admin_mapping = {
            "Low": 20,
            "Medium": 45,
            "High": 70,
            "Critical": 90
        }

        admin_score = admin_mapping.get(
            project["administrative_bottleneck"],
            50
        )

        administrative_risk = (
            0.30 * min(
                project["pending_approvals"] * 10,
                100
            )
            +
            0.25 * min(
                project["approval_delay_days"] * 1.5,
                100
            )
            +
            0.15 * min(
                project["pending_notifications"] * 15,
                100
            )
            +
            0.20 * admin_score
            +
            0.10 * min(
                project["coordination_delay_days"] * 2,
                100
            )
        )

    administrative_risk = clamp(
        administrative_risk
    )

    # ========================================================
    # LEGAL RISK
    # ========================================================

    ownership_mapping = {
        "None": 0,
        "Low": 25,
        "Medium": 55,
        "High": 90
    }

    ownership_risk = ownership_mapping.get(
        project["ownership_conflicts"],
        50
    )

    legal_risk = (
        0.30 * min(
            project["legal_disputes"] * 8,
            100
        )
        +
        0.20 * min(
            project["court_cases_pending"] * 12,
            100
        )
        +
        0.20 * ownership_risk
        +
        0.30 * inverse_percentage(
            project["legal_resolution_pct"]
        )
    )

    legal_risk = clamp(
        legal_risk
    )

    # ========================================================
    # COMPENSATION RISK
    # ========================================================

    compensation_risk = (
        0.40 * inverse_percentage(
            project["compensation_completion_pct"]
        )
        +
        0.20 * min(
            project["compensation_pending_cases"] * 2,
            100
        )
        +
        0.20 * min(
            project["compensation_delay_days"] * 1.5,
            100
        )
        +
        0.20 * min(
            project["affected_families"] / 2,
            100
        )
    )

    compensation_risk = clamp(
        compensation_risk
    )

    # ========================================================
    # R&R RISK
    # ========================================================

    rr_risk = (
        0.55 * inverse_percentage(
            project["rr_progress_pct"]
        )
        +
        0.30 * min(
            project["rr_pending_cases"] * 3,
            100
        )
        +
        0.15 * (
            100
            if project["rr_progress_pct"] < 30
            else 50
            if project["rr_progress_pct"] < 60
            else 10
        )
    )

    rr_risk = clamp(
        rr_risk
    )

    # ========================================================
    # POSSESSION RISK
    # ========================================================

    possession_risk = (
        0.35 * inverse_percentage(
            project["possession_progress_pct"]
        )
        +
        0.25 * inverse_percentage(
            project["handover_progress_pct"]
        )
        +
        0.20 * inverse_percentage(
            project["compensation_completion_pct"]
        )
        +
        0.10 * inverse_percentage(
            project["documentation_completion_pct"]
        )
        +
        0.10 * inverse_percentage(
            project["legal_resolution_pct"]
        )
    )

    possession_risk = clamp(
        possession_risk
    )

    return {
        "administrative": round(
            administrative_risk
        ),
        "legal": round(
            legal_risk
        ),
        "compensation": round(
            compensation_risk
        ),
        "rr": round(
            rr_risk
        ),
        "possession": round(
            possession_risk
        )
    }


# ============================================================
# GET /projects/{project_id}/stage-risk
# ============================================================

@router.get("/{project_id}/stage-risk")
def get_stage_risk(
    project_id: str
):

    project = projects_store.get(
        project_id
    )

    if not project:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )

    # Calculate stage risks
    stage_risk = calculate_stage_risks(
        project
    )

    # Find highest-risk stage
    highest_stage = max(
        stage_risk,
        key=stage_risk.get
    )

    highest_score = stage_risk[
        highest_stage
    ]

    # Human-readable stage name
    stage_names = {
        "administrative": "Administrative",
        "legal": "Legal / Objection",
        "compensation": "Compensation",
        "rr": "Rehabilitation & Resettlement",
        "possession": "Possession / Handover"
    }

    return {
        "success": True,

        "project_id": project_id,

        "current_stage": project[
            "current_stage"
        ],

        "stage_risk": stage_risk,

        "highest_risk_stage": {
            "stage": stage_names[
                highest_stage
            ],
            "risk_score": highest_score
        }
    }