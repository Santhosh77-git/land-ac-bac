from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# ============================================================
# CONFIGURATION
# ============================================================

SECRET_KEY = "SIH26017-DEMO-SECRET-CHANGE-BEFORE-PRODUCTION"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60


# ============================================================
# DEMO USERS
# ============================================================

DEMO_USERS = {
    "admin": {
        "password": "admin123",
        "name": "System Administrator",
        "role": "Admin"
    },
    "stateofficer": {
        "password": "state123",
        "name": "State Officer",
        "role": "State Officer"
    },
    "districtofficer": {
        "password": "district123",
        "name": "District Officer",
        "role": "District Officer"
    },
    "projectmanager": {
        "password": "project123",
        "name": "Project Manager",
        "role": "Project Manager"
    }
}


# ============================================================
# REQUEST MODEL
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
# TOKEN
# ============================================================

def create_access_token(
    username: str,
    role: str
):
    expire = (
        datetime.utcnow()
        + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": username,
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# ============================================================
# POST /auth/login
# ============================================================

@router.post("/login")
def login(credentials: LoginRequest):

    username = credentials.username.strip()

    user = DEMO_USERS.get(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    if credentials.password != user["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    access_token = create_access_token(
        username=username,
        role=user["role"]
    )

    return {
        "success": True,
        "message": "Login successful.",

        "access_token": access_token,
        "token_type": "bearer",

        "user": {
            "username": username,
            "name": user["name"],
            "role": user["role"]
        },

        # Compatibility with current React App.jsx
        "username": username,
        "name": user["name"],
        "role": user["role"]
    }
