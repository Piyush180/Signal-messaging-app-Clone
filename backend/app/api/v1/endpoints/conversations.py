from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationResponse,
    DirectConversationCreate,
    GroupConversationCreate,
)
from app.services import conversations as conv_service

router = APIRouter()


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await conv_service.list_for_user(db, user)


@router.post("/direct", response_model=ConversationResponse)
async def create_direct(
    payload: DirectConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.get_or_create_direct(db, user, payload.contact_user_id)


@router.post("/group", response_model=ConversationResponse)
async def create_group(
    payload: GroupConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.create_group(
        db,
        creator=user,
        name=payload.name,
        member_user_ids=payload.member_user_ids,
        description=payload.description,
        avatar_url=payload.avatar_url,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.get_for_user(db, conversation_id, user)
