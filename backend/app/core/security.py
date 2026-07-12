from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from backend.app.core.config import settings


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Convert a plain password into a secure hash."""

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check whether a password matches its stored hash."""

    return password_hasher.verify(password, password_hash)


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    role: str,
) -> str:
    """Create a signed JWT access token."""

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "organization_id": organization_id,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )