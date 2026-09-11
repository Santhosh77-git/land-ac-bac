# api/projects.py

from datetime import datetime
from typing import Optional
import uuid
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)


# ============================================================
# IN-MEMORY STORAGE
# ============================================================
# Temporary storage for SIH prototype.
#
# IMPORTANT:
# Data will disappear whenever the server restarts.
# Later this dictionary can be replaced with PostgreSQL
# without changing the API structure.
# ============================================================

projects_store = {}


# ============================================================
# PROJECT INPUT SCHEMA
# ============================================================

class ProjectCreate(BaseModel):

    project_id: Optional[str] = None
    project_name: str = Field(
        min_length=1,
        max_length=255
    )

    # --------------------------------------------------------
    # Core project
    # --------------------------------------------------------

    project_type: str
    state: str
    district: str

    land_area_acres: float = Field(gt=0)
    affected_families: int = Field(ge=0)

    current_stage: str

    # --------------------------------------------------------
    # Administrative
    # --------------------------------------------------------

    pending_approvals: int = Field(ge=0)
    approval_delay_days: float = Field(ge=0)
    pending_notifications: int = Field(ge=0)

    administrative_bottleneck: str

    coordination_delay_days: float = Field(
        ge=0
    )

    # --------------------------------------------------------
    # Legal
    # --------------------------------------------------------

    legal_disputes: int = Field(ge=0)

    ownership_conflicts: str

    court_cases_pending: int = Field(
        ge=0
    )

    legal_resolution_pct: float = Field(
        ge=0,
        le=100
    )

    # --------------------------------------------------------
    # Compensation
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Documentation
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # R&R
    # --------------------------------------------------------

    rr_progress_pct: float = Field(
        ge=0,
        le=100
    )

    rr_pending_cases: int = Field(
        ge=0
    )

    # --------------------------------------------------------
    # Stakeholder
    # --------------------------------------------------------

    stakeholder_responsiveness: float = Field(
        ge=0,
        le=100
    )

    # --------------------------------------------------------
    # Possession / Handover
    # --------------------------------------------------------

    possession_progress_pct: float = Field(
        ge=0,
        le=100
    )

    handover_progress_pct: float = Field(
        ge=0,
        le=100
    )

    # --------------------------------------------------------
    # Historical performance
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Schedule
    # --------------------------------------------------------

    planned_acquisition_days: float = Field(
        gt=0
    )

    elapsed_acquisition_days: float = Field(
        ge=0
    )

    days_remaining_to_target: float = Field(
        ge=0
    )

    # --------------------------------------------------------
    # GIS
    # --------------------------------------------------------

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # --------------------------------------------------------
    # Additional context
    # --------------------------------------------------------

    land_environment: Optional[str] = None
    rural_urban: Optional[str] = None


# ============================================================
# GENERATE PROJECT ID
# ============================================================

def generate_project_id():
    """
    Generate a unique project ID.

    Example:
    LA-3F8A21
    """

    while True:

        short_uuid = uuid.uuid4().hex[:6].upper()

        project_id = f"LA-{short_uuid}"

        if project_id not in projects_store:
            return project_id


# ============================================================
# POST /projects
# ============================================================

@router.post("")
def create_project(
    project: ProjectCreate
):

    data = project.model_dump()

    # --------------------------------------------------------
    # Generate project ID if frontend didn't provide one
    # --------------------------------------------------------

    if not data.get("project_id"):

        data["project_id"] = (
            generate_project_id()
        )

    # --------------------------------------------------------
    # Check duplicate ID
    # --------------------------------------------------------

    if data["project_id"] in projects_store:

        raise HTTPException(
            status_code=409,
            detail="Project ID already exists."
        )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    now = datetime.utcnow()

    data["created_at"] = now.isoformat()
    data["updated_at"] = now.isoformat()

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    projects_store[
        data["project_id"]
    ] = data

    return {
        "success": True,
        "message": "Project created successfully.",
        "project": data
    }


# ============================================================
# GET /projects
# ============================================================

@router.get("")
def get_projects(
    state: Optional[str] = Query(
        default=None
    ),
    district: Optional[str] = Query(
        default=None
    ),
    project_type: Optional[str] = Query(
        default=None
    ),
    current_stage: Optional[str] = Query(
        default=None
    ),
    risk_level: Optional[str] = Query(
        default=None
    )
):

    projects = list(
        projects_store.values()
    )

    # --------------------------------------------------------
    # Apply filters
    # --------------------------------------------------------

    if state:

        projects = [
            p for p in projects
            if p["state"].lower()
            == state.lower()
        ]

    if district:

        projects = [
            p for p in projects
            if p["district"].lower()
            == district.lower()
        ]

    if project_type:

        projects = [
            p for p in projects
            if p["project_type"].lower()
            == project_type.lower()
        ]

    if current_stage:

        projects = [
            p for p in projects
            if p["current_stage"].lower()
            == current_stage.lower()
        ]

    # --------------------------------------------------------
    # Risk filter
    #
    # Currently projects may not have risk information
    # until prediction is performed.
    # This filter becomes fully active once risk results
    # are attached to projects.
    # --------------------------------------------------------

    if risk_level:

        projects = [
            p for p in projects
            if p.get("risk_level", "").lower()
            == risk_level.lower()
        ]

    return {
        "success": True,
        "count": len(projects),
        "projects": projects
    }


# ============================================================
# GET /projects/{project_id}
# ============================================================

@router.get("/{project_id}")
def get_project(
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

    return {
        "success": True,
        "project": project
    }