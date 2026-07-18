from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserResponse


class MessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    # Optional client-generated id so the sender can match the "sending" bubble
    # it drew optimistically with the confirmed message echoed back by the server.
    client_id: Optional[str] = None
    # Id of the message being quoted (WhatsApp-style reply). Validated
    # server-side: it must exist and belong to the same conversation.
    reply_to_id: Optional[int] = None


class QuotedMessage(BaseModel):
    """
    The compact preview embedded in a reply bubble: just enough to render the
    quote (who said it, what they said). Deliberately NOT a full MessageResponse
    — quotes never need status/receipts, and a flat shape avoids recursion.
    """

    id: int
    sender_id: int
    sender_name: str
    content: str
    message_type: str

    model_config = ConfigDict(from_attributes=False)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender: UserResponse
    content: str
    message_type: str
    created_at: datetime

    # Derived per-viewer, not stored. For a message you sent, this is the
    # aggregate status across the other members: sent | delivered | read.
    status: str = "sent"
    # Echoed back so the client can reconcile its optimistic bubble.
    client_id: Optional[str] = None
    # Present when this message quotes another one.
    reply_to: Optional[QuotedMessage] = None

    model_config = ConfigDict(from_attributes=True)


class MessagePage(BaseModel):
    """One page of history. `has_more` + `next_cursor` drive infinite scroll."""

    messages: List[MessageResponse]
    has_more: bool
    next_cursor: Optional[int] = None  # pass as `before_id` to get older messages
