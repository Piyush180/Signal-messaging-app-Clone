from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class RequestOTPRequest(BaseModel):
    phone_number: str = Field(..., examples=["+15551234567"])


class RequestOTPResponse(BaseModel):
    message: str
    phone_number: str
    # Only returned because this is a demo with a mocked OTP. A real app would
    # never send the code back to the client.
    otp_demo: str


class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., examples=["+15551234567"])
    code: str = Field(..., examples=["123456"])
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
