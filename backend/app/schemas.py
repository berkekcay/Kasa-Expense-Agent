"""Pydantic request/response models for the REST API.

Amounts go over the wire as decimal strings ("123.45") plus exact `*_minor` integers,
so no client ever has to do float money math.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models import Expense, House
from app.services.houses import HouseBalances
from app.services.money import format_minor

Amount = Decimal  # validated to max 2 decimal places via Field(decimal_places=2)


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Amount = Field(gt=0, decimal_places=2)
    quantity: Decimal = Field(default=Decimal(1), gt=0, decimal_places=3)


class ExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    expense_date: dt.date | None = None
    currency: str = Field(default="TRY", min_length=2, max_length=3)
    category: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)
    items: list[ItemIn] = []


class HouseExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    expense_date: dt.date | None = None
    currency: str | None = Field(default=None, min_length=2, max_length=3)
    category: str | None = Field(default=None, max_length=50)
    paid_by: str | None = Field(default=None, description="defaults to the caller")
    split_between: list[str] | None = Field(default=None, description="defaults to all members")


class ItemOut(BaseModel):
    description: str
    quantity: str
    amount: str
    amount_minor: int


class ShareOut(BaseModel):
    user_id: str
    amount: str
    amount_minor: int


class ExpenseOut(BaseModel):
    id: int
    owner_id: str
    house_id: int | None
    merchant: str
    expense_date: dt.date
    currency: str
    total: str
    total_minor: int
    category: str | None
    source: str
    note: str | None
    items: list[ItemOut]
    shares: list[ShareOut]

    @classmethod
    def from_model(cls, e: Expense) -> ExpenseOut:
        return cls(
            id=e.id,
            owner_id=e.owner_id,
            house_id=e.house_id,
            merchant=e.merchant,
            expense_date=e.expense_date,
            currency=e.currency,
            total=format_minor(e.total_minor),
            total_minor=e.total_minor,
            category=e.category,
            source=e.source,
            note=e.note,
            items=[
                ItemOut(
                    description=i.description,
                    quantity=str(i.quantity.normalize() if isinstance(i.quantity, Decimal) else i.quantity),
                    amount=format_minor(i.amount_minor),
                    amount_minor=i.amount_minor,
                )
                for i in e.items
            ],
            shares=[
                ShareOut(user_id=s.user_id, amount=format_minor(s.amount_minor), amount_minor=s.amount_minor)
                for s in e.shares
            ],
        )


class ReceiptOut(BaseModel):
    expense: ExpenseOut
    agent_message: str
    warnings: list[str] = []


class HouseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="TRY", min_length=2, max_length=3)


class MemberIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class MemberOut(BaseModel):
    user_id: str
    display_name: str


class HouseOut(BaseModel):
    id: int
    name: str
    currency: str
    members: list[MemberOut]

    @classmethod
    def from_model(cls, h: House) -> HouseOut:
        return cls(
            id=h.id,
            name=h.name,
            currency=h.currency,
            members=[MemberOut(user_id=m.user_id, display_name=m.user.display_name) for m in h.members],
        )


class BalanceOut(BaseModel):
    user_id: str
    balance: str  # + means the house owes this person
    balance_minor: int


class TransferOut(BaseModel):
    from_user: str
    to_user: str
    amount: str
    amount_minor: int


class BalancesOut(BaseModel):
    house_id: int
    currency: str
    balances: list[BalanceOut]
    transfers: list[TransferOut]

    @classmethod
    def from_result(cls, r: HouseBalances) -> BalancesOut:
        return cls(
            house_id=r.house.id,
            currency=r.house.currency,
            balances=[
                BalanceOut(user_id=u, balance=format_minor(b), balance_minor=b) for u, b in r.balances.items()
            ],
            transfers=[
                TransferOut(
                    from_user=t.from_user,
                    to_user=t.to_user,
                    amount=format_minor(t.amount_minor),
                    amount_minor=t.amount_minor,
                )
                for t in r.transfers
            ],
        )


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie"]
    title: str = ""
    x: str
    y: str
    data: list[dict[str, Any]]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatOut(BaseModel):
    session_id: str
    text: str
    chart: ChartSpec | None = None
