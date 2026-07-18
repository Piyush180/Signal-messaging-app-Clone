from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.contact import Contact
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactResponse
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("", response_model=List[ContactResponse])
async def list_contacts(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(Contact)
            .where(Contact.user_id == user.id)
            .options(selectinload(Contact.contact_user))
            .order_by(Contact.created_at.desc())
        )
    ).scalars().all()
    return [
        ContactResponse(
            id=c.id,
            user_id=c.user_id,
            contact_user=UserResponse.model_validate(c.contact_user),
            nickname=c.nickname,
            created_at=c.created_at,
        )
        for c in rows
    ]


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def add_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    phone = payload.phone_number.strip()
    target = (
        await db.execute(select(User).where(User.phone_number == phone))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that phone number.")
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot add yourself.")

    exists = (
        await db.execute(
            select(Contact.id).where(
                Contact.user_id == user.id, Contact.contact_user_id == target.id
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already in your contacts.")

    contact = Contact(
        user_id=user.id,
        contact_user_id=target.id,
        nickname=payload.nickname or target.full_name,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return ContactResponse(
        id=contact.id,
        user_id=contact.user_id,
        contact_user=UserResponse.model_validate(target),
        nickname=contact.nickname,
        created_at=contact.created_at,
    )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contact = (
        await db.execute(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found.")
    await db.delete(contact)
    await db.commit()
