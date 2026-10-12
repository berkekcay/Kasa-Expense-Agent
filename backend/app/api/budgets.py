"""Budgets (owner: track MONEY)."""

import datetime as dt

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.budgets import BudgetIn, BudgetOut, BudgetStatusOut
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
def list_budgets(db: DB, user_id: CurrentUser) -> list[BudgetOut]:
    budget_service.list_budgets(db, user_id)
    raise NotImplementedError("GET /budgets: track MONEY")


@router.put("", response_model=BudgetOut)
def set_budget(body: BudgetIn, db: DB, user_id: CurrentUser) -> BudgetOut:
    """Create or update the budget for body.category (empty = overall)."""
    raise NotImplementedError("PUT /budgets: track MONEY")


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, db: DB, user_id: CurrentUser) -> None:
    budget_service.delete_budget(db, user_id, budget_id)


@router.get("/status", response_model=list[BudgetStatusOut])
def budget_status(db: DB, user_id: CurrentUser, month: dt.date | None = None) -> list[BudgetStatusOut]:
    raise NotImplementedError("GET /budgets/status: track MONEY")
