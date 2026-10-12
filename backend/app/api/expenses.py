"""Personal expenses + the category list (shared)."""

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.expenses import CategoriesOut, ExpenseIn, ExpenseOut
from app.services import expenses as expense_service
from app.services.categories import CATEGORIES

router = APIRouter(tags=["expenses"])


@router.get("/categories", response_model=CategoriesOut)
def list_categories() -> CategoriesOut:
    """The fixed category list every stored expense uses."""
    return CategoriesOut(categories=list(CATEGORIES))


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(db: DB, user_id: CurrentUser, limit: int = 100) -> list[ExpenseOut]:
    return [
        ExpenseOut.from_model(e) for e in expense_service.list_expenses(db, user_id, limit=min(limit, 500))
    ]


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(body: ExpenseIn, db: DB, user_id: CurrentUser) -> ExpenseOut:
    data = expense_service.ExpenseInput(
        merchant=body.merchant,
        total=body.total,
        expense_date=body.expense_date,
        currency=body.currency,
        category=body.category,
        note=body.note,
        items=[expense_service.ItemInput(i.description, i.amount, i.quantity) for i in body.items],
    )
    saved = expense_service.add_expense(db, user_id, data)
    return ExpenseOut.from_model(saved.expense, saved.warnings)
