"""Import every model here so SQLAlchemy's mapper sees them all.

Importing the package (``from app import models``) guarantees all tables are
registered on ``Base.metadata`` before we call ``create_all`` or run Alembic.
"""
from app.models.user import User
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationMember
from app.models.group import GroupMetadata
from app.models.message import Message
from app.models.otp import OTPCode

__all__ = [
    "User",
    "Contact",
    "Conversation",
    "ConversationMember",
    "GroupMetadata",
    "Message",
    "OTPCode",
]
