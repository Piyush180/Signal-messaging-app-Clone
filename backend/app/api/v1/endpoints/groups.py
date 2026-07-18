"""
Group admin endpoints: add and remove members.

Only a group admin may add or remove members. The `_require_admin` check lives
in the conversation service so both the REST layer here and any future callers
enforce the same rule.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.conversation import ConversationResponse, GroupMemberAdd
from app.services import conversations as conv_service

router = APIRouter()


@router.post("/{conversation_id}/members", response_model=ConversationResponse)
async def add_group_members(
    conversation_id: int,
    payload: GroupMemberAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.add_members(db, conversation_id, user, payload.user_ids)


@router.delete("/{conversation_id}/members/{user_id}", response_model=ConversationResponse)
async def remove_group_member(
    conversation_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.remove_member(db, conversation_id, user, user_id)
