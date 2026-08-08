"""
Password hashing + JWT issuing/verification.

Security Plan requirements this satisfies:
- "Passwords hashed" -> bcrypt (used directly, not via passlib - passlib's
  bcrypt version-detection shim is incompatible with modern bcrypt releases
  and throws a misleading "password cannot be longer than 72 bytes" error
  even for short passwords; calling bcrypt directly avoids that entirely).
- "Users can only access their own data" -> get_current_user dependency below,
  used by any router that returns user-specific data (preferences, saved routes).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# bcrypt only looks at the first 72 bytes of a password and raises ValueError
# on anything longer (since bcrypt 4.1). We used to truncate silently here,
# but that means two different long passwords sharing the same first 72
# bytes would hash identically and authenticate as each other - a real
# password-collision bug. Reject instead of truncating.
_BCRYPT_MAX_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised instead of silently truncating a password over bcrypt's 72-byte limit."""


def _encode_and_validate(password: str) -> bytes:
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > _BCRYPT_MAX_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {_BCRYPT_MAX_BYTES} bytes when UTF-8 encoded."
        )
    return pw_bytes


def hash_password(password: str) -> str:
    pw_bytes = _encode_and_validate(password)
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = _encode_and_validate(plain_password)
    return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception from None
        return user_id
    except JWTError:
        raise credentials_exception from None


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    user_id = decode_access_token(token)
    user = db.get(models.User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
