import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType


async def create_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    category_type: CategoryType,
) -> Category:
    category = Category(
        user_id=user_id,
        name=name,
        type=category_type,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def get_user_categories(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Category]:
    result = await db.execute(
        select(Category).where(Category.user_id == user_id)
    )
    return list(result.scalars().all())
