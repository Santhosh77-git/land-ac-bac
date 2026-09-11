# app.py

import os
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
# CORS (Configured for Vercel Frontend & Local Development)
# ============================================================

allowed_origins = [
    "https://land-ac.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

env_frontend = os.environ.get("FRONTEND_URL")
if env_frontend and env_frontend not in allowed_origins:
    allowed_origins.append(env_frontend)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(prediction_router)
app.include_router(projects_router)
app.include_router(stage_risk_router)
app.include_router(explanation_router)
app.include_router(recommendations_router)


# ============================================================
# ROOT & HEALTH CHECK (For Render Service Monitoring)
# ============================================================

@app.get("/")
def root():
    return {
        "project": "SIH 26017",
        "system": "Land Acquisition Early Warning System",
        "status": "online",
        "frontend": "https://land-ac.vercel.app"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "uptime": "ok"
    }