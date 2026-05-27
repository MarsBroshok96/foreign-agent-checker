from fa_checker.article.normalizer import (
    normalize_for_display,
    normalize_for_matching,
    normalize_quotes_and_dashes,
    normalize_whitespace,
)


def test_normalize_whitespace_collapses_spaces_and_newlines() -> None:
    assert normalize_whitespace("  Alpha   beta\n\n gamma\t delta  ") == "Alpha beta gamma delta"


def test_normalize_whitespace_replaces_non_breaking_spaces() -> None:
    assert normalize_whitespace("Alpha\u00a0\u00a0beta") == "Alpha beta"


def test_normalize_for_matching_lowercases() -> None:
    assert normalize_for_matching("МИХАИЛ Example") == "михаил example"


def test_normalize_for_matching_replaces_yo() -> None:
    assert normalize_for_matching("Семён и Ёлка") == "семен и елка"


def test_normalize_for_matching_normalizes_dashes_and_quotes() -> None:
    text = "«Альфа» — “Бета” – минус − штрих"

    assert normalize_for_matching(text) == '"альфа" - "бета" - минус - штрих'


def test_normalize_quotes_and_dashes_is_deterministic() -> None:
    assert normalize_quotes_and_dashes("„А“ — 'Б'") == "\"А\" - 'Б'"


def test_normalize_for_display_preserves_casing_and_yo() -> None:
    assert normalize_for_display("  Ёлка\nИ   Река  ") == "Ёлка И Река"

