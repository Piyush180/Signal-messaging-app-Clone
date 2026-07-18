from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    bio: Mapped[Optional[str]] = mapped_column(String(256))

    # Presence. `is_online` is a cache of "has at least one live socket"; it is
    # reset to False on server startup so a crash can't leave users stuck online.
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    contacts: Mapped[List["Contact"]] = relationship(
        "Contact",
        foreign_keys="[Contact.user_id]",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
