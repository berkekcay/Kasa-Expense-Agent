"""Houses (owner: track HOUSE): members, split expenses, balances, payments, reminders.

Validation problems come back as 422 (bad input), 403 (someone is not a member), 404
(house or row not visible to the caller) or 409 (a payment larger than the open debt).
"""

from typing import Annotated

from fastapi import APIRouter, Body, Query, Response

from app.auth import DB, CurrentUser
from app.schemas.expenses import ExpenseOut
from app.schemas.houses import (
    BalancesOut,
    EqualSplitIn,
    ExactSplitIn,
    HouseExpenseIn,
    HouseIn,
    HouseOut,
    ItemsSplitIn,
    MemberIn,
    PercentSplitIn,
    ReminderCreateIn,
    ReminderOut,
    RemindersCreatedOut,
    ReminderStatusIn,
    SettlementIn,
    SettlementOut,
    SplitExpenseIn,
)
from app.services import houses as house_service
from app.services import reminders as reminder_service
from app.services.expenses import ExpenseInput, ItemInput

router = APIRouter(prefix="/houses", tags=["houses"])

SPLIT_EXAMPLES = {
    "percent": {
        "summary": "Percent split",
        "value": {
            "split_type": "percent",
            "merchant": "Electricity bill",
            "total": "600.00",
            "percents": {"ali": "50", "ayse": "30", "mehmet": "20"},
        },
    },
    "exact": {
        "summary": "Exact amounts",
        "value": {
            "split_type": "exact",
            "merchant": "Groceries",
            "total": "300.00",
            "paid_by": "ayse",
            "amounts": {"ali": "120.00", "ayse": "180.00"},
        },
    },
    "items": {
        "summary": "Per item",
        "value": {
            "split_type": "items",
            "merchant": "Migros",
            "total": "110.00",
            "items": [
                {"description": "Cheese", "amount": "60.00", "assignees": ["ali"]},
                {"description": "Bread", "amount": "40.00"},
            ],
        },
    },
    "equal": {
        "summary": "Equal split",
        "value": {"split_type": "equal", "merchant": "Internet", "total": "450.00"},
    },
}


@router.get("", response_model=list[HouseOut])
def list_houses(db: DB, user_id: CurrentUser) -> list[HouseOut]:
    return [HouseOut.from_model(h) for h in house_service.list_houses(db, user_id)]


@router.post("", response_model=HouseOut, status_code=201)
def create_house(body: HouseIn, db: DB, user_id: CurrentUser) -> HouseOut:
    return HouseOut.from_model(house_service.create_house(db, user_id, body.name, body.currency))


@router.get("/{house_id}", response_model=HouseOut)
def get_house(house_id: int, db: DB, user_id: CurrentUser) -> HouseOut:
    return HouseOut.from_model(house_service.get_house(db, user_id, house_id))


@router.post("/{house_id}/members", response_model=HouseOut, status_code=201)
def add_member(house_id: int, body: MemberIn, db: DB, user_id: CurrentUser) -> HouseOut:
    house = house_service.add_member(db, user_id, house_id, body.user_id, body.display_name)
    return HouseOut.from_model(house)


@router.get("/{house_id}/expenses", response_model=list[ExpenseOut])
def list_house_expenses(house_id: int, db: DB, user_id: CurrentUser) -> list[ExpenseOut]:
    """House expenses, newest first, with `split_type`, `shares` and per-item `assignees`."""
    return [ExpenseOut.from_model(e) for e in house_service.list_house_expenses(db, user_id, house_id)]


@router.post("/{house_id}/expenses", response_model=ExpenseOut, status_code=201)
def add_house_expense(house_id: int, body: HouseExpenseIn, db: DB, user_id: CurrentUser) -> ExpenseOut:
    """Record a shared expense split equally between `split_between` (default: everyone).

    For percent, exact or per-item splits use `POST /houses/{house_id}/expenses/split`.
    """
    expense, warnings = house_service.add_split_expense(
        db,
        user_id,
        house_id,
        ExpenseInput(
            merchant=body.merchant,
            total=body.total,
            expense_date=body.expense_date,
            currency=body.currency,
            category=body.category,
        ),
        split_type="equal",
        paid_by=body.paid_by,
        participants=body.split_between,
    )
    return ExpenseOut.from_model(expense, warnings)


@router.post("/{house_id}/expenses/split", response_model=ExpenseOut, status_code=201)
def add_split_expense(
    house_id: int,
    body: Annotated[SplitExpenseIn, Body(openapi_examples=SPLIT_EXAMPLES)],
    db: DB,
    user_id: CurrentUser,
) -> ExpenseOut:
    """Record a shared expense with any split type, chosen by `split_type`:

    - `equal`: `participants` (default all members) pay the same.
    - `percent`: `percents` maps user_id to percent; must add up to exactly 100.
    - `exact`: `amounts` maps user_id to amount; must add up to the total.
    - `items`: each line in `items` is shared by its `assignees` (empty = all
      `participants`); a difference between the lines and the total is spread in
      proportion.

    Shares always add up to the total exactly (largest-remainder rounding). The response
    carries the shares, the item assignees and any warnings (currency, budgets, items).
    """
    data = ExpenseInput(
        merchant=body.merchant,
        total=body.total,
        expense_date=body.expense_date,
        currency=body.currency,
        category=body.category,
        note=body.note,
    )
    kwargs: dict = {}
    if isinstance(body, EqualSplitIn):
        kwargs["participants"] = body.participants
    elif isinstance(body, PercentSplitIn):
        kwargs["percents"] = body.percents
    elif isinstance(body, ExactSplitIn):
        kwargs["exact_amounts"] = body.amounts
    elif isinstance(body, ItemsSplitIn):
        data.items = [ItemInput(i.description, i.amount, i.quantity) for i in body.items]
        kwargs["participants"] = body.participants
        kwargs["item_assignees"] = [i.assignees for i in body.items]
    expense, warnings = house_service.add_split_expense(
        db, user_id, house_id, data, split_type=body.split_type, paid_by=body.paid_by, **kwargs
    )
    return ExpenseOut.from_model(expense, warnings)


@router.get("/{house_id}/balances", response_model=BalancesOut)
def get_balances(house_id: int, db: DB, user_id: CurrentUser) -> BalancesOut:
    """Net balance per member plus the settle-up transfers (recorded payments included)."""
    return BalancesOut.from_result(house_service.house_balances(db, user_id, house_id))


@router.get("/{house_id}/settlements", response_model=list[SettlementOut])
def list_settlements(house_id: int, db: DB, user_id: CurrentUser) -> list[SettlementOut]:
    """Recorded payments between flatmates, newest first."""
    return [SettlementOut.from_model(s) for s in house_service.list_settlements(db, user_id, house_id)]


@router.post("/{house_id}/settlements", response_model=SettlementOut, status_code=201)
def record_settlement(house_id: int, body: SettlementIn, db: DB, user_id: CurrentUser) -> SettlementOut:
    """Record a payment between flatmates ("Ayşe paid Ali 43.33"); balances shrink accordingly.

    A payment larger than the open debt between the two answers 409 and names the largest
    amount that fits, unless `allow_overpayment` is true.
    """
    row = house_service.record_settlement(
        db,
        user_id,
        house_id,
        from_user=body.from_user,
        to_user=body.to_user,
        amount=body.amount,
        note=body.note,
        allow_overpayment=body.allow_overpayment,
    )
    return SettlementOut.from_model(row)


@router.delete("/{house_id}/settlements/{settlement_id}", status_code=204)
def delete_settlement(house_id: int, settlement_id: int, db: DB, user_id: CurrentUser) -> Response:
    """Undo a recorded payment. Only the member who recorded it can delete it (403 otherwise)."""
    house_service.delete_settlement(db, user_id, house_id, settlement_id)
    return Response(status_code=204)


@router.post("/{house_id}/reminders", response_model=RemindersCreatedOut, status_code=201)
def create_reminders(
    house_id: int, body: ReminderCreateIn, db: DB, user_id: CurrentUser
) -> RemindersCreatedOut:
    """One reminder per current settle-up transfer, due on `due_date`.

    With a connected Google account each new reminder also becomes an all-day event on the
    caller's calendar, with the two flatmates invited by email. Without one, the reminders
    are saved in Kasa only and a warning says so. Existing scheduled reminders for the same
    transfer are reused, not duplicated.
    """
    result = reminder_service.create_settle_up_reminders(
        db, user_id, house_id, due_date=body.due_date, add_to_calendar=body.add_to_calendar
    )
    return RemindersCreatedOut.from_result(result)


@router.get("/{house_id}/reminders", response_model=list[ReminderOut])
def list_reminders(
    house_id: int,
    db: DB,
    user_id: CurrentUser,
    status: Annotated[str | None, Query(description="scheduled, done or cancelled")] = None,
) -> list[ReminderOut]:
    """Reminders of the house, earliest due first."""
    return [ReminderOut.from_model(r) for r in reminder_service.list_reminders(db, user_id, house_id, status)]


@router.patch("/{house_id}/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    house_id: int, reminder_id: int, body: ReminderStatusIn, db: DB, user_id: CurrentUser
) -> ReminderOut:
    """Mark a reminder done (or scheduled again), or cancel it. Cancelling is final, only
    its creator can do it, and it deletes the calendar event."""
    row = reminder_service.set_reminder_status(db, user_id, reminder_id, body.status, house_id=house_id)
    return ReminderOut.from_model(row)
