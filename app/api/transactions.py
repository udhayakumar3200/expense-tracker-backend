import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_id
from app.models.transaction import TransactionType
from app.schemas.transaction_schema import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
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


@router.get("/get_transactions", response_model=list[TransactionResponse])
async def get_transactions(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    transaction_date_from: datetime | None = Query(None),
    transaction_date_to: datetime | None = Query(None),
    type: TransactionType | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
):
    return await transaction_service.list_transactions(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        txn_type=type,
        account_id=account_id,
        category_id=category_id,
    )


@router.get("/get_transaction/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    txn = await transaction_service.get_transaction(
        db=db, user_id=user_id, transaction_id=transaction_id
    )
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    return txn


@router.patch("/update_transaction/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    updates = data.model_dump(exclude_unset=True)
    try:
        txn = await transaction_service.update_transaction(
            db=db, user_id=user_id, transaction_id=transaction_id, updates=updates
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    return txn


@router.delete("/delete_transaction/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        deleted = await transaction_service.delete_transaction(
            db=db, user_id=user_id, transaction_id=transaction_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    return None
