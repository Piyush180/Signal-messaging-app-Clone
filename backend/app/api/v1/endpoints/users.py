from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.bio is not None:
        user.bio = payload.bio
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/search", response_model=List[UserResponse])
async def search_users(
    q: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    term = f"%{q.strip()}%"
    rows = (
        await db.execute(
            select(User)
            .where(
                User.id != user.id,
                or_(User.phone_number.ilike(term), User.full_name.ilike(term)),
            )
            .limit(20)
        )
    ).scalars().all()
    return [UserResponse.model_validate(u) for u in rows]
