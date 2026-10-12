"""The one fixed list of expense categories, plus a normaliser for whatever people type.

Every expense-creating path stores `normalize_category(raw)`, so the DB only ever holds
values from CATEGORIES (or NULL when no category was given). Reports, budgets and the
frontend can rely on that.
"""

from __future__ import annotations

CATEGORIES: tuple[str, ...] = (
    "groceries",
    "food",
    "transport",
    "rent",
    "utilities",
    "subscriptions",
    "shopping",
    "health",
    "education",
    "entertainment",
    "travel",
    "other",
)

# Synonyms (Turkish and English) -> category. Keys are compared after `_fold`.
_SYNONYMS: dict[str, str] = {
    # groceries
    "market": "groceries", "supermarket": "groceries", "süpermarket": "groceries",
    "bakkal": "groceries", "manav": "groceries", "kasap": "groceries", "gıda": "groceries",
    "grocery": "groceries", "migros": "groceries", "bim": "groceries", "a101": "groceries",
    "şok": "groceries", "carrefoursa": "groceries",
    # food
    "yemek": "food", "restoran": "food", "restaurant": "food", "kafe": "food", "cafe": "food",
    "kahve": "food", "coffee": "food", "lokanta": "food", "yemeksepeti": "food", "getir": "food",
    "dining": "food", "fast food": "food",
    # transport
    "ulaşım": "transport", "ulasim": "transport", "taksi": "transport", "taxi": "transport",
    "otobüs": "transport", "metro": "transport", "istanbulkart": "transport", "benzin": "transport",
    "akaryakıt": "transport", "yakıt": "transport", "fuel": "transport", "uber": "transport",
    "bitaksi": "transport", "dolmuş": "transport", "vapur": "transport",
    # rent
    "kira": "rent", "aidat": "rent",
    # utilities
    "fatura": "utilities", "faturalar": "utilities", "bills": "utilities", "bill": "utilities",
    "elektrik": "utilities", "su": "utilities", "doğalgaz": "utilities", "dogalgaz": "utilities",
    "internet": "utilities", "telefon": "utilities", "electricity": "utilities", "water": "utilities",
    "gas": "utilities", "phone": "utilities",
    # subscriptions
    "abonelik": "subscriptions", "subscription": "subscriptions", "netflix": "subscriptions",
    "spotify": "subscriptions", "youtube premium": "subscriptions", "icloud": "subscriptions",
    # shopping
    "alışveriş": "shopping", "giyim": "shopping", "clothes": "shopping", "clothing": "shopping",
    "elektronik": "shopping", "electronics": "shopping", "trendyol": "shopping",
    "hepsiburada": "shopping", "amazon": "shopping",
    # health
    "sağlık": "health", "eczane": "health", "ilaç": "health", "pharmacy": "health",
    "doktor": "health", "hastane": "health", "medical": "health", "spor": "health", "gym": "health",
    # education
    "eğitim": "education", "okul": "education", "kitap": "education", "kırtasiye": "education",
    "kurs": "education", "books": "education", "book": "education", "school": "education",
    "tuition": "education", "harç": "education",
    # entertainment
    "eğlence": "entertainment", "sinema": "entertainment", "cinema": "entertainment",
    "konser": "entertainment", "concert": "entertainment", "oyun": "entertainment",
    "games": "entertainment", "tiyatro": "entertainment", "bar": "entertainment",
    # travel
    "seyahat": "travel", "tatil": "travel", "otel": "travel", "hotel": "travel", "uçak": "travel",
    "flight": "travel", "holiday": "travel", "vacation": "travel",
    # other
    "diğer": "other", "misc": "other", "miscellaneous": "other",
}  # fmt: skip

_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _fold(value: str) -> str:
    """Lowercase with Turkish rules (İ->i, I->ı), then strip Turkish letters to ASCII."""
    lowered = value.strip().replace("İ", "i").replace("I", "ı").lower()
    return " ".join(lowered.translate(_ASCII).split())


_LOOKUP: dict[str, str] = {_fold(c): c for c in CATEGORIES} | {_fold(k): v for k, v in _SYNONYMS.items()}


def fold_text(value: str) -> str:
    """Public alias of the folding used for lookups (Turkish-aware lowercase, ASCII)."""
    return _fold(value)


def is_known_category(raw: str) -> bool:
    """True when `raw` is a category or a known synonym (so it won't fall back to "other")."""
    return _fold(raw) in _LOOKUP


def normalize_category(raw: str | None) -> str | None:
    """Map free text to a category from CATEGORIES.

    None or blank stays None (uncategorised); anything unrecognised becomes "other".

    >>> normalize_category("Market"), normalize_category("ULAŞIM"), normalize_category("kira")
    ('groceries', 'transport', 'rent')
    """
    if raw is None or not raw.strip():
        return None
    return _LOOKUP.get(_fold(raw), "other")
