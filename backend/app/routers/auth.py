"""
Authentication endpoints.

Register / login only - no OAuth/social login for the onboarding scope.
Passwords are hashed with bcrypt before storage (Security Plan requirement).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import (
    PasswordTooLongError,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = models.User(username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise invalid_credentials

    try:
        password_ok = verify_password(form_data.password, user.hashed_password)
    except PasswordTooLongError:
        # login form isn't covered by UserCreate's length validator - an
        # over-length password here just means "wrong password", not a 500.
        password_ok = False

    if not password_ok:
        raise invalid_credentials

    token = create_access_token(subject=str(user.user_id))
    return schemas.Token(access_token=token)
