"""Pick the reply language from the user's message, in code.

Small models do not follow "answer in the user's language" reliably once the instructions,
tool results and category names mix Turkish and English, so the API detects the language
and adds a one-line note to the message the agents see.
"""

from __future__ import annotations

import re

_TURKISH_LETTERS = set("çğıöşüÇĞİÖŞÜ")
# Common Turkish words that are written without Turkish letters, so ASCII-only messages
# ("bu ay ne kadar harcadim") are still recognised.
_TURKISH_WORD_LIST = (
    "bu ne ve mi mu kadar bana ben beni benim icin ile ay ayki hafta yil toplam harcadim "
    "harcama harcamalar odedi odedim kaydet kac nedir nasil neden var yok goster grafik "
    "butce ev kira fatura market borclu kim kime lira tl"
)
_TURKISH_WORDS = frozenset(_TURKISH_WORD_LIST.split())
_WORD = re.compile(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+")


def detect_language(text: str) -> str:
    """'tr' or 'en'. Turkish letters decide at once; otherwise two Turkish words do."""
    if any(ch in _TURKISH_LETTERS for ch in text):
        return "tr"
    words = [w.lower() for w in _WORD.findall(text)]
    hits = sum(1 for w in words if w in _TURKISH_WORDS)
    return "tr" if hits >= 2 or (hits == 1 and len(words) <= 2) else "en"


def reply_language_note(text: str) -> str:
    """The note appended to the user's message for the agents."""
    if detect_language(text) == "tr":
        return "(Kasa: reply in Turkish.)"
    return "(Kasa: reply in English.)"
