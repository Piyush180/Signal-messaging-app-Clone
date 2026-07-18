"""
Seed demo data so the app is usable the moment it boots.

Idempotent: if any user exists we skip, so restarting the server does not
duplicate data. Run automatically on startup, or manually: `python -m app.seed`.
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, Base, engine
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationMember
from app.models.group import GroupMetadata
from app.models.message import Message
from app.models.user import User


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(User.id).limit(1))).scalar_one_or_none():
            return

        alice = User(phone_number="+15551234567", full_name="Alice Smith",
                     bio="Privacy first.")
        bob = User(phone_number="+15559876543", full_name="Bob Jones",
                   bio="Real-time everything.")
        charlie = User(phone_number="+15555555555", full_name="Charlie Brown",
                       bio="Coffee and code.")
        diana = User(phone_number="+15557778888", full_name="Diana Prince",
                     bio="Design systems.")
        db.add_all([alice, bob, charlie, diana])
        await db.flush()

        db.add_all([
            Contact(user_id=alice.id, contact_user_id=bob.id, nickname="Bob"),
            Contact(user_id=alice.id, contact_user_id=charlie.id, nickname="Charlie"),
            Contact(user_id=alice.id, contact_user_id=diana.id, nickname="Diana"),
            Contact(user_id=bob.id, contact_user_id=alice.id, nickname="Alice"),
            Contact(user_id=bob.id, contact_user_id=charlie.id, nickname="Charlie"),
        ])

        # Direct chat: Alice <-> Bob
        direct = Conversation(type="direct")
        db.add(direct)
        await db.flush()
        db.add_all([
            ConversationMember(conversation_id=direct.id, user_id=alice.id),
            ConversationMember(conversation_id=direct.id, user_id=bob.id),
        ])
        first = Message(conversation_id=direct.id, sender_id=bob.id,
                        content="Hey Alice! Did you see the new build?")
        db.add(first)
        await db.flush()  # need first.id to seed a quoted reply below
        db.add_all([
            Message(conversation_id=direct.id, sender_id=alice.id,
                    content="Yes — the read receipts finally work per person.",
                    reply_to_id=first.id),
            Message(conversation_id=direct.id, sender_id=bob.id,
                    content="Exactly what we wanted."),
        ])

        # Group chat: Alice (admin), Bob, Charlie
        group = Conversation(type="group")
        db.add(group)
        await db.flush()
        db.add(GroupMetadata(conversation_id=group.id, name="Engineering",
                             description="Build channel", created_by=alice.id))
        db.add_all([
            ConversationMember(conversation_id=group.id, user_id=alice.id, role="admin"),
            ConversationMember(conversation_id=group.id, user_id=bob.id),
            ConversationMember(conversation_id=group.id, user_id=charlie.id),
        ])
        db.add_all([
            Message(conversation_id=group.id, sender_id=alice.id, message_type="system",
                    content='Alice Smith created "Engineering"'),
            Message(conversation_id=group.id, sender_id=alice.id,
                    content="Welcome to the team channel."),
            Message(conversation_id=group.id, sender_id=charlie.id,
                    content="Glad to be here!"),
        ])
        await db.commit()


async def _main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_if_empty()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(_main())
