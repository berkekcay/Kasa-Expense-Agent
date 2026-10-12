"""Houses (owner: track HOUSE). Settlements are done; add split-type and reminder routes here."""

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.expenses import ExpenseOut
from app.schemas.houses import (
    BalancesOut,
    HouseExpenseIn,
    HouseIn,
    HouseOut,
    MemberIn,
    SettlementIn,
    SettlementOut,
)
from app.services import houses as house_service
from app.services.expenses import ExpenseInput

router = APIRouter(prefix="/houses", tags=["houses"])


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
    return [ExpenseOut.from_model(e) for e in house_service.list_house_expenses(db, user_id, house_id)]


@router.post("/{house_id}/expenses", response_model=ExpenseOut, status_code=201)
def add_house_expense(house_id: int, body: HouseExpenseIn, db: DB, user_id: CurrentUser) -> ExpenseOut:
    """Record a shared expense split equally between `split_between` (default: everyone)."""
    expense = house_service.add_equal_split_expense(
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
        paid_by=body.paid_by,
        split_between=body.split_between,
    )
    return ExpenseOut.from_model(expense)


@router.get("/{house_id}/balances", response_model=BalancesOut)
def get_balances(house_id: int, db: DB, user_id: CurrentUser) -> BalancesOut:
    """Net balance per member plus the settle-up transfers (recorded payments included)."""
    return BalancesOut.from_result(house_service.house_balances(db, user_id, house_id))


@router.get("/{house_id}/settlements", response_model=list[SettlementOut])
def list_settlements(house_id: int, db: DB, user_id: CurrentUser) -> list[SettlementOut]:
    return [SettlementOut.from_model(s) for s in house_service.list_settlements(db, user_id, house_id)]


@router.post("/{house_id}/settlements", response_model=SettlementOut, status_code=201)
def record_settlement(house_id: int, body: SettlementIn, db: DB, user_id: CurrentUser) -> SettlementOut:
    """Record a payment between flatmates ("Ayşe paid Ali 43.33"); balances shrink accordingly."""
    row = house_service.record_settlement(
        db,
        user_id,
        house_id,
        from_user=body.from_user,
        to_user=body.to_user,
        amount=body.amount,
        note=body.note,
    )
    return SettlementOut.from_model(row)
