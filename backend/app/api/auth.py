import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.security import create_access_token, get_current_user, hash_password, verify_password
from ..db import models
from ..db.database import get_db
from ..schemas.auth import AuthResponse, LoginRequest, MeResponse, SignupRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Un compte existe déjà pour cet email.")
    user = models.User(
        id=str(uuid.uuid4()),
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.id, "email": user.email})
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides.")
    token = create_access_token({"sub": user.id, "email": user.email})
    return AuthResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_user: models.User = Depends(get_current_user)):
    return MeResponse(id=current_user.id, email=current_user.email)
