"""Split math beyond equal shares (owner: track HOUSE).

Pure functions on integer minor units, like `settlement.equal_split`: no DB, no LLM.
Every function returns {user_id: share_minor} whose values sum exactly to `total_minor`,
in the order the participants were given. Raise ValueError on bad input (the service
turns it into InvalidInput).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal


def percent_split(total_minor: int, percents: Mapping[str, Decimal | str]) -> dict[str, int]:
    """Split by percentages ("50", "33.33", ...) that must sum to exactly 100.

    Rounding: floor each share, then hand out the leftover minor units one at a time by
    largest fractional remainder (ties: given order), so the sum is exact.
    """
    raise NotImplementedError("percent_split: track HOUSE")


def exact_split(total_minor: int, amounts_minor: Mapping[str, int]) -> dict[str, int]:
    """Each person's exact amount; must be >= 0 and sum to `total_minor`."""
    raise NotImplementedError("exact_split: track HOUSE")


def items_split(
    total_minor: int,
    items: Sequence[tuple[int, Sequence[str]]],
    participants: Sequence[str],
) -> dict[str, int]:
    """Per-item split. `items` is [(item_amount_minor, assignee_user_ids), ...]; an empty
    assignee list means the item is shared by all `participants`. Each item is split
    equally between its assignees. Any difference between the item sum and `total_minor`
    (discounts, service charge, VAT lines) is spread over participants in proportion to
    their item shares, with the same exact-rounding rule as `percent_split`.
    """
    raise NotImplementedError("items_split: track HOUSE")
