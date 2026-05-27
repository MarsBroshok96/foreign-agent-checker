import pytest

from fa_checker.article.context import get_context_window
from fa_checker.domain.enums import EvidenceSource


def test_get_context_window_for_middle_mention() -> None:
    text = "alpha beta gamma delta epsilon"
    mention_start = text.index("gamma")
    mention_end = mention_start + len("gamma")

    fragment = get_context_window(text, mention_start, mention_end, window_size=6)

    assert fragment.source == EvidenceSource.ARTICLE_TEXT
    assert fragment.text == "beta gamma delta"
    assert fragment.start == 5
    assert fragment.end == 22


def test_get_context_window_near_beginning() -> None:
    text = "alpha beta gamma"
    mention_start = text.index("alpha")
    mention_end = mention_start + len("alpha")

    fragment = get_context_window(text, mention_start, mention_end, window_size=5)

    assert fragment.text == "alpha beta"
    assert fragment.start == 0
    assert fragment.end == 10


def test_get_context_window_near_end() -> None:
    text = "alpha beta gamma"
    mention_start = text.index("gamma")
    mention_end = mention_start + len("gamma")

    fragment = get_context_window(text, mention_start, mention_end, window_size=5)

    assert fragment.text == "beta gamma"
    assert fragment.start == 6
    assert fragment.end == len(text)


@pytest.mark.parametrize(
    ("mention_start", "mention_end", "window_size"),
    [
        (-1, 2, 5),
        (3, 3, 5),
        (4, 3, 5),
        (0, 99, 5),
        (0, 1, -1),
    ],
)
def test_get_context_window_rejects_invalid_indexes(
    mention_start: int,
    mention_end: int,
    window_size: int,
) -> None:
    with pytest.raises(ValueError):
        get_context_window("alpha beta", mention_start, mention_end, window_size=window_size)


def test_get_context_window_normalizes_display_fragment() -> None:
    text = "alpha\n\nbeta\u00a0\u00a0gamma"
    mention_start = text.index("beta")
    mention_end = mention_start + len("beta")

    fragment = get_context_window(text, mention_start, mention_end, window_size=len(text))

    assert fragment.text == "alpha beta gamma"
    assert fragment.start == 0
    assert fragment.end == len(text)
