"""House schemas (owner: track HOUSE; Sprint 1 models and settlements are done)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.db.models import House, Settlement
from app.schemas.common import Amount
from app.services.houses import HouseBalances
from app.services.money import format_minor


class HouseExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    expense_date: dt.date | None = None
    currency: str | None = Field(default=None, min_length=2, max_length=3)
    category: str | None = Field(default=None, max_length=50)
    paid_by: str | None = Field(default=None, description="defaults to the caller")
    split_between: list[str] | None = Field(default=None, description="defaults to all members")


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


class SettlementIn(BaseModel):
    from_user: str = Field(min_length=1, max_length=128, description="who paid back")
    to_user: str = Field(min_length=1, max_length=128, description="who received the money")
    amount: Amount = Field(gt=0, decimal_places=2)
    note: str | None = Field(default=None, max_length=500)


class SettlementOut(BaseModel):
    id: int
    house_id: int
    from_user: str
    to_user: str
    amount: str
    amount_minor: int
    currency: str
    note: str | None
    created_by: str
    created_at: dt.datetime

    @classmethod
    def from_model(cls, s: Settlement) -> SettlementOut:
        return cls(
            id=s.id,
            house_id=s.house_id,
            from_user=s.from_user,
            to_user=s.to_user,
            amount=format_minor(s.amount_minor),
            amount_minor=s.amount_minor,
            currency=s.currency,
            note=s.note,
            created_by=s.created_by,
            created_at=s.created_at,
        )
