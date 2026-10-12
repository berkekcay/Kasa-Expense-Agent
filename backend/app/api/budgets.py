"""Budgets (owner: track MONEY). Errors: 422 invalid input, 404 unknown budget."""

import datetime as dt

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.budgets import BudgetIn, BudgetOut, BudgetStatusOut
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut], summary="List my budgets")
def list_budgets(db: DB, user_id: CurrentUser) -> list[BudgetOut]:
    """Overall budget first (category null), then category budgets alphabetically."""
    return [BudgetOut.from_model(b) for b in budget_service.list_budgets(db, user_id)]


@router.put("", response_model=BudgetOut, summary="Create or update a budget")
def set_budget(body: BudgetIn, db: DB, user_id: CurrentUser) -> BudgetOut:
    """Create or update the budget for body.category (empty = overall). One budget per
    category; sending the same category again changes its limit and threshold."""
    budget = budget_service.set_budget(
        db,
        user_id,
        category=body.category,
        limit=body.limit,
        currency=body.currency,
        alert_threshold_pct=body.alert_threshold_pct,
    )
    return BudgetOut.from_model(budget)


@router.delete("/{budget_id}", status_code=204, summary="Delete a budget")
def delete_budget(budget_id: int, db: DB, user_id: CurrentUser) -> None:
    budget_service.delete_budget(db, user_id, budget_id)


@router.get("/status", response_model=list[BudgetStatusOut], summary="Spent and remaining per budget")
def budget_status(db: DB, user_id: CurrentUser, month: dt.date | None = None) -> list[BudgetStatusOut]:
    """For the month containing `month` (default: this month). Spending is my personal
    expenses plus my shares of house expenses, in the base currency."""
    statuses = budget_service.budget_status(db, user_id, month)
    db.commit()  # keeps any exchange rate fetched while converting
    return [BudgetStatusOut.from_status(s) for s in statuses]
