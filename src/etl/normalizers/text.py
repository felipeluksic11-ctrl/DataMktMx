"""Text normalization utilities used across all normalizers.

All functions are pure — no side effects, no DB access.
"""

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Remove accents: 'México' → 'Mexico'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(text: str | None) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    text = strip_accents(text.strip().lower())
    text = re.sub(r"\s+", " ", text)
    return text


def extract_zip_code(text: str) -> str | None:
    """Extract 5-digit Mexican zip code from text."""
    match = re.search(r"\b(\d{5})\b", text)
    return match.group(1) if match else None


def title_case_mx(text: str) -> str:
    """Title case respecting Mexican conventions (de, del, la, las, los, etc.)."""
    minor = {"de", "del", "la", "las", "los", "el", "en", "y", "e", "o", "al", "por"}
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in minor:
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return " ".join(result)
