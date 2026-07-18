"""
Reusable FastAPI dependencies.

`get_current_user` is how every protected endpoint gets "who is calling?". It
reads the bearer token, verifies it, loads the user, and raises 401 if anything
is wrong. Endpoints just declare `user: User = Depends(get_current_user)` and
never touch tokens themselves.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# auto_error=False so we can return a clean 401 instead of FastAPI's default.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise _unauthorized("Missing authentication token")

    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise _unauthorized("Invalid or expired token")

    user = (
        await db.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if user is None:
        # Token is well-formed but the user no longer exists -> treat as auth
        # failure (401), not "not found" (404). 401 tells the client to log in.
        raise _unauthorized("User no longer exists")
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
