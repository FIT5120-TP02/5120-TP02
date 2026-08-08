"""
User preference endpoints - "Users can only access their own data"
(Security Plan). Every route here is scoped to the authenticated user
via get_current_user, never by an id passed in the URL/body.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/me/preferences", response_model=schemas.PreferenceOut)
def upsert_preferences(
    payload: schemas.PreferenceIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    pref = (
        db.query(models.Preference)
        .filter(models.Preference.user_id == current_user.user_id)
        .first()
    )
    if pref is None:
        pref = models.Preference(user_id=current_user.user_id)
        db.add(pref)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)

    db.commit()
    db.refresh(pref)
    return pref


@router.get("/me/preferences", response_model=schemas.PreferenceOut)
def read_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    pref = (
        db.query(models.Preference)
        .filter(models.Preference.user_id == current_user.user_id)
        .first()
    )
    if pref is None:
        # Sensible defaults so the frontend Settings screen has something to
        # render on first login. Persisted immediately so it has a real id
        # and future GET/PUT calls hit the same row.
        pref = models.Preference(
            user_id=current_user.user_id,
            noise_tolerance=0.5,
            light_tolerance=0.5,
            crowd_tolerance=0.5,
            preferred_route_type="balanced",
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref
