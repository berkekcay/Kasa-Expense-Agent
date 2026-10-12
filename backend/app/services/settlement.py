"""Pure money math for shared houses: equal split, balances, settle-up.

No database, no LLM. Everything works on integer minor units so results are exact.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Transfer:
    from_user: str
    to_user: str
    amount_minor: int


def equal_split(total_minor: int, participants: Sequence[str]) -> dict[str, int]:
    """Split `total_minor` equally. The remainder is handed out one minor unit at a time
    to the first participants (in the given order), so shares always sum to the total.

    >>> equal_split(1000, ["a", "b", "c"])
    {'a': 334, 'b': 333, 'c': 333}
    """
    if total_minor <= 0:
        raise ValueError("total must be positive")
    if not participants:
        raise ValueError("at least one participant is required")
    if len(set(participants)) != len(participants):
        raise ValueError("participants must be unique")
    base, remainder = divmod(total_minor, len(participants))
    return {user: base + (1 if i < remainder else 0) for i, user in enumerate(participants)}


def compute_balances(
    payments: Iterable[tuple[str, int]],
    shares: Iterable[tuple[str, int]],
    members: Iterable[str] = (),
    settlements: Iterable[tuple[str, str, int]] = (),
) -> dict[str, int]:
    """Net balance per user = paid - owed. Positive: others owe them. Sums to zero.

    `settlements` are recorded payments (from_user, to_user, amount) between members: the
    payer's debt shrinks and the receiver is owed that much less.
    """
    balances: dict[str, int] = {m: 0 for m in members}
    for user, amount in payments:
        balances[user] = balances.get(user, 0) + amount
    for user, amount in shares:
        balances[user] = balances.get(user, 0) - amount
    for from_user, to_user, amount in settlements:
        balances[from_user] = balances.get(from_user, 0) + amount
        balances[to_user] = balances.get(to_user, 0) - amount
    return balances


def settle_up(balances: Mapping[str, int]) -> list[Transfer]:
    """Greedy settle-up: repeatedly pay the largest creditor from the largest debtor.

    Produces at most n-1 transfers (not always the theoretical minimum, which is NP-hard,
    but optimal or close for flat-sized groups). Deterministic: ties break on user id.
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to zero")
    creditors = {u: b for u, b in balances.items() if b > 0}
    debtors = {u: -b for u, b in balances.items() if b < 0}
    transfers: list[Transfer] = []
    while creditors and debtors:
        creditor = _largest(creditors)
        debtor = _largest(debtors)
        amount = min(creditors[creditor], debtors[debtor])
        transfers.append(Transfer(from_user=debtor, to_user=creditor, amount_minor=amount))
        for book, user in ((creditors, creditor), (debtors, debtor)):
            book[user] -= amount
            if book[user] == 0:
                del book[user]
    return transfers


def _largest(book: Mapping[str, int]) -> str:
    """User with the largest amount; ties go to the alphabetically first user id."""
    return min(book, key=lambda u: (-book[u], u))
