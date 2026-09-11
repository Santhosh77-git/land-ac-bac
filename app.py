# app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.prediction import router as prediction_router
from api.projects import router as projects_router
from api.stage_risk import router as stage_risk_router
from api.explanation import router as explanation_router
from api.recommendations import router as recommendations_router


app = FastAPI(
    title="SIH 26017 - Land Acquisition Risk API",
    description=(
        "AI-powered predictive analytics system for "
        "early detection of land acquisition delays."
    ),
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    prediction_router
)

app.include_router(
    projects_router
)

app.include_router(
    stage_risk_router
)

app.include_router(
    explanation_router
)

app.include_router(
    recommendations_router
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "project": "SIH 26017",
        "system": "Land Acquisition Early Warning System",
        "status": "online"
    }