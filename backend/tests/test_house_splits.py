"""Pure split math: percent, exact and per-item splits (track HOUSE)."""

import random
from decimal import Decimal

import pytest

from app.services.splits import allocate, exact_split, items_split, percent_split


class TestAllocate:
    def test_proportional_and_exact(self):
        assert allocate(100, [1, 1, 1]) == [34, 33, 33]
        assert allocate(100, [2, 1, 1]) == [50, 25, 25]
        assert allocate(0, [1, 2]) == [0, 0]

    def test_zero_weight_never_gets_a_unit(self):
        assert allocate(5, [1, 0, 1]) == [3, 0, 2]

    @pytest.mark.parametrize("weights", [[], [0, 0], [-1, 2]])
    def test_invalid(self, weights):
        with pytest.raises(ValueError):
            allocate(10, weights)


class TestPercentSplit:
    def test_the_bill_from_the_brief(self):
        assert percent_split(60000, {"ali": "50", "ayse": "30", "me": "20"}) == {
            "ali": 30000,
            "ayse": 18000,
            "me": 12000,
        }

    def test_largest_remainder(self):
        # 100.00 at 33.33/33.33/33.34 is exact; 1.00 at thirds needs rounding.
        assert percent_split(10000, {"a": "33.33", "b": "33.33", "c": "33.34"}) == {
            "a": 3333,
            "b": 3333,
            "c": 3334,
        }
        # exact: 33.33, 33.33, 33.34 -> floors 33, 33, 33, leftover 1 to the largest remainder (c)
        assert percent_split(100, {"a": "33.33", "b": "33.33", "c": "33.34"}) == {"a": 33, "b": 33, "c": 34}

    def test_ties_go_to_the_given_order(self):
        assert percent_split(1, {"b": "50", "a": "50"}) == {"b": 1, "a": 0}
        assert percent_split(1, {"a": "50", "b": "50"}) == {"a": 1, "b": 0}

    def test_accepts_decimal_int_and_comma_and_percent_sign(self):
        assert percent_split(1000, {"a": Decimal("12.5"), "b": 50, "c": "37,5%"}) == {
            "a": 125,
            "b": 500,
            "c": 375,
        }

    def test_zero_percent_person_pays_nothing(self):
        assert percent_split(999, {"a": "0", "b": "100"}) == {"a": 0, "b": 999}

    @pytest.mark.parametrize(
        ("percents", "message"),
        [
            ({"a": "50", "b": "49.99"}, "add up to 100"),
            ({"a": "60", "b": "60"}, "add up to 100"),
            ({"a": "33.333", "b": "66.667"}, "2 decimal places"),
            ({"a": "-10", "b": "110"}, "between 0 and 100"),
            ({"a": "abc", "b": "100"}, "not a number"),
            ({"a": "NaN", "b": "100"}, "not a number"),
            ({"a": 50.0, "b": "50"}, "not float"),
            ({}, "at least one"),
        ],
    )
    def test_invalid(self, percents, message):
        with pytest.raises(ValueError, match=message):
            percent_split(1000, percents)

    @pytest.mark.parametrize("total", [0, -1])
    def test_invalid_total(self, total):
        with pytest.raises(ValueError):
            percent_split(total, {"a": "100"})

    def test_property_random(self):
        rng = random.Random(7)
        for _ in range(2000):
            n = rng.randint(1, 7)
            cuts = sorted(rng.randint(0, 10000) for _ in range(n - 1))
            hundredths = [b - a for a, b in zip([0, *cuts], [*cuts, 10000], strict=True)]
            percents = {f"u{i}": str(Decimal(h) / 100) for i, h in enumerate(hundredths)}
            total = rng.randint(1, 10_000_000)
            shares = percent_split(total, percents)
            assert list(shares) == list(percents)
            assert sum(shares.values()) == total
            assert all(v >= 0 for v in shares.values())
            for user, h in zip(shares, hundredths, strict=True):
                exact = Decimal(total) * h / 10000
                assert abs(shares[user] - exact) < 1  # never more than one minor unit off
                if h == 0:
                    assert shares[user] == 0

    def test_deterministic(self):
        percents = {"x": "33.33", "y": "33.33", "z": "33.34"}
        assert all(percent_split(1001, percents) == percent_split(1001, percents) for _ in range(5))


class TestExactSplit:
    def test_ok(self):
        assert exact_split(30000, {"ali": 12000, "ayse": 18000}) == {"ali": 12000, "ayse": 18000}
        assert exact_split(100, {"a": 0, "b": 100}) == {"a": 0, "b": 100}

    def test_missing_amount_is_explained(self):
        with pytest.raises(ValueError, match=r"add up to 250.00 but the total is 300.00 \(50.00 missing\)"):
            exact_split(30000, {"a": 12000, "b": 13000})

    def test_too_much_is_explained(self):
        with pytest.raises(ValueError, match=r"0.01 too much"):
            exact_split(100, {"a": 50, "b": 51})

    @pytest.mark.parametrize("amounts", [{}, {"a": -1, "b": 101}, {"a": 50.0, "b": 50}, {"a": True}])
    def test_invalid(self, amounts):
        with pytest.raises(ValueError):
            exact_split(100, amounts)


class TestItemsSplit:
    def test_assigned_and_shared_lines(self):
        # cheese 60 for ali, bread 40 for everyone (a, b) -> ali 80, ayse 20
        shares = items_split(10000, [(6000, ["ali"]), (4000, [])], ["ali", "ayse"])
        assert shares == {"ali": 8000, "ayse": 2000}

    def test_person_without_items_pays_nothing(self):
        shares = items_split(5000, [(3000, ["a"]), (2000, ["b"])], ["a", "b", "c"])
        assert shares == {"a": 3000, "b": 2000, "c": 0}

    def test_tax_is_spread_in_proportion(self):
        # items 100 (a 75, b 25), total 120: a 90, b 30
        assert items_split(12000, [(7500, ["a"]), (2500, ["b"])], ["a", "b"]) == {"a": 9000, "b": 3000}

    def test_discount_is_spread_in_proportion(self):
        assert items_split(8000, [(7500, ["a"]), (2500, ["b"])], ["a", "b"]) == {"a": 6000, "b": 2000}

    def test_no_per_item_rounding(self):
        # Three 1-kurus lines shared by a, b, c: exactly 1 kurus each, not 3 to "a".
        shares = items_split(3, [(1, []), (1, []), (1, [])], ["a", "b", "c"])
        assert shares == {"a": 1, "b": 1, "c": 1}

    def test_remainder_by_participant_order(self):
        assert items_split(100, [(100, ["b", "a", "c"])], ["a", "b", "c"]) == {"a": 34, "b": 33, "c": 33}

    def test_zero_amount_line_is_fine(self):
        assert items_split(100, [(100, ["a"]), (0, ["b"])], ["a", "b"]) == {"a": 100, "b": 0}

    @pytest.mark.parametrize(
        ("items", "participants", "message"),
        [
            ([], ["a"], "at least one item"),
            ([(100, ["x"])], ["a"], "not among the participants"),
            ([(100, ["a", "a"])], ["a"], "unique"),
            ([(-5, ["a"]), (105, ["a"])], ["a"], "must not be negative"),
            ([(0, ["a"])], ["a"], "more than 0"),
            ([(100, [])], [], "at least one participant"),
            ([(100, [])], ["a", "a"], "unique"),
        ],
    )
    def test_invalid(self, items, participants, message):
        with pytest.raises(ValueError, match=message):
            items_split(100, items, participants)

    def test_property_random(self):
        rng = random.Random(11)
        for _ in range(1500):
            people = [f"u{i}" for i in range(rng.randint(1, 6))]
            items = []
            for _ in range(rng.randint(1, 8)):
                who = rng.sample(people, rng.randint(0, len(people)))
                items.append((rng.randint(0, 50_000), who))
            if sum(a for a, _ in items) == 0:
                continue
            items_total = sum(a for a, _ in items)
            total = max(1, items_total + rng.randint(-items_total // 2, items_total // 2))
            shares = items_split(total, items, people)
            assert list(shares) == people
            assert sum(shares.values()) == total
            assert all(v >= 0 for v in shares.values())
            # With no tax/discount difference everyone is within 1 unit of their exact items.
            if total == items_total:
                for user in people:
                    exact = sum(
                        Decimal(a) / len(who or people) for a, who in items if user in (who or people)
                    )
                    assert abs(shares[user] - exact) < 1
