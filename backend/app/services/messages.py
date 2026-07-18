"""
Message service: the single source of truth for creating messages, computing
delivery/read status, and paginating history.

Both the REST endpoint (`POST /messages`) and the WebSocket handler call
`create_and_broadcast` here, so a message behaves identically no matter how it
was sent. Duplicating this logic per transport is how the two paths drift apart
(e.g. an HTTP send that persists but forgets to broadcast).
"""
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.common import utcnow
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message
from app.schemas.message import MessageResponse, QuotedMessage
from app.schemas.user import UserResponse
from app.websockets.manager import manager


# ---------- reads ----------

async def member_ids(db: AsyncSession, conversation_id: int) -> List[int]:
    rows = await db.execute(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id
        )
    )
    return list(rows.scalars().all())


async def is_member(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
    row = await db.execute(
        select(ConversationMember.id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def _members(db: AsyncSession, conversation_id: int) -> List[ConversationMember]:
    rows = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id
        )
    )
    return list(rows.scalars().all())


def _status_for(
    message: Message,
    viewer_id: int,
    members: Sequence[ConversationMember],
) -> str:
    """
    Compute a message's status from the *sender's* point of view.

    Only meaningful for messages the viewer sent. We look at the OTHER members'
    read/delivered pointers and take the weakest one:
      - read      if every other member has read up to this message,
      - delivered if every other member has at least received it,
      - sent      otherwise.
    Incoming messages (viewer is not the sender) just report "read"; the UI only
    draws ticks on outgoing bubbles anyway.
    """
    if message.sender_id != viewer_id:
        return "read"
    others = [m for m in members if m.user_id != viewer_id]
    if not others:
        return "sent"
    if all((m.last_read_message_id or 0) >= message.id for m in others):
        return "read"
    if all((m.last_delivered_message_id or 0) >= message.id for m in others):
        return "delivered"
    return "sent"


def _quote_of(message: Message) -> Optional[QuotedMessage]:
    """Compact preview of the quoted message, or None if this isn't a reply."""
    q = message.reply_to
    if q is None:
        return None
    return QuotedMessage(
        id=q.id,
        sender_id=q.sender_id,
        sender_name=q.sender.full_name or q.sender.phone_number,
        content=q.content,
        message_type=q.message_type,
    )


def to_response(
    message: Message,
    viewer_id: int,
    members: Sequence[ConversationMember],
    client_id: Optional[str] = None,
) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender=UserResponse.model_validate(message.sender),
        content=message.content,
        message_type=message.message_type,
        created_at=message.created_at,
        status=_status_for(message, viewer_id, members),
        client_id=client_id,
        reply_to=_quote_of(message),
    )


async def unread_count(
    db: AsyncSession, conversation_id: int, member: ConversationMember
) -> int:
    """Messages after my last-read pointer that I did not send (system excluded)."""
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != member.user_id,
            Message.message_type != "system",
            Message.id > (member.last_read_message_id or 0),
        )
    )
    return int(result.scalar() or 0)


async def get_history(
    db: AsyncSession,
    conversation_id: int,
    viewer_id: int,
    limit: int = 30,
    before_id: Optional[int] = None,
):
    """
    Cursor pagination. We fetch the NEWEST `limit` messages older than
    `before_id` (descending), then reverse them so the caller gets chronological
    order. Naive `offset/limit` ascending returns the OLDEST page first and
    makes new messages unreachable once a chat outgrows the page size; anchoring
    on the newest and walking backwards by id avoids that entirely.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .options(
            selectinload(Message.sender),
            selectinload(Message.reply_to).selectinload(Message.sender),
        )
        .order_by(Message.id.desc())
        .limit(limit + 1)  # fetch one extra to detect "has_more"
    )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    members = await _members(db, conversation_id)
    messages = [to_response(m, viewer_id, members) for m in reversed(rows)]
    next_cursor = rows[-1].id if (has_more and rows) else None
    return messages, has_more, next_cursor


# ---------- writes ----------

async def create_and_broadcast(
    db: AsyncSession,
    conversation_id: int,
    sender_id: int,
    content: str,
    message_type: str = "text",
    client_id: Optional[str] = None,
    reply_to_id: Optional[int] = None,
) -> MessageResponse:
    """
    Persist a message, update pointers, and push it to every member's sockets.

    All DB writes happen in ONE transaction (a single commit) so a message can
    never be left half-saved: it exists with all its pointer updates, or not at
    all.

    `reply_to_id` is validated here, not trusted from the client: the quoted
    message must exist AND belong to this conversation, otherwise a crafted
    request could quote a message from a chat the sender can't even see.
    """
    members = await _members(db, conversation_id)
    online = set(manager.online_user_ids())

    if reply_to_id is not None:
        quoted = (
            await db.execute(
                select(Message.id).where(
                    Message.id == reply_to_id,
                    Message.conversation_id == conversation_id,
                )
            )
        ).scalar_one_or_none()
        if quoted is None:
            raise ValueError("reply_to_id does not reference a message in this conversation")

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        message_type=message_type,
        reply_to_id=reply_to_id,
    )
    db.add(message)
    await db.flush()  # assigns message.id without ending the transaction

    # Bump the conversation so it floats to the top of the sidebar.
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=utcnow())
    )

    # Pointer updates:
    #  - the sender has, by definition, read their own message,
    #  - any recipient with a live socket is considered "delivered" right now.
    for m in members:
        if m.user_id == sender_id:
            m.last_read_message_id = message.id
            m.last_delivered_message_id = message.id
        elif m.user_id in online:
            m.last_delivered_message_id = message.id

    await db.commit()

    # Reload with sender relationship for serialization.
    message = (
        await db.execute(
            select(Message)
            .where(Message.id == message.id)
            .options(
                selectinload(Message.sender),
                selectinload(Message.reply_to).selectinload(Message.sender),
            )
        )
    ).scalar_one()
    members = await _members(db, conversation_id)

    # Each recipient sees the message as "read" (incoming); the sender sees the
    # true aggregate status. So we serialize per-viewer.
    for m in members:
        payload = to_response(
            message, m.user_id, members, client_id if m.user_id == sender_id else None
        )
        await manager.send_to_user(
            m.user_id, {"type": "new_message", "message": payload.model_dump(mode="json")}
        )

    return to_response(message, sender_id, members, client_id)


async def mark_delivered_up_to_latest(
    db: AsyncSession, conversation_id: int, user_id: int
) -> None:
    """Called when a user's socket connects/opens a chat: mark everything delivered."""
    latest = (
        await db.execute(
            select(func.max(Message.id)).where(
                Message.conversation_id == conversation_id
            )
        )
    ).scalar()
    if latest is None:
        return
    await db.execute(
        update(ConversationMember)
        .where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        .values(last_delivered_message_id=latest)
    )
    await db.commit()


async def mark_read(
    db: AsyncSession, conversation_id: int, reader_id: int
) -> Optional[int]:
    """
    Mark the whole conversation read for `reader_id` and notify the other members
    so senders can flip their ticks to 'read'. Returns the message id read up to.
    """
    latest = (
        await db.execute(
            select(func.max(Message.id)).where(
                Message.conversation_id == conversation_id
            )
        )
    ).scalar()
    if latest is None:
        return None

    await db.execute(
        update(ConversationMember)
        .where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == reader_id,
        )
        .values(last_read_message_id=latest, last_delivered_message_id=latest)
    )
    await db.commit()

    others = [uid for uid in await member_ids(db, conversation_id) if uid != reader_id]
    await manager.broadcast(
        others,
        {
            "type": "read_receipt",
            "conversation_id": conversation_id,
            "reader_id": reader_id,
            "up_to_message_id": latest,
        },
    )
    return latest
