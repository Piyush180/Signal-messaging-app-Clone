from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import utcnow


class Message(Base):
    """
    A single message.

    Note there is NO per-message `status` column here. Delivery/read state is
    derived from the per-member pointers on ConversationMember (see that model).
    A status column can only represent ONE reader, which breaks down for groups,
    so it is deliberately absent.

    `reply_to_id` points at the quoted message for WhatsApp-style replies. It is
    nullable and uses ON DELETE SET NULL so deleting a quoted message degrades
    gracefully instead of cascading or failing.

    `message_type`:
      text   -> normal user message
      system -> app-generated notice ("X created the group", "Y was added")
    """

    __tablename__ = "messages"
    __table_args__ = (
        # The hot query is "messages in this conversation, newest first".
        # A composite index on (conversation_id, id) makes that a fast range scan.
        Index("ix_messages_conv_id", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(16), default="text", nullable=False
    )
    reply_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    sender: Mapped["User"] = relationship("User")
    # The quoted message. `remote_side` tells SQLAlchemy which side of the
    # self-referencing FK is the "parent" (the message being quoted).
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message", remote_side="Message.id", foreign_keys=[reply_to_id]
    )
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
