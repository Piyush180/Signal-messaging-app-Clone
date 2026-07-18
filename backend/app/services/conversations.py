"""
Conversation service: create/fetch conversations and assemble the rich
`ConversationResponse` the sidebar needs (members, last message, unread count).
"""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, ConversationMember
from app.models.group import GroupMetadata
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import (
    ConversationResponse,
    GroupMetadataResponse,
    MemberResponse,
)
from app.schemas.user import UserResponse
from app.services import messages as msg_service


async def _load_full(db: AsyncSession, conversation_id: int) -> Conversation:
    conv = (
        await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.group_metadata),
            )
        )
    ).scalar_one()
    return conv


async def build_response(
    db: AsyncSession, conv: Conversation, viewer_id: int
) -> ConversationResponse:
    members = [
        MemberResponse(user=UserResponse.model_validate(m.user), role=m.role)
        for m in conv.members
        if m.user
    ]
    my_member = next((m for m in conv.members if m.user_id == viewer_id), None)

    group_meta = (
        GroupMetadataResponse.model_validate(conv.group_metadata)
        if conv.type == "group" and conv.group_metadata
        else None
    )

    last_msg = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .options(selectinload(Message.sender))
            .order_by(Message.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    last_message = None
    if last_msg:
        last_message = msg_service.to_response(last_msg, viewer_id, conv.members)

    unread = (
        await msg_service.unread_count(db, conv.id, my_member) if my_member else 0
    )

    return ConversationResponse(
        id=conv.id,
        type=conv.type,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        members=members,
        group_metadata=group_meta,
        last_message=last_message,
        unread_count=unread,
    )


async def list_for_user(db: AsyncSession, user: User) -> List[ConversationResponse]:
    conv_ids = (
        await db.execute(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user.id
            )
        )
    ).scalars().all()
    if not conv_ids:
        return []

    convs = (
        await db.execute(
            select(Conversation)
            .where(Conversation.id.in_(conv_ids))
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.group_metadata),
            )
            .order_by(Conversation.updated_at.desc())
        )
    ).scalars().all()

    return [await build_response(db, c, user.id) for c in convs]


async def get_for_user(
    db: AsyncSession, conversation_id: int, user: User
) -> ConversationResponse:
    if not await msg_service.is_member(db, conversation_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this conversation.")
    conv = await _load_full(db, conversation_id)
    return await build_response(db, conv, user.id)


async def get_or_create_direct(
    db: AsyncSession, user: User, other_user_id: int
) -> ConversationResponse:
    if other_user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot chat with yourself.")

    other = (
        await db.execute(select(User).where(User.id == other_user_id))
    ).scalar_one_or_none()
    if not other:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    # Find an existing direct conversation containing exactly these two users.
    existing = (
        await db.execute(
            select(Conversation.id)
            .join(ConversationMember)
            .where(
                Conversation.type == "direct",
                ConversationMember.user_id.in_([user.id, other_user_id]),
            )
            .group_by(Conversation.id)
            .having(func.count(ConversationMember.id) == 2)
        )
    ).scalars().first()

    if existing:
        conv = await _load_full(db, existing)
        return await build_response(db, conv, user.id)

    # Create atomically: one flush to get the id, members added, single commit.
    conv = Conversation(type="direct")
    db.add(conv)
    await db.flush()
    db.add_all(
        [
            ConversationMember(conversation_id=conv.id, user_id=user.id),
            ConversationMember(conversation_id=conv.id, user_id=other_user_id),
        ]
    )
    await db.commit()

    conv = await _load_full(db, conv.id)
    return await build_response(db, conv, user.id)


async def create_group(
    db: AsyncSession,
    creator: User,
    name: str,
    member_user_ids: List[int],
    description: Optional[str],
    avatar_url: Optional[str],
) -> ConversationResponse:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Group name is required.")

    ids = set(member_user_ids) | {creator.id}
    valid = (
        await db.execute(select(User.id).where(User.id.in_(ids)))
    ).scalars().all()
    if len(set(valid)) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more members do not exist.")

    conv = Conversation(type="group")
    db.add(conv)
    await db.flush()

    db.add(
        GroupMetadata(
            conversation_id=conv.id,
            name=name,
            description=description,
            avatar_url=avatar_url,
            created_by=creator.id,
        )
    )
    for uid in ids:
        db.add(
            ConversationMember(
                conversation_id=conv.id,
                user_id=uid,
                role="admin" if uid == creator.id else "member",
            )
        )
    await db.commit()

    # System message announcing creation, broadcast to everyone's sidebar.
    await msg_service.create_and_broadcast(
        db,
        conversation_id=conv.id,
        sender_id=creator.id,
        content=f'{creator.full_name or creator.phone_number} created "{name}"',
        message_type="system",
    )

    conv = await _load_full(db, conv.id)
    return await build_response(db, conv, creator.id)


# ---------- group admin ----------

async def _require_admin(
    db: AsyncSession, conversation_id: int, user_id: int
) -> ConversationMember:
    conv = await _load_full(db, conversation_id)
    if conv.type != "group":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a group conversation.")
    member = next((m for m in conv.members if m.user_id == user_id), None)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this group.")
    if member.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required.")
    return member


async def add_members(
    db: AsyncSession, conversation_id: int, actor: User, user_ids: List[int]
) -> ConversationResponse:
    await _require_admin(db, conversation_id, actor.id)

    existing_ids = set(await msg_service.member_ids(db, conversation_id))
    to_add = [uid for uid in set(user_ids) if uid not in existing_ids]

    valid = (
        await db.execute(select(User).where(User.id.in_(to_add)))
    ).scalars().all()
    for u in valid:
        db.add(ConversationMember(conversation_id=conversation_id, user_id=u.id))
    await db.commit()

    for u in valid:
        await msg_service.create_and_broadcast(
            db,
            conversation_id=conversation_id,
            sender_id=actor.id,
            content=f"{actor.full_name or actor.phone_number} added {u.full_name or u.phone_number}",
            message_type="system",
        )

    conv = await _load_full(db, conversation_id)
    return await build_response(db, conv, actor.id)


async def remove_member(
    db: AsyncSession, conversation_id: int, actor: User, target_id: int
) -> ConversationResponse:
    await _require_admin(db, conversation_id, actor.id)

    conv = await _load_full(db, conversation_id)
    target = next((m for m in conv.members if m.user_id == target_id), None)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User is not in this group.")

    creator_id = conv.group_metadata.created_by if conv.group_metadata else None
    if target_id == creator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove the group creator.")

    target_user = target.user
    # Remove from the loaded collection too, otherwise the cascade relationship
    # re-inserts it on the next commit (the system-message commit below).
    conv.members.remove(target)
    await db.delete(target)
    await db.commit()
    db.expunge_all()  # drop cached instances so the final reload is truly fresh

    await msg_service.create_and_broadcast(
        db,
        conversation_id=conversation_id,
        sender_id=actor.id,
        content=f"{actor.full_name or actor.phone_number} removed "
        f"{target_user.full_name or target_user.phone_number}",
        message_type="system",
    )

    conv = await _load_full(db, conversation_id)
    return await build_response(db, conv, actor.id)
