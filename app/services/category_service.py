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


async def get_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> Category | None:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    name: str | None = None,
    category_type: CategoryType | None = None,
) -> Category | None:
    category = await get_category(db, user_id, category_id)
    if category is None:
        return None
    if name is not None:
        category.name = name
    if category_type is not None:
        category.type = category_type
    await db.flush()
    await db.refresh(category)
    return category
