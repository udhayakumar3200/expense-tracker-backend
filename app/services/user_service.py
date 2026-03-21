import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def ensure_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str | None,
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is not None:
        return
    resolved_email = email or f"{user_id}@users.local"
    if email:
        dup = await db.execute(select(User).where(User.email == email))
        if dup.scalar_one_or_none() is not None:
            resolved_email = f"{user_id}@users.local"
    db.add(User(id=user_id, email=resolved_email))
    await db.flush()
