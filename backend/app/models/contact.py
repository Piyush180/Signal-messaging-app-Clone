from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import utcnow


class Contact(Base):
    """A directional 'A saved B' relationship with an optional nickname."""

    __tablename__ = "contacts"
    __table_args__ = (
        # You can only save a given person once.
        UniqueConstraint("user_id", "contact_user_id", name="uq_user_contact"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="contacts"
    )
    contact_user: Mapped["User"] = relationship(
        "User", foreign_keys=[contact_user_id]
    )
