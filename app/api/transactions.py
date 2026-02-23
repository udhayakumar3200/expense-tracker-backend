import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_id
from app.schemas.transaction_schema import TransactionCreate, TransactionResponse
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/create_transaction", response_model=TransactionResponse)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        transaction = await transaction_service.create_transaction(
            db=db,
            user_id=user_id,
            amount=data.amount,
            transaction_type=data.type,
            transaction_date=data.transaction_date,
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            category_id=data.category_id,
            description=data.description,
        )
        return transaction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
