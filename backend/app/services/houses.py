"""Shared-flat ("house") data layer (owner: track HOUSE). Money math lives in `settlement`
and `splits`.

Access rule: only members of a house can read or change anything about it.

Expenses: `add_split_expense` handles every split type (equal, percent, exact, items)
through the MONEY hook; `delete_house_expense` (payer only) removes one with its shares.
Members: `add_member`, `remove_member` (leave, or the creator removes someone; only with a
zero balance, and never the last member). Payments: `record_settlement` (overpayment is refused unless
asked for), `list_settlements`, `delete_settlement` (creator only). `house_balances`
includes every recorded payment.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    SPLIT_TYPES,
    Expense,
    ExpenseItem,
    ExpenseItemAssignee,
    ExpenseShare,
    House,
    HouseMember,
    Settlement,
)
from app.services import budgets, settlement, splits
from app.services.errors import Conflict, Forbidden, InvalidInput, NotFound
from app.services.expenses import ExpenseInput, build_expense, ensure_user, finalize_expense
from app.services.money import MoneyError, format_minor, normalize_currency, to_minor


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


def remove_member(db: Session, user_id: str, house_id: int, member_id: str) -> None:
    """Leave a house (member_id == user_id) or, as the house creator, remove someone.

    Only when that person's balance in the house is exactly zero (Conflict with the amount
    otherwise), and never the last member (Conflict). Their past shares and payments stay
    for history; balances keep counting them, so they stay zero.
    """
    house = get_house(db, user_id, house_id)
    members = member_ids(house)
    if member_id not in members:
        raise NotFound(f"{member_id} is not a member of this house")
    if member_id != user_id and house.created_by != user_id:
        raise Forbidden("only the person who created the house can remove other members")
    if len(members) == 1:
        raise Conflict("the last member cannot leave the house")
    balance = house_balances(db, user_id, house_id).balances.get(member_id, 0)
    if balance != 0:
        amount = f"{format_minor(abs(balance))} {house.currency}"
        if member_id == user_id:
            state = "are owed" if balance > 0 else "owe"
            raise Conflict(f"you {state} {amount} in this house; settle up to zero before leaving")
        name = next(m.user.display_name for m in house.members if m.user_id == member_id)
        state = "is owed" if balance > 0 else "owes"
        raise Conflict(f"{name} {state} {amount} in this house; settle up to zero before removing them")
    row = next(m for m in house.members if m.user_id == member_id)
    house.members.remove(row)
    db.delete(row)
    db.commit()


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
    # Budgets are checked in add_split_expense after the shares exist.
    warnings = finalize_expense(db, expense, base_currency=house.currency, check_budgets=False)
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
    expense, _warnings = add_split_expense(
        db,
        user_id,
        house_id,
        data,
        split_type="equal",
        paid_by=paid_by,
        participants=split_between,
        source=source,
    )
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
    """Record a house expense with any split type. Returns (expense, warnings).

    - "equal":   between `participants` (default all members, in join order).
    - "percent": `percents` maps user_id -> percent (strings like "33.5"); must sum to 100.
                 The people sharing are the keys of `percents`.
    - "exact":   `exact_amounts` maps user_id -> amount in major units; must sum to the total.
                 The people sharing are the keys of `exact_amounts`.
    - "items":   `data.items` are the receipt lines; `item_assignees[i]` lists who shares
                 line i (empty = all `participants`, default all members). Every line gets
                 ExpenseItemAssignee rows for the people who actually share it.
    The payer and everyone sharing must be house members (Forbidden otherwise). The MONEY
    hook runs first; percent and items splits apply to the converted total, and exact
    amounts must be given in the house currency. Warnings come from the hook plus a note
    when the item lines do not add up to the total.
    """
    if split_type not in SPLIT_TYPES:
        raise InvalidInput(f"unknown split type {split_type!r}; use one of {', '.join(SPLIT_TYPES)}")
    people, exact_minor = _split_people(split_type, participants, percents, exact_amounts)
    if split_type == "items":
        _check_item_input(data, item_assignees)

    house, expense, people, warnings = _prepare_house_expense(
        db, user_id, house_id, data, paid_by, people, source
    )
    members = member_ids(house)
    try:
        if split_type == "equal":
            shares = settlement.equal_split(expense.total_minor, people)
        elif split_type == "percent":
            shares = splits.percent_split(expense.total_minor, percents or {})
        elif split_type == "exact":
            shares = splits.exact_split(expense.total_minor, exact_minor)
        else:
            assignees = [list(a) for a in item_assignees] if item_assignees else [[] for _ in expense.items]
            outsiders = sorted({u for who in assignees for u in who if u not in members})
            if outsiders:
                raise Forbidden(f"not members of this house: {', '.join(outsiders)}")
            shares = splits.items_split(
                expense.total_minor,
                [(item.amount_minor, who) for item, who in zip(expense.items, assignees, strict=True)],
                people,
            )
            for item, who in zip(expense.items, assignees, strict=True):
                item.assignees = [ExpenseItemAssignee(user_id=u) for u in (who or people)]
            items_total = sum(item.amount_minor for item in expense.items)
            if items_total != expense.total_minor:
                warnings.append(
                    f"items add up to {format_minor(items_total)} but the total is "
                    f"{format_minor(expense.total_minor)}; the difference was spread in "
                    "proportion to each person's items"
                )
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc

    expense.split_type = split_type
    expense.shares = [ExpenseShare(user_id=u, amount_minor=a) for u, a in shares.items()]
    warnings += budgets.warnings_for_new_expense(db, expense)
    db.add(expense)
    db.commit()
    return expense, warnings


def _split_people(
    split_type: str,
    participants: Sequence[str] | None,
    percents: Mapping[str, Decimal | str] | None,
    exact_amounts: Mapping[str, Decimal | str] | None,
) -> tuple[list[str] | None, dict[str, int]]:
    """Who shares the expense, checked before anything runs. Returns (people, exact_minor).

    `people` is None when it should default to every member.
    """
    exact_minor: dict[str, int] = {}
    if split_type in ("equal", "items"):
        people = list(participants) if participants else None
        if people is not None and len(set(people)) != len(people):
            raise InvalidInput("participants must be unique")
        return people, exact_minor
    mapping = percents if split_type == "percent" else exact_amounts
    if not mapping:
        what = "percents" if split_type == "percent" else "exact_amounts"
        raise InvalidInput(f"a {split_type} split needs {what} (user_id -> value)")
    people = list(mapping)
    if participants and set(participants) != set(people):
        raise InvalidInput(f"participants do not match the people in the {split_type} split")
    try:
        if split_type == "percent":
            splits.check_percents(mapping)
        else:
            for user, amount in mapping.items():
                try:
                    exact_minor[user] = to_minor(amount)
                except MoneyError as exc:
                    raise InvalidInput(f"amount for {user}: {exc}") from exc
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    return people, exact_minor


def _check_item_input(data: ExpenseInput, item_assignees: Sequence[Sequence[str]] | None) -> None:
    if not data.items:
        raise InvalidInput("an items split needs the receipt lines (items)")
    if item_assignees is not None and len(item_assignees) != len(data.items):
        raise InvalidInput(
            f"item_assignees has {len(item_assignees)} entries but there are {len(data.items)} items"
        )


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


def delete_house_expense(db: Session, user_id: str, house_id: int, expense_id: int) -> None:
    """Delete a house expense with its shares, items and item assignees. Balances follow.

    Only the member who paid it (`owner_id`; expenses do not store who entered them) may
    delete it (Forbidden otherwise). Refused (Conflict) when someone who shares it has left
    the house, because that would change the balance of a person who is no longer there.
    """
    house = get_house(db, user_id, house_id)  # membership check
    expense = db.scalars(
        select(Expense)
        .where(Expense.id == expense_id, Expense.house_id == house_id)
        .options(
            selectinload(Expense.items).selectinload(ExpenseItem.assignees),
            selectinload(Expense.shares),
        )
    ).first()
    if expense is None:
        raise NotFound(f"expense {expense_id} not found in this house")
    if expense.owner_id != user_id:
        raise Forbidden("only the member who paid an expense can delete it")
    members = set(member_ids(house))
    involved = {s.user_id for s in expense.shares} | {a.user_id for i in expense.items for a in i.assignees}
    gone = sorted(involved - members)
    if gone:
        raise Conflict(f"{', '.join(gone)} left the house; deleting this expense would change their balance")
    db.delete(expense)
    db.commit()


def record_settlement(
    db: Session,
    user_id: str,
    house_id: int,
    *,
    from_user: str,
    to_user: str,
    amount: Decimal | str,
    note: str | None = None,
    allow_overpayment: bool = False,
) -> Settlement:
    """Record that `from_user` paid `to_user` back. Any member may record it.

    Overpayment rule: by default a payment may not be larger than what `from_user` owes
    (their negative net balance) nor larger than what `to_user` is owed (their positive
    net balance). So a payment never turns a debtor into a creditor or the other way
    round, and a typo like 2000 instead of 200 is caught. The Conflict error names the
    largest amount that fits. Pass `allow_overpayment=True` for a deliberate advance or
    a loan between flatmates; balances then simply go past zero.
    """
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
    if not allow_overpayment:
        balances = house_balances(db, user_id, house_id).balances
        owes = max(0, -balances.get(from_user, 0))
        owed = max(0, balances.get(to_user, 0))
        limit = min(owes, owed)
        if amount_minor > limit:
            if limit == 0:
                reason = (
                    f"{from_user} owes nothing right now"
                    if owes == 0
                    else f"{to_user} is not owed anything right now"
                )
            else:
                reason = f"at most {format_minor(limit)} {house.currency} is open between them"
            raise Conflict(
                f"payment of {format_minor(amount_minor)} {house.currency} from {from_user} to "
                f"{to_user} is more than the debt: {reason}"
            )
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


def delete_settlement(db: Session, user_id: str, house_id: int, settlement_id: int) -> None:
    """Undo a recorded payment. Only the member who recorded it may delete it, and not when
    one of the two people has left the house."""
    house = get_house(db, user_id, house_id)  # membership check
    row = db.get(Settlement, settlement_id)
    if row is None or row.house_id != house_id:
        raise NotFound(f"payment {settlement_id} not found")
    if row.created_by != user_id:
        raise Forbidden("only the person who recorded a payment can delete it")
    gone = sorted({row.from_user, row.to_user} - set(member_ids(house)))
    if gone:
        raise Conflict(f"{', '.join(gone)} left the house; deleting this payment would change their balance")
    db.delete(row)
    db.commit()


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
    members = set(member_ids(house))
    # People who left (always with a zero balance) are not shown.
    balances = {u: b for u, b in balances.items() if u in members or b != 0}
    return HouseBalances(house=house, balances=balances, transfers=settlement.settle_up(balances))
