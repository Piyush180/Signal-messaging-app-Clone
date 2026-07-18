from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.message import MessageResponse
from app.schemas.user import UserResponse


class GroupMetadataResponse(BaseModel):
    id: int
    conversation_id: int
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    """A conversation member = the user plus their role in this conversation."""

    user: UserResponse
    role: str

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: int
    type: str
    created_at: datetime
    updated_at: datetime
    members: List[MemberResponse]
    group_metadata: Optional[GroupMetadataResponse] = None
    last_message: Optional[MessageResponse] = None
    unread_count: int = 0


class DirectConversationCreate(BaseModel):
    contact_user_id: int


class GroupConversationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    member_user_ids: List[int]


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None


class GroupMemberAdd(BaseModel):
    user_ids: List[int]
