from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import utcnow


class Conversation(Base):
    """
    A single table for both 1-on-1 ("direct") and "group" chats.

    Why one table instead of two? A direct chat is just a group with exactly two
    members and no name/avatar. Unifying them means messages, membership, unread
    counts, and read receipts all have ONE code path instead of two. This is the
    biggest schema decision in the app and it keeps the rest of the code small.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16), default="direct", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # Bumped every time a message is sent, so the sidebar can sort by "recent".
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    members: Mapped[List["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    group_metadata: Mapped[Optional["GroupMetadata"]] = relationship(
        "GroupMetadata",
        back_populates="conversation",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ConversationMember(Base):
    """
    Membership row linking a user to a conversation.

    This table is where per-user chat state lives, and it is what makes read
    receipts and unread counts correct per person:

      last_read_message_id      -> the highest message id this member has read.
      last_delivered_message_id -> the highest message id delivered to a live
                                   socket for this member.

    From these two pointers we can compute, per user:
      * unread count = messages after last_read_message_id not sent by me.
      * a message's status for the SENDER = read if EVERY other member's
        last_read_message_id >= that message id, else delivered if every other
        member's last_delivered pointer covers it, else sent.

    The naive alternative — a single status string on the message itself —
    breaks in groups: one member reading a message would mark it "read" for
    everyone. Per-member pointers are correct for both direct and group chats.
    """

    __tablename__ = "conversation_members"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conv_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)
    last_read_message_id: Mapped[Optional[int]] = mapped_column(default=None)
    last_delivered_message_id: Mapped[Optional[int]] = mapped_column(default=None)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="members"
    )
    user: Mapped["User"] = relationship("User", back_populates="memberships")
