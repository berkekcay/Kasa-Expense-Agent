"""House schemas (owner: track HOUSE): houses, split expenses, balances, payments, reminders."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.db.models import House, Reminder, Settlement
from app.schemas.common import Amount
from app.services.houses import HouseBalances
from app.services.money import format_minor
from app.services.reminders import CreatedReminders

UserRef = Annotated[str, Field(min_length=1, max_length=128)]
Percent = Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]
ShareAmount = Annotated[Decimal, Field(ge=0, decimal_places=2)]


class HouseExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    expense_date: dt.date | None = None
    currency: str | None = Field(default=None, min_length=2, max_length=3)
    category: str | None = Field(default=None, max_length=50)
    paid_by: str | None = Field(default=None, description="defaults to the caller")
    split_between: list[str] | None = Field(default=None, description="defaults to all members")


class _SplitExpenseBase(BaseModel):
    merchant: str = Field(min_length=1, max_length=200, description="what was bought, e.g. Electricity bill")
    total: Amount = Field(gt=0, decimal_places=2, description="grand total in major units, e.g. 600.00")
    expense_date: dt.date | None = Field(default=None, description="defaults to today")
    currency: str | None = Field(
        default=None, min_length=2, max_length=3, description="defaults to the house currency"
    )
    category: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)
    paid_by: str | None = Field(
        default=None, max_length=128, description="member who paid; defaults to the caller"
    )


class EqualSplitIn(_SplitExpenseBase):
    """Everyone in `participants` pays the same; leftover minor units go to the first ones."""

    split_type: Literal["equal"]
    participants: list[UserRef] | None = Field(default=None, description="defaults to all members")


class PercentSplitIn(_SplitExpenseBase):
    """Shares by percent. Percents must add up to exactly 100 (up to 2 decimals each)."""

    split_type: Literal["percent"]
    percents: dict[str, Percent] = Field(
        min_length=1, description='user_id -> percent, e.g. {"ali": "50", "ayse": "30", "me": "20"}'
    )


class ExactSplitIn(_SplitExpenseBase):
    """Each person's exact amount in the house currency; must add up to the total."""

    split_type: Literal["exact"]
    amounts: dict[str, ShareAmount] = Field(
        min_length=1, description='user_id -> amount, e.g. {"ali": "250.00", "ayse": "350.00"}'
    )


class SplitItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Amount = Field(gt=0, decimal_places=2, description="line total in major units")
    quantity: Decimal = Field(default=Decimal(1), gt=0, decimal_places=3)
    assignees: list[UserRef] = Field(
        default_factory=list, description="who shares this line; empty means all participants"
    )


class ItemsSplitIn(_SplitExpenseBase):
    """Per-item split. Each line is shared equally by its assignees. If the lines do not add
    up to the total (tax, tip, discount), the difference is spread in proportion to what
    each person had."""

    split_type: Literal["items"]
    items: list[SplitItemIn] = Field(min_length=1)
    participants: list[UserRef] | None = Field(
        default=None, description="who shares unassigned lines; defaults to all members"
    )


SplitExpenseIn = Annotated[
    EqualSplitIn | PercentSplitIn | ExactSplitIn | ItemsSplitIn, Field(discriminator="split_type")
]


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
    created_by: str = Field(description="the creator; only they can remove other members")
    members: list[MemberOut]

    @classmethod
    def from_model(cls, h: House) -> HouseOut:
        return cls(
            id=h.id,
            name=h.name,
            currency=h.currency,
            created_by=h.created_by,
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
    allow_overpayment: bool = Field(
        default=False,
        description=(
            "By default a payment larger than the open debt between the two is refused (409). "
            "Set true for a deliberate advance or loan."
        ),
    )


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


class ReminderCreateIn(BaseModel):
    due_date: dt.date = Field(description="day the payments are due (today or later)")
    add_to_calendar: bool = Field(
        default=True, description="also add Google Calendar events when the caller has connected Google"
    )


class ReminderStatusIn(BaseModel):
    status: Literal["scheduled", "done", "cancelled"] = Field(
        description="done = paid; cancelled is final and deletes the calendar event (creator only)"
    )


class ReminderOut(BaseModel):
    id: int
    house_id: int
    from_user: str
    to_user: str
    amount: str
    amount_minor: int
    currency: str
    due_date: dt.date
    status: str
    calendar_event_id: str | None
    created_by: str
    created_at: dt.datetime | None
    cancel_reason: Literal["user", "outdated"] | None = Field(
        default=None,
        description='why it was cancelled: "user" by its creator, "outdated" replaced after the balances changed',
    )
    outdated: bool = Field(
        default=False,
        description="scheduled, but no longer matches a suggested transfer; creating reminders again updates it",
    )

    @classmethod
    def from_model(cls, r: Reminder, *, outdated: bool = False) -> ReminderOut:
        return cls(
            id=r.id,
            house_id=r.house_id,
            from_user=r.from_user,
            to_user=r.to_user,
            amount=format_minor(r.amount_minor),
            amount_minor=r.amount_minor,
            currency=r.currency,
            due_date=r.due_date,
            status=r.status,
            calendar_event_id=r.calendar_event_id,
            created_by=r.created_by,
            created_at=r.created_at,
            cancel_reason=r.cancel_reason,
            outdated=outdated,
        )


class RemindersCreatedOut(BaseModel):
    reminders: list[ReminderOut]
    calendar_connected: bool = Field(description="true when the caller's Google Calendar was used")
    warnings: list[str] = []
    cancelled: list[ReminderOut] = Field(
        default=[], description="scheduled reminders that no longer matched the balances and were cancelled"
    )

    @classmethod
    def from_result(cls, r: CreatedReminders) -> RemindersCreatedOut:
        return cls(
            reminders=[ReminderOut.from_model(x) for x in r.reminders],
            calendar_connected=r.calendar_connected,
            warnings=r.warnings,
            cancelled=[ReminderOut.from_model(x) for x in r.cancelled],
        )
