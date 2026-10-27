"""Personal expenses + the category list (shared)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.auth import DB, CurrentUser
from app.schemas.expenses import CategoriesOut, ExpenseIn, ExpenseOut, ExpenseUpdateIn
from app.services import expenses as expense_service
from app.services.categories import CATEGORIES

router = APIRouter(tags=["expenses"])

TOTAL_COUNT_HEADER = "X-Total-Count"


@router.get("/categories", response_model=CategoriesOut)
def list_categories() -> CategoriesOut:
    """The fixed category list every stored expense uses."""
    return CategoriesOut(categories=list(CATEGORIES))


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(
    db: DB,
    user_id: CurrentUser,
    response: Response,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")] = None,
    category: Annotated[
        str | None, Query(max_length=50, description="a category from /categories, or none")
    ] = None,
    source: Annotated[str | None, Query(description="manual, receipt, statement or email")] = None,
    scope: Annotated[
        Literal["all", "personal", "house"],
        Query(description="all (default): personal and house bills you paid; personal; house"),
    ] = "all",
    limit: Annotated[int, Query(ge=1, description="page size, at most 500")] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExpenseOut]:
    """Your own expenses, newest first: personal ones and house bills you paid.

    Filters combine with AND. The `X-Total-Count` header holds the number of matching
    expenses, so a client can page with `limit` and `offset`.
    """
    filters = expense_service.ExpenseFilters(month=month, category=category, source=source, scope=scope)
    rows = expense_service.list_expenses(
        db, user_id, limit=min(limit, expense_service.MAX_PAGE), offset=offset, filters=filters
    )
    response.headers[TOTAL_COUNT_HEADER] = str(expense_service.count_expenses(db, user_id, filters))
    return [ExpenseOut.from_model(e) for e in rows]


@router.get(
    "/expenses/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "UTF-8 CSV with a BOM"}},
)
def export_expenses(
    db: DB,
    user_id: CurrentUser,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")] = None,
    category: Annotated[
        str | None, Query(max_length=50, description="a category from /categories, or none")
    ] = None,
    source: Annotated[str | None, Query(description="manual, receipt, statement or email")] = None,
    scope: Annotated[
        Literal["all", "personal", "house"],
        Query(description="all (default): personal and house bills you paid; personal; house"),
    ] = "all",
) -> Response:
    """Download the expenses `GET /expenses` would list with the same filters, all of them.

    Columns: id, date, merchant, category, source, amount, amount_minor, currency,
    original_amount, original_currency, fx_rate, house_id, my_share (your share of a house
    bill), note. More than 10 000 matching expenses answers 422.
    """
    filters = expense_service.ExpenseFilters(month=month, category=category, source=source, scope=scope)
    body = expense_service.export_expenses_csv(db, user_id, filters)
    filename = f"kasa-expenses-{month}.csv" if month else "kasa-expenses.csv"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, body: ExpenseUpdateIn, db: DB, user_id: CurrentUser) -> ExpenseOut:
    """Change the merchant, category, date or note of one of your expenses.

    Send only the fields to change. Amounts cannot be edited: to fix an amount, delete the
    expense and add it again (sending `total`, `currency` or `items` answers 422).
    Someone else's expense answers 404.
    """
    changes = expense_service.ExpenseChanges(fields=set(body.model_fields_set), **body.model_dump())
    return ExpenseOut.from_model(expense_service.update_expense(db, user_id, expense_id, changes))


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: DB, user_id: CurrentUser) -> Response:
    """Delete one of your personal expenses with its receipt lines.

    Someone else's expense answers 404. A house expense answers 409: delete it with
    `DELETE /houses/{house_id}/expenses/{expense_id}` so the balances stay right.
    """
    expense_service.delete_expense(db, user_id, expense_id)
    return Response(status_code=204)
