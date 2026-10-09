"""Shared-flat ("house") data layer. Money math is delegated to `settlement`.

Access rule: only members of a house can read or change anything about it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Expense, ExpenseShare, House, HouseMember
from app.services import settlement
from app.services.errors import Forbidden, InvalidInput, NotFound
from app.services.expenses import ExpenseInput, build_expense, ensure_user
from app.services.money import normalize_currency


@dataclass
class HouseBalances:
    house: House
    balances: dict[str, int]  # user_id -> net minor units (+ = is owed money)
    transfers: list[settlement.Transfer]


def create_house(db: Session, user_id: str, name: str, currency: str = "TRY") -> House:
    if not name.strip():
        raise InvalidInput("house name is required")
    ensure_user(db, user_id)
    house = House(name=name.strip()[:100], currency=normalize_currency(currency), created_by=user_id)
    house.members.append(HouseMember(user_id=user_id))
    db.add(house)
    db.commit()
    return get_house(db, user_id, house.id)


def list_houses(db: Session, user_id: str) -> list[House]:
    stmt = (
        select(House)
        .join(HouseMember, HouseMember.house_id == House.id)
        .where(HouseMember.user_id == user_id)
        .options(selectinload(House.members).selectinload(HouseMember.user))
        .order_by(House.id)
    )
    return list(db.scalars(stmt))


def get_house(db: Session, user_id: str, house_id: int) -> House:
    house = db.scalars(
        select(House)
        .where(House.id == house_id)
        .options(selectinload(House.members).selectinload(HouseMember.user))
    ).first()
    # Same 404 for "missing" and "not yours" so house ids can't be probed.
    if house is None or user_id not in member_ids(house):
        raise NotFound(f"house {house_id} not found")
    return house


def member_ids(house: House) -> list[str]:
    return [m.user_id for m in house.members]


def add_member(
    db: Session, user_id: str, house_id: int, new_user_id: str, display_name: str | None = None
) -> House:
    """Sprint 1: any member can add a user by id. Later: invite links + Firebase accounts."""
    house = get_house(db, user_id, house_id)
    new_user_id = new_user_id.strip()
    if not new_user_id:
        raise InvalidInput("user_id is required")
    if new_user_id in member_ids(house):
        raise InvalidInput(f"{new_user_id} is already a member")
    ensure_user(db, new_user_id, display_name)
    house.members.append(HouseMember(user_id=new_user_id))
    db.commit()
    db.expire(house)
    return get_house(db, user_id, house_id)


def add_equal_split_expense(
    db: Session,
    user_id: str,
    house_id: int,
    data: ExpenseInput,
    *,
    paid_by: str | None = None,
    split_between: list[str] | None = None,
    source: str = "manual",
) -> Expense:
    """Record a house expense paid by `paid_by` (default: caller), split equally between
    `split_between` (default: all members, in join order)."""
    house = get_house(db, user_id, house_id)
    members = member_ids(house)
    payer = paid_by or user_id
    participants = split_between or members
    outsiders = [u for u in [payer, *participants] if u not in members]
    if outsiders:
        raise Forbidden(f"not members of this house: {', '.join(sorted(set(outsiders)))}")
    if data.currency is None:
        data.currency = house.currency

    expense = build_expense(payer, data, source=source)
    if expense.currency != house.currency:
        raise InvalidInput(f"house currency is {house.currency}; currency conversion comes later")
    expense.house_id = house.id
    try:
        shares = settlement.equal_split(expense.total_minor, participants)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    expense.shares = [ExpenseShare(user_id=u, amount_minor=a) for u, a in shares.items()]
    db.add(expense)
    db.commit()
    return expense


def list_house_expenses(db: Session, user_id: str, house_id: int) -> list[Expense]:
    get_house(db, user_id, house_id)  # membership check
    stmt = (
        select(Expense)
        .where(Expense.house_id == house_id)
        .options(selectinload(Expense.items), selectinload(Expense.shares))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
    )
    return list(db.scalars(stmt))


def house_balances(db: Session, user_id: str, house_id: int) -> HouseBalances:
    house = get_house(db, user_id, house_id)
    expenses = list_house_expenses(db, user_id, house_id)
    balances = settlement.compute_balances(
        payments=((e.owner_id, e.total_minor) for e in expenses),
        shares=((s.user_id, s.amount_minor) for e in expenses for s in e.shares),
        members=member_ids(house),
    )
    return HouseBalances(house=house, balances=balances, transfers=settlement.settle_up(balances))
