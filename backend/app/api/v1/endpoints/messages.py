"""
Message history + a REST send endpoint.

The REST send is a FALLBACK for when the WebSocket is momentarily down. It calls
the exact same `create_and_broadcast` service as the socket handler, so a
message sent over HTTP is persisted, bumps the conversation, and is pushed to
the other members' sockets — identical behaviour, no matter the transport.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.message import MessageCreate, MessagePage, MessageResponse
from app.services import messages as msg_service

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/messages", response_model=MessagePage
)
async def get_messages(
    conversation_id: int,
    limit: int = Query(30, ge=1, le=100),
    before_id: Optional[int] = Query(None, description="Return messages older than this id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await msg_service.is_member(db, conversation_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this conversation.")
    messages, has_more, next_cursor = await msg_service.get_history(
        db, conversation_id, user.id, limit=limit, before_id=before_id
    )
    return MessagePage(messages=messages, has_more=has_more, next_cursor=next_cursor)


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
async def send_message(
    conversation_id: int,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message cannot be empty.")
    if not await msg_service.is_member(db, conversation_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this conversation.")
    try:
        return await msg_service.create_and_broadcast(
            db,
            conversation_id=conversation_id,
            sender_id=user.id,
            content=content,
            message_type="text",
            client_id=payload.client_id,
            reply_to_id=payload.reply_to_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
