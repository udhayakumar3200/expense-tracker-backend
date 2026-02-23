from fastapi import FastAPI

from app import models  # noqa: F401 - register all models
from app.api.accounts import router as accounts_router
from app.api.transactions import router as transactions_router

app = FastAPI(title="Expense Tracker API", version="0.1.0")

app.include_router(accounts_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
