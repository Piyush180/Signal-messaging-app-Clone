from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserResponse


class ContactCreate(BaseModel):
    phone_number: str
    nickname: Optional[str] = None


class ContactResponse(BaseModel):
    id: int
    user_id: int
    contact_user: UserResponse
    nickname: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
