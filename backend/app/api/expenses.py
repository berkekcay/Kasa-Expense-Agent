from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas import ExpenseIn, ExpenseOut
from app.services import expenses as expense_service

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
def list_expenses(db: DB, user_id: CurrentUser, limit: int = 100) -> list[ExpenseOut]:
    return [
        ExpenseOut.from_model(e) for e in expense_service.list_expenses(db, user_id, limit=min(limit, 500))
    ]


@router.post("", response_model=ExpenseOut, status_code=201)
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
    return ExpenseOut.from_model(expense_service.create_expense(db, user_id, data))
