"""Shared-flat ("house") data layer (owner: track HOUSE). Money math lives in `settlement`
and `splits`.

Access rule: only members of a house can read or change anything about it.

Done in the foundation: equal split through the MONEY hook, recorded settlements that
reduce balances. Track HOUSE implements `add_split_expense` (percent / exact / items).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Expense, ExpenseItem, ExpenseShare, House, HouseMember, Settlement
from app.services import settlement
from app.services.errors import Forbidden, InvalidInput, NotFound
from app.services.expenses import ExpenseInput, build_expense, ensure_user, finalize_expense
from app.services.money import MoneyError, normalize_currency, to_minor


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


def _prepare_house_expense(
    db: Session,
    user_id: str,
    house_id: int,
    data: ExpenseInput,
    paid_by: str | None,
    participants: Sequence[str] | None,
    source: str,
) -> tuple[House, Expense, list[str], list[str]]:
    """Shared steps for every split type: membership checks, build, MONEY hook.

    Returns (house, expense, participants, warnings). The expense is in the house currency
    after this (or InvalidInput is raised), ready for its shares.
    """
    house = get_house(db, user_id, house_id)
    members = member_ids(house)
    payer = paid_by or user_id
    people = list(participants or members)
    outsiders = [u for u in [payer, *people] if u not in members]
    if outsiders:
        raise Forbidden(f"not members of this house: {', '.join(sorted(set(outsiders)))}")
    if data.currency is None:
        data.currency = house.currency

    expense = build_expense(payer, data, source=source)
    warnings = finalize_expense(db, expense, base_currency=house.currency)
    if expense.currency != house.currency:
        raise InvalidInput(f"house currency is {house.currency}; could not convert from {expense.currency}")
    expense.house_id = house.id
    return house, expense, people, warnings


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
    _house, expense, participants, _warnings = _prepare_house_expense(
        db, user_id, house_id, data, paid_by, split_between, source
    )
    try:
        shares = settlement.equal_split(expense.total_minor, participants)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    expense.split_type = "equal"
    expense.shares = [ExpenseShare(user_id=u, amount_minor=a) for u, a in shares.items()]
    db.add(expense)
    db.commit()
    return expense


def add_split_expense(
    db: Session,
    user_id: str,
    house_id: int,
    data: ExpenseInput,
    *,
    split_type: str,
    paid_by: str | None = None,
    participants: list[str] | None = None,
    percents: Mapping[str, Decimal | str] | None = None,
    exact_amounts: Mapping[str, Decimal | str] | None = None,
    item_assignees: Sequence[Sequence[str]] | None = None,
    source: str = "manual",
) -> tuple[Expense, list[str]]:
    """TRACK HOUSE: record a house expense with any split type. Returns (expense, warnings).

    - "equal":   like add_equal_split_expense, between `participants` (default all members).
    - "percent": `percents` maps user_id -> percent (strings like "33.5"); must sum to 100.
    - "exact":   `exact_amounts` maps user_id -> amount in major units; must sum to the total.
    - "items":   `data.items` are the receipt lines; `item_assignees[i]` lists who shares
                 line i (empty = all `participants`). Stored as ExpenseItemAssignee rows.
    Use `_prepare_house_expense` first (it runs the MONEY hook), then `splits.*` for the
    math, then set `expense.split_type` and `expense.shares`. When the expense was
    converted from another currency, percent/items splits apply to the converted total and
    exact amounts must be given in the house currency.
    """
    raise NotImplementedError("add_split_expense: track HOUSE")


def list_house_expenses(db: Session, user_id: str, house_id: int) -> list[Expense]:
    get_house(db, user_id, house_id)  # membership check
    stmt = (
        select(Expense)
        .where(Expense.house_id == house_id)
        .options(
            selectinload(Expense.items).selectinload(ExpenseItem.assignees),
            selectinload(Expense.shares),
        )
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
    )
    return list(db.scalars(stmt))


def record_settlement(
    db: Session,
    user_id: str,
    house_id: int,
    *,
    from_user: str,
    to_user: str,
    amount: Decimal | str,
    note: str | None = None,
) -> Settlement:
    """Record that `from_user` paid `to_user` back. Any member may record it."""
    house = get_house(db, user_id, house_id)
    members = member_ids(house)
    outsiders = [u for u in (from_user, to_user) if u not in members]
    if outsiders:
        raise Forbidden(f"not members of this house: {', '.join(sorted(set(outsiders)))}")
    if from_user == to_user:
        raise InvalidInput("a payment needs two different people")
    try:
        amount_minor = to_minor(amount)
    except MoneyError as exc:
        raise InvalidInput(str(exc)) from exc
    if amount_minor <= 0:
        raise InvalidInput("amount must be positive")
    row = Settlement(
        house_id=house.id,
        from_user=from_user,
        to_user=to_user,
        amount_minor=amount_minor,
        currency=house.currency,
        note=note.strip()[:500] if note and note.strip() else None,
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    return row


def list_settlements(db: Session, user_id: str, house_id: int) -> list[Settlement]:
    get_house(db, user_id, house_id)  # membership check
    stmt = (
        select(Settlement)
        .where(Settlement.house_id == house_id)
        .order_by(Settlement.created_at.desc(), Settlement.id.desc())
    )
    return list(db.scalars(stmt))


def house_balances(db: Session, user_id: str, house_id: int) -> HouseBalances:
    house = get_house(db, user_id, house_id)
    expenses = list_house_expenses(db, user_id, house_id)
    payments = list_settlements(db, user_id, house_id)
    balances = settlement.compute_balances(
        payments=((e.owner_id, e.total_minor) for e in expenses),
        shares=((s.user_id, s.amount_minor) for e in expenses for s in e.shares),
        members=member_ids(house),
        settlements=((p.from_user, p.to_user, p.amount_minor) for p in payments),
    )
    return HouseBalances(house=house, balances=balances, transfers=settlement.settle_up(balances))
