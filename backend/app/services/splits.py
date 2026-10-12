"""Split math beyond equal shares (owner: track HOUSE).

Pure functions on integer minor units, like `settlement.equal_split`: no DB, no LLM.
Every function returns {user_id: share_minor} whose values sum exactly to `total_minor`,
in the order the participants were given, and no share is ever negative. They raise
ValueError on bad input (the service turns it into InvalidInput).

Rounding rule (shared by percent and items splits): every person's exact share is a
fraction of the total. Each share is rounded down, and the minor units left over are
handed out one at a time to the largest fractional remainders. Ties go to whoever comes
first in the given order. This is the largest-remainder (Hamilton) method: no share is
more than one minor unit away from its exact value, and the result is deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from math import lcm

from app.services.money import format_minor

HUNDRED_PERCENT = 10_000  # percents are handled in hundredths: "33.33" -> 3333


def allocate(total_minor: int, weights: Sequence[int]) -> list[int]:
    """Split `total_minor` in proportion to non-negative integer `weights`.

    Largest-remainder rounding, ties to the earlier index. A zero weight always gets 0.
    """
    if total_minor < 0:
        raise ValueError("total must not be negative")
    if any(w < 0 for w in weights):
        raise ValueError("weights must not be negative")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("at least one weight must be positive")
    floors, remainders = [], []
    for w in weights:
        q, r = divmod(total_minor * w, weight_sum)
        floors.append(q)
        remainders.append(r)
    leftover = total_minor - sum(floors)
    # leftover < number of non-zero remainders, so zero weights never get a unit.
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        floors[i] += 1
    return floors


def _is_minor(value: object) -> bool:
    """A plain int (bool is an int subclass, but True is not an amount)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_total(total_minor: int) -> None:
    if not _is_minor(total_minor):
        raise ValueError("total must be an integer number of minor units")
    if total_minor <= 0:
        raise ValueError("total must be positive")


def _percent_hundredths(user: str, value: Decimal | str | int) -> int:
    kind = type(value).__name__
    if kind in ("float", "bool"):
        raise ValueError(f"percent for {user}: pass a string or Decimal, not {kind}")
    try:
        number = Decimal(str(value).strip().replace(",", ".").removesuffix("%").strip())
    except InvalidOperation as exc:
        raise ValueError(f"percent for {user} is not a number: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"percent for {user} is not a number: {value!r}")
    hundredths = number * 100
    if hundredths != hundredths.to_integral_value():
        raise ValueError(f"percent for {user} has more than 2 decimal places: {value!r}")
    if number < 0 or number > 100:
        raise ValueError(f"percent for {user} must be between 0 and 100, got {value!r}")
    return int(hundredths)


def check_percents(percents: Mapping[str, Decimal | str | int]) -> dict[str, int]:
    """Validate percents and return them in hundredths. They must sum to exactly 100."""
    if not percents:
        raise ValueError("at least one percent is required")
    parsed = {user: _percent_hundredths(user, value) for user, value in percents.items()}
    total = sum(parsed.values())
    if total != HUNDRED_PERCENT:
        raise ValueError(f"percents must add up to 100, they add up to {Decimal(total) / 100}")
    return parsed


def percent_split(total_minor: int, percents: Mapping[str, Decimal | str | int]) -> dict[str, int]:
    """Split by percentages ("50", "33.33", ...) that must sum to exactly 100.

    At most 2 decimal places per percent; floats are refused (pass strings or Decimal).
    Rounding: largest remainder (see the module docstring), ties to the given order.

    >>> percent_split(10000, {"a": "33.33", "b": "33.33", "c": "33.34"})
    {'a': 3333, 'b': 3333, 'c': 3334}
    """
    _check_total(total_minor)
    parsed = check_percents(percents)
    users = list(parsed)
    shares = allocate(total_minor, [parsed[u] for u in users])
    return dict(zip(users, shares, strict=True))


def exact_split(total_minor: int, amounts_minor: Mapping[str, int]) -> dict[str, int]:
    """Each person's exact amount; must be >= 0 and sum to `total_minor`."""
    _check_total(total_minor)
    if not amounts_minor:
        raise ValueError("at least one amount is required")
    for user, amount in amounts_minor.items():
        if not _is_minor(amount):
            raise ValueError(f"amount for {user} must be an integer number of minor units")
        if amount < 0:
            raise ValueError(f"amount for {user} must not be negative")
    given = sum(amounts_minor.values())
    if given != total_minor:
        diff = total_minor - given
        hint = f"{format_minor(diff)} missing" if diff > 0 else f"{format_minor(-diff)} too much"
        raise ValueError(
            f"exact amounts add up to {format_minor(given)} but the total is "
            f"{format_minor(total_minor)} ({hint})"
        )
    return dict(amounts_minor)


def items_split(
    total_minor: int,
    items: Sequence[tuple[int, Sequence[str]]],
    participants: Sequence[str],
) -> dict[str, int]:
    """Per-item split. `items` is [(item_amount_minor, assignee_user_ids), ...].

    Rules:
    1. Each item is shared equally by its assignees. An empty assignee list means the item
       is shared by all `participants`. Assignees must be participants.
    2. Item shares are kept as exact fractions (nothing is rounded per item), so a person's
       weight is the sum of amount / number_of_assignees over their items.
    3. The total is then split in proportion to those weights. When the items add up to
       the total this gives each person exactly their item shares. When they do not (tax,
       service charge, discount, rounding on the receipt) the difference is spread in
       proportion to what each person had, so a person with no items pays nothing.
    4. Rounding to minor units uses the largest-remainder method of `percent_split`, ties
       to the order of `participants`.

    Item amounts must be >= 0 and add up to more than 0. Put discounts in the total, not
    as negative lines.
    """
    _check_total(total_minor)
    people = list(participants)
    if not people:
        raise ValueError("at least one participant is required")
    if len(set(people)) != len(people):
        raise ValueError("participants must be unique")
    if not items:
        raise ValueError("an items split needs at least one item")
    member_set = set(people)
    resolved: list[tuple[int, list[str]]] = []
    for index, (amount, assignees) in enumerate(items, start=1):
        if not _is_minor(amount):
            raise ValueError(f"item {index}: amount must be an integer number of minor units")
        if amount < 0:
            raise ValueError(f"item {index}: amount must not be negative")
        who = list(assignees) or people
        if len(set(who)) != len(who):
            raise ValueError(f"item {index}: assignees must be unique")
        strangers = [u for u in who if u not in member_set]
        if strangers:
            raise ValueError(f"item {index}: {', '.join(strangers)} not among the participants")
        resolved.append((amount, who))
    if sum(amount for amount, _ in resolved) <= 0:
        raise ValueError("items must add up to more than 0")

    # Exact weights as integers: scale every item share by a common denominator.
    denominator = lcm(*(len(who) for _, who in resolved))
    weights = dict.fromkeys(people, 0)
    for amount, who in resolved:
        per_person = amount * (denominator // len(who))
        for user in who:
            weights[user] += per_person
    shares = allocate(total_minor, [weights[u] for u in people])
    return dict(zip(people, shares, strict=True))
