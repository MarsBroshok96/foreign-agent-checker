"""Deterministic foreign-agent label checking."""

from fa_checker.article.normalizer import normalize_for_display, normalize_for_matching
from fa_checker.domain.enums import LabelQuality
from fa_checker.domain.models import Article, CandidateMatch, LabelCheckResult

LABEL_PHRASES = [
    "иностранный агент",
    "иностранным агентом",
    "иностранного агента",
    "иноагент",
    "иноагентом",
    "признан иностранным агентом",
    "признана иностранным агентом",
    "признано иностранным агентом",
    "признанный иностранным агентом",
    "внесен в реестр иностранных агентов",
    "внесён в реестр иностранных агентов",
    "включен в реестр иностранных агентов",
    "включён в реестр иностранных агентов",
]

NORMALIZED_LABEL_PHRASES = tuple(normalize_for_matching(phrase) for phrase in LABEL_PHRASES)


def check_label(
    article: Article,
    match: CandidateMatch,
    near_window_size: int = 300,
) -> LabelCheckResult:
    """Check whether a foreign-agent label appears near a match or in the article."""
    if near_window_size < 0:
        msg = "near_window_size must be greater than or equal to 0."
        raise ValueError(msg)

    if _has_valid_match_positions(article, match):
        near_result = _check_near_window(article, match, near_window_size)
        if near_result is not None:
            return near_result

    whole_article_match = _find_first_label(normalize_for_matching(article.text))
    if whole_article_match is not None:
        _, label_start = whole_article_match
        return LabelCheckResult(
            label_found=True,
            label_fragment=_make_display_fragment(article.text, label_start),
            label_distance=None,
            label_quality=LabelQuality.WEAK,
        )

    return LabelCheckResult(
        label_found=False,
        label_fragment=None,
        label_distance=None,
        label_quality=LabelQuality.ABSENT,
    )


def _has_valid_match_positions(article: Article, match: CandidateMatch) -> bool:
    if match.mention_start is None or match.mention_end is None:
        return False
    return 0 <= match.mention_start < match.mention_end <= len(article.text)


def _check_near_window(
    article: Article,
    match: CandidateMatch,
    near_window_size: int,
) -> LabelCheckResult | None:
    if match.mention_start is None or match.mention_end is None:
        return None

    window_start = max(0, match.mention_start - near_window_size)
    window_end = min(len(article.text), match.mention_end + near_window_size)
    window_text = article.text[window_start:window_end]
    label_match = _find_first_label(normalize_for_matching(window_text))
    if label_match is None:
        return None

    phrase, label_start = label_match
    approximate_article_label_start = window_start + label_start
    return LabelCheckResult(
        label_found=True,
        label_fragment=_make_display_fragment(window_text, label_start, label_start + len(phrase)),
        label_distance=abs(approximate_article_label_start - match.mention_start),
        label_quality=LabelQuality.EXACT,
    )


def _find_first_label(text: str) -> tuple[str, int] | None:
    first_match: tuple[str, int] | None = None
    for phrase in NORMALIZED_LABEL_PHRASES:
        position = _find_phrase_with_boundaries(text, phrase)
        if position is None:
            continue
        if first_match is None or position < first_match[1]:
            first_match = (phrase, position)
    return first_match


def _find_phrase_with_boundaries(text: str, phrase: str) -> int | None:
    start = 0
    while True:
        position = text.find(phrase, start)
        if position == -1:
            return None
        end = position + len(phrase)
        if _has_text_boundaries(text, position, end):
            return position
        start = position + 1


def _has_text_boundaries(text: str, start: int, end: int) -> bool:
    before_is_boundary = start == 0 or not text[start - 1].isalnum()
    after_is_boundary = end == len(text) or not text[end].isalnum()
    return before_is_boundary and after_is_boundary


def _make_display_fragment(
    text: str,
    label_start: int,
    label_end: int | None = None,
    window_size: int = 120,
) -> str:
    label_end = label_start if label_end is None else label_end
    fragment_start = max(0, label_start - window_size)
    fragment_end = min(len(text), label_end + window_size)
    return normalize_for_display(text[fragment_start:fragment_end])
