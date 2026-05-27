"""Context-window extraction for article evidence."""

from fa_checker.article.normalizer import normalize_for_display
from fa_checker.domain.enums import EvidenceSource
from fa_checker.domain.models import EvidenceFragment


def get_context_window(
    text: str,
    mention_start: int,
    mention_end: int,
    window_size: int = 160,
) -> EvidenceFragment:
    """Return a normalized display fragment around known mention indexes."""
    if window_size < 0:
        msg = "window_size must be greater than or equal to 0."
        raise ValueError(msg)
    if mention_start < 0 or mention_end < 0:
        msg = "mention indexes must be greater than or equal to 0."
        raise ValueError(msg)
    if mention_start >= mention_end:
        msg = "mention_start must be less than mention_end."
        raise ValueError(msg)
    if mention_end > len(text):
        msg = "mention indexes must be inside the text."
        raise ValueError(msg)

    fragment_start = max(0, mention_start - window_size)
    fragment_end = min(len(text), mention_end + window_size)
    fragment_text = normalize_for_display(text[fragment_start:fragment_end])

    return EvidenceFragment(
        source=EvidenceSource.ARTICLE_TEXT,
        text=fragment_text,
        start=fragment_start,
        end=fragment_end,
    )
