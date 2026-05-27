"""Deterministic article text normalization utilities."""

import re

_WHITESPACE_RE = re.compile(r"\s+")
_QUOTE_TRANSLATION = str.maketrans(
    {
        "«": '"',
        "»": '"',
        "„": '"',
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
    }
)
_DASH_TRANSLATION = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
    }
)


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace while preserving non-whitespace characters."""
    return _WHITESPACE_RE.sub(" ", text.replace("\u00a0", " ")).strip()


def normalize_quotes_and_dashes(text: str) -> str:
    """Normalize common typographic quotes and dashes deterministically."""
    return text.translate(_QUOTE_TRANSLATION).translate(_DASH_TRANSLATION)


def normalize_for_display(text: str) -> str:
    """Normalize evidence text for display while preserving casing and ё."""
    return normalize_whitespace(text)


def normalize_for_matching(text: str) -> str:
    """Normalize text for deterministic matching."""
    normalized = normalize_quotes_and_dashes(text)
    normalized = normalize_whitespace(normalized)
    return normalized.lower().replace("ё", "е")


def normalize_article_text(text: str) -> str:
    """Backward-compatible alias for display-oriented normalization."""
    return normalize_for_display(text)
