import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db
from app.schemas.category_schema import CategoryCreate, CategoryResponse
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("/create_category", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    category = await category_service.create_category(
        db=db,
        user_id=user_id,
        name=data.name,
        category_type=data.type,
    )
    return category


@router.get("/get_categories", response_model=list[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    categories = await category_service.get_user_categories(db=db, user_id=user_id)
    return categories
