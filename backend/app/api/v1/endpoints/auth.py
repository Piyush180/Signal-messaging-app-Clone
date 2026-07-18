"""
Authentication endpoints: request an OTP, verify it (which also registers a new
user on first login), fetch the current user, and log out.

The flow is mocked per the assignment: the OTP is always the fixed demo code.
But we still store and verify it against expiry + a used-flag, so the shape
matches a real SMS OTP flow.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, generate_mock_otp
from app.models.common import utcnow
from app.models.otp import OTPCode
from app.models.user import User
from app.schemas.auth import (
    RequestOTPRequest,
    RequestOTPResponse,
    TokenResponse,
    VerifyOTPRequest,
)
from app.schemas.user import UserResponse

router = APIRouter()


@router.post("/request-otp", response_model=RequestOTPResponse)
async def request_otp(payload: RequestOTPRequest, db: AsyncSession = Depends(get_db)):
    phone = payload.phone_number.strip()
    if len(phone) < 7:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid phone number.")

    code = generate_mock_otp()
    db.add(
        OTPCode(
            phone_number=phone,
            code=code,
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    await db.commit()
    return RequestOTPResponse(
        message="OTP sent. For this demo use the code below.",
        phone_number=phone,
        otp_demo=code,
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(payload: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    phone = payload.phone_number.strip()
    code = payload.code.strip()

    otp = (
        await db.execute(
            select(OTPCode)
            .where(
                OTPCode.phone_number == phone,
                OTPCode.code == code,
                OTPCode.is_used.is_(False),
                OTPCode.expires_at > utcnow(),
            )
            .order_by(OTPCode.id.desc())
        )
    ).scalars().first()

    if not otp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code.")

    otp.is_used = True

    user = (
        await db.execute(select(User).where(User.phone_number == phone))
    ).scalar_one_or_none()

    if user is None:
        # First successful verification for this number => register.
        user = User(
            phone_number=phone,
            full_name=payload.full_name or f"User {phone[-4:]}",
            avatar_url=None,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(_: User = Depends(get_current_user)):
    # Tokens are stateless (JWT), so "logout" is a client-side token discard.
    # We keep the endpoint for symmetry and future token-blacklist support.
    return {"message": "Logged out"}
