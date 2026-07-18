"""
Presence service: keep the `is_online` flag correct and tell the right people
when it changes.

Who needs to know your status? Everyone you share a conversation with, because
they render your online dot. Scoping the broadcast to saved contacts would be
wrong: a chat partner who never added you would see a stale status forever.
"""
from typing import List

from sqlalchemy import distinct, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import utcnow
from app.models.conversation import ConversationMember
from app.models.user import User
from app.websockets.manager import manager


async def _audience(db: AsyncSession, user_id: int) -> List[int]:
    """Distinct users who share at least one conversation with `user_id`."""
    my_convs = select(ConversationMember.conversation_id).where(
        ConversationMember.user_id == user_id
    )
    rows = await db.execute(
        select(distinct(ConversationMember.user_id)).where(
            ConversationMember.conversation_id.in_(my_convs),
            ConversationMember.user_id != user_id,
        )
    )
    return list(rows.scalars().all())


async def set_online(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(User).where(User.id == user_id).values(is_online=True, last_seen=None)
    )
    await db.commit()
    await manager.broadcast(
        await _audience(db, user_id),
        {"type": "presence", "user_id": user_id, "is_online": True, "last_seen": None},
    )


async def set_offline(db: AsyncSession, user_id: int) -> None:
    ts = utcnow()
    await db.execute(
        update(User).where(User.id == user_id).values(is_online=False, last_seen=ts)
    )
    await db.commit()
    await manager.broadcast(
        await _audience(db, user_id),
        {
            "type": "presence",
            "user_id": user_id,
            "is_online": False,
            "last_seen": ts.isoformat(),
        },
    )


async def reset_all_offline(db: AsyncSession) -> None:
    """Run once on startup so a previous crash can't leave users 'online'."""
    await db.execute(update(User).values(is_online=False))
    await db.commit()
