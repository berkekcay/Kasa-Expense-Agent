import random

import pytest

from app.services.money import MoneyError, format_minor, to_minor
from app.services.settlement import Transfer, compute_balances, equal_split, settle_up


class TestMoney:
    @pytest.mark.parametrize(
        ("raw", "minor"), [("12.5", 1250), ("0.01", 1), ("100", 10000), ("1,99", 199), (7, 700)]
    )
    def test_to_minor(self, raw, minor):
        assert to_minor(raw) == minor

    @pytest.mark.parametrize("raw", ["1.001", "abc", "NaN", 1.5])
    def test_to_minor_rejects(self, raw):
        with pytest.raises(MoneyError):
            to_minor(raw)

    def test_format(self):
        assert format_minor(123456) == "1234.56"
        assert format_minor(-5) == "-0.05"


class TestEqualSplit:
    def test_even(self):
        assert equal_split(900, ["a", "b", "c"]) == {"a": 300, "b": 300, "c": 300}

    def test_remainder_goes_to_first_participants(self):
        assert equal_split(1000, ["a", "b", "c"]) == {"a": 334, "b": 333, "c": 333}
        assert equal_split(1001, ["a", "b", "c"]) == {"a": 334, "b": 334, "c": 333}

    def test_smaller_than_participants(self):
        assert equal_split(2, ["a", "b", "c"]) == {"a": 1, "b": 1, "c": 0}

    @pytest.mark.parametrize("total", [1, 7, 99, 100, 101, 12345, 999_999_99])
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 6, 7])
    def test_always_sums_to_total_and_differs_by_at_most_one(self, total, n):
        shares = equal_split(total, [f"u{i}" for i in range(n)])
        assert sum(shares.values()) == total
        assert max(shares.values()) - min(shares.values()) <= 1

    @pytest.mark.parametrize(("total", "people"), [(0, ["a"]), (-5, ["a"]), (100, []), (100, ["a", "a"])])
    def test_invalid(self, total, people):
        with pytest.raises(ValueError):
            equal_split(total, people)


class TestBalances:
    def test_simple_flat(self):
        # a pays 90 for a/b/c, b pays 30 for a/b/c
        payments = [("a", 9000), ("b", 3000)]
        shares = [(u, 3000) for u in "abc"] + [(u, 1000) for u in "abc"]
        balances = compute_balances(payments, shares)
        assert balances == {"a": 5000, "b": -1000, "c": -4000}
        assert sum(balances.values()) == 0

    def test_members_without_activity_are_zero(self):
        assert compute_balances([], [], members=["a", "b"]) == {"a": 0, "b": 0}


class TestSettleUp:
    def test_simple(self):
        transfers = settle_up({"a": 5000, "b": -1000, "c": -4000})
        assert transfers == [Transfer("c", "a", 4000), Transfer("b", "a", 1000)]

    def test_all_settled(self):
        assert settle_up({"a": 0, "b": 0}) == []

    def test_rejects_unbalanced(self):
        with pytest.raises(ValueError):
            settle_up({"a": 10, "b": -5})

    def test_deterministic_ties(self):
        assert settle_up({"b": 100, "a": 100, "c": -200}) == [
            Transfer("c", "a", 100),
            Transfer("c", "b", 100),
        ]

    def test_random_groups_settle_exactly_with_at_most_n_minus_1_transfers(self):
        rng = random.Random(42)
        for _ in range(500):
            n = rng.randint(2, 8)
            users = [f"u{i}" for i in range(n)]
            balances = {u: rng.randint(-50_000, 50_000) for u in users[:-1]}
            balances[users[-1]] = -sum(balances.values())
            transfers = settle_up(balances)
            assert len(transfers) <= n - 1
            assert all(t.amount_minor > 0 for t in transfers)
            after = dict(balances)
            for t in transfers:
                after[t.from_user] += t.amount_minor
                after[t.to_user] -= t.amount_minor
            assert all(v == 0 for v in after.values())

    def test_split_then_settle_round_trip(self):
        members = ["ali", "ayse", "mehmet"]
        expenses = [("ali", 100_00), ("ayse", 35_50), ("ali", 10_01)]
        payments, shares = [], []
        for payer, total in expenses:
            payments.append((payer, total))
            shares.extend(equal_split(total, members).items())
        balances = compute_balances(payments, shares, members)
        assert sum(balances.values()) == 0
        transfers = settle_up(balances)
        received = {m: 0 for m in members}
        for t in transfers:
            received[t.to_user] += t.amount_minor
            received[t.from_user] -= t.amount_minor
        assert received == balances
