"""
The single WebSocket endpoint: /ws?token=<jwt>

Design notes:
  - Auth happens once, at connect. A bad/absent token => close with policy code.
  - The receive loop is wrapped so that ANY error (including a malformed frame)
    still runs the cleanup in `finally`. Catching only WebSocketDisconnect is a
    classic leak: any other exception would skip cleanup and leave the user
    stuck "online". Never let cleanup depend on the happy path.
  - Every DB touch uses its own short-lived session (`AsyncSessionLocal`), not a
    request-scoped one, because a socket is long-lived and must not hold a
    session open for its whole lifetime.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.conversation import ConversationMember
from app.models.message import Message
from app.models.user import User
from app.services import messages as msg_service
from app.services import presence as presence_service
from app.websockets.manager import manager

logger = logging.getLogger("ws.endpoint")
router = APIRouter()


async def _authenticate(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    async with AsyncSessionLocal() as db:
        return (
            await db.execute(select(User).where(User.id == int(payload["sub"])))
        ).scalar_one_or_none()


async def _deliver_pending(db: AsyncSession, user_id: int) -> None:
    """On (re)connect, mark everything in the user's chats as delivered and tell
    the senders so their ticks advance from 'sent' to 'delivered'."""
    conv_ids = (
        await db.execute(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user_id
            )
        )
    ).scalars().all()
    for cid in conv_ids:
        latest = (
            await db.execute(
                select(Message.id)
                .where(Message.conversation_id == cid)
                .order_by(Message.id.desc())
                .limit(1)
            )
        ).scalar()
        if latest is None:
            continue
        await db.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == cid,
                ConversationMember.user_id == user_id,
            )
            .values(last_delivered_message_id=latest)
        )
        await db.commit()
        others = [
            uid for uid in await msg_service.member_ids(db, cid) if uid != user_id
        ]
        await manager.broadcast(
            others,
            {
                "type": "delivered",
                "conversation_id": cid,
                "user_id": user_id,
                "up_to_message_id": latest,
            },
        )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    user = await _authenticate(token or websocket.query_params.get("token"))
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = user.id
    await manager.connect(user_id, websocket)

    async with AsyncSessionLocal() as db:
        await presence_service.set_online(db, user_id)
        await _deliver_pending(db, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_event(user_id, data)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - log, then fall through to cleanup
        logger.warning("socket error for user %s: %s", user_id, exc)
    finally:
        manager.disconnect(user_id, websocket)
        # Only flip to offline once the user's LAST socket is gone.
        if not manager.is_online(user_id):
            async with AsyncSessionLocal() as db:
                await presence_service.set_offline(db, user_id)


async def _handle_event(user_id: int, data: dict) -> None:
    event = data.get("type")

    if event == "ping":
        # Heartbeat: the client pings, we pong. Lets both sides notice a dead link.
        await manager.send_to_user(user_id, {"type": "pong"})
        return

    if event == "typing":
        conv_id = data.get("conversation_id")
        if not conv_id:
            return
        async with AsyncSessionLocal() as db:
            if not await msg_service.is_member(db, conv_id, user_id):
                return
            others = [
                uid for uid in await msg_service.member_ids(db, conv_id) if uid != user_id
            ]
        await manager.broadcast(
            others,
            {
                "type": "typing",
                "conversation_id": conv_id,
                "user_id": user_id,
                "is_typing": bool(data.get("is_typing", False)),
            },
        )
        return

    if event == "chat_message":
        conv_id = data.get("conversation_id")
        content = (data.get("content") or "").strip()
        if not conv_id or not content:
            return
        reply_to_id = data.get("reply_to_id")
        async with AsyncSessionLocal() as db:
            if not await msg_service.is_member(db, conv_id, user_id):
                return
            try:
                await msg_service.create_and_broadcast(
                    db,
                    conversation_id=conv_id,
                    sender_id=user_id,
                    content=content,
                    message_type="text",
                    client_id=data.get("client_id"),
                    reply_to_id=reply_to_id if isinstance(reply_to_id, int) else None,
                )
            except ValueError:
                # Bad quote reference over the socket: drop silently. The sender's
                # optimistic bubble will reconcile on the next history load.
                return
        return

    if event == "read_receipt":
        conv_id = data.get("conversation_id")
        if not conv_id:
            return
        async with AsyncSessionLocal() as db:
            if not await msg_service.is_member(db, conv_id, user_id):
                return
            await msg_service.mark_read(db, conv_id, user_id)
        return
