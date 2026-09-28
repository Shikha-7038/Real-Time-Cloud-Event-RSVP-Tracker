"""auth.py - /api/register, /api/login, /api/logout"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.security import hash_password, verify_password, issue_token, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user_id = f"usr_{uuid.uuid4().hex}"
    user = User(user_id=user_id, name=payload.name, email=payload.email,
                password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()

    token = issue_token(user_id, payload.role)
    return {"token": token, "user": user}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        # Generic message for both "no such user" and "wrong password".
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = issue_token(user.user_id, user.role)
    return {"token": token, "user": user}


@router.post("/logout")
def logout(user=Depends(get_current_user)):
    # Stateless JWT - logout is client-side token discard. For server-side
    # revocation in production, maintain a short-lived token blacklist.
    return {"message": "Logged out. Discard the token client-side."}
