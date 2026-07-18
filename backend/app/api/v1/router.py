from fastapi import APIRouter

from app.api.v1.endpoints import auth, contacts, conversations, groups, messages, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(
    conversations.router, prefix="/conversations", tags=["conversations"]
)
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(messages.router, tags=["messages"])
