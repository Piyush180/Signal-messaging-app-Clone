"""
Security helpers: JWT creation/verification and the mock OTP.

We deliberately keep this tiny. There are no passwords in this app (auth is a
mocked phone + OTP flow per the assignment), so there is no password hashing
library here. Adding one would be dead code.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import jwt

from app.core.config import settings


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Return a signed JWT whose `sub` claim is the user id."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Return the JWT payload, or None if the token is invalid/expired."""
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except jwt.PyJWTError:
        return None


def generate_mock_otp() -> str:
    """Assignment allows a fixed OTP. Kept in one place so it is easy to find."""
    return settings.MOCK_OTP_CODE
