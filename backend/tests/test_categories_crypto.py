import datetime as dt
import time

import pytest

from app.config import get_settings
from app.services import crypto
from app.services.categories import CATEGORIES, normalize_category
from app.services.inbox import ParsedExpense, ParsedItem
from app.services.statements import StatementLine, line_ref


class TestCategories:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("groceries", "groceries"),
            ("Market", "groceries"),
            ("SÜPERMARKET", "groceries"),
            ("yemek", "food"),
            ("Ulaşım", "transport"),
            ("ULASIM", "transport"),
            ("fatura", "utilities"),
            ("bills", "utilities"),  # Sprint 1 name
            ("Kira", "rent"),
            ("EĞİTİM", "education"),
            ("netflix", "subscriptions"),
            ("something odd", "other"),
            ("  ", None),
            (None, None),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_category(raw) == expected

    def test_every_category_maps_to_itself(self):
        assert all(normalize_category(c) == c for c in CATEGORIES)
        assert len(CATEGORIES) == 12


class TestCrypto:
    def test_round_trip_and_key_required(self):
        key = crypto.generate_key()
        token = crypto.encrypt("1//refresh-token-ş", key=key)
        assert "refresh" not in token
        assert crypto.decrypt(token, key=key) == "1//refresh-token-ş"
        with pytest.raises(crypto.CryptoError):
            crypto.decrypt(token, key=crypto.generate_key())
        with pytest.raises(crypto.CryptoError):
            crypto.encrypt("x", key="")
        with pytest.raises(crypto.CryptoError):
            crypto.encrypt("x", key="not-a-fernet-key")

    def test_max_age(self, monkeypatch):
        key = crypto.generate_key()
        token = crypto.encrypt("state", key=key)
        assert crypto.decrypt(token, key=key, max_age_seconds=60) == "state"
        real = time.time
        monkeypatch.setattr(time, "time", lambda: real() + 120)
        with pytest.raises(crypto.CryptoError):
            crypto.decrypt(token, key=key, max_age_seconds=60)

    def test_uses_settings_key(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "token_encryption_key", crypto.generate_key())
        assert crypto.decrypt(crypto.encrypt("abc")) == "abc"


class TestImportContracts:
    def test_parsed_expense_json_round_trip(self):
        parsed = ParsedExpense(
            merchant="Şok Market",
            total="57.50",
            currency="TRY",
            expense_date=dt.date(2026, 10, 2),
            category="market",
            items=[ParsedItem("Ayran", "17.50"), ParsedItem("Simit", "40.00", "2")],
        )
        again = ParsedExpense.from_json(parsed.to_json())
        assert again == parsed
        assert "Şok" in parsed.to_json()  # stored as readable UTF-8
        data = again.to_input()
        assert data.total == "57.50" and [i.amount for i in data.items] == ["17.50", "40.00"]

    def test_statement_line_ref_is_stable_and_distinguishes_repeats(self):
        line = StatementLine(dt.date(2026, 10, 1), "STARBUCKS  KADIKOY", "85.00")
        same_text = StatementLine(dt.date(2026, 10, 1), "starbucks kadikoy", "85.00")
        assert line_ref(line, 0) == line_ref(same_text, 0)
        assert line_ref(line, 0) != line_ref(line, 1)
        assert line_ref(line, 0).startswith("stmt:") and len(line_ref(line, 0)) <= 200
