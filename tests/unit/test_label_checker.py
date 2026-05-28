from fa_checker.domain.enums import EntityType, LabelQuality, MatchType
from fa_checker.domain.models import Article, CandidateMatch, RegistryEntry
from fa_checker.matching.labels import check_label


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_match(
    article_text: str,
    mention_text: str = "Илья Варламов",
    mention_start: int | None = None,
    mention_end: int | None = None,
) -> CandidateMatch:
    if mention_start is None and mention_end is None and mention_text in article_text:
        mention_start = article_text.index(mention_text)
        mention_end = mention_start + len(mention_text)

    registry_entry = RegistryEntry(
        full_name="Варламов Илья Александрович",
        entity_type=EntityType.PERSON,
        normalized_name="варламов илья александрович",
        registry_source_url="https://minjust.gov.ru/registry",
    )
    return CandidateMatch(
        mention_text=mention_text,
        mention_start=mention_start,
        mention_end=mention_end,
        registry_entry=registry_entry,
        match_type=MatchType.EXACT,
        match_score=1.0,
        evidence=[],
        requires_disambiguation=False,
    )


def test_check_label_finds_nearby_exact_label_after_mention() -> None:
    text = "Илья Варламов, признан иностранным агентом, прокомментировал ситуацию."
    article = make_article(text)

    result = check_label(article, make_match(text))

    assert result.label_found is True
    assert result.label_quality == LabelQuality.EXACT
    assert result.label_fragment is not None
    assert "признан иностранным агентом" in result.label_fragment
    assert result.label_distance is not None


def test_check_label_finds_nearby_exact_label_before_mention() -> None:
    text = "Признанный иностранным агентом Илья Варламов прокомментировал ситуацию."
    article = make_article(text)

    result = check_label(article, make_match(text))

    assert result.label_found is True
    assert result.label_quality == LabelQuality.EXACT
    assert result.label_fragment is not None
    assert "Признанный иностранным агентом" in result.label_fragment


def test_check_label_handles_yo_normalization() -> None:
    text = "Илья Варламов внесён в реестр иностранных агентов."
    article = make_article(text)

    result = check_label(article, make_match(text))

    assert result.label_found is True
    assert result.label_quality == LabelQuality.EXACT
    assert result.label_fragment is not None
    assert "внесён в реестр иностранных агентов" in result.label_fragment


def test_check_label_finds_article_level_weak_label_outside_near_window() -> None:
    text = "Илья Варламов начал комментарий. " + ("без метки " * 80) + "иноагент."
    article = make_article(text)

    result = check_label(article, make_match(text), near_window_size=20)

    assert result.label_found is True
    assert result.label_quality == LabelQuality.WEAK
    assert result.label_fragment is not None
    assert "иноагент" in result.label_fragment
    assert result.label_distance is None


def test_check_label_returns_absent_when_no_label_exists() -> None:
    text = "Илья Варламов прокомментировал ситуацию."
    article = make_article(text)

    result = check_label(article, make_match(text))

    assert result.label_found is False
    assert result.label_quality == LabelQuality.ABSENT
    assert result.label_fragment is None
    assert result.label_distance is None


def test_check_label_without_positions_checks_whole_article_as_weak() -> None:
    text = "Материал содержит пометку: иностранный агент."
    article = make_article(text)
    match = make_match(text, mention_start=None, mention_end=None)

    result = check_label(article, match)

    assert result.label_found is True
    assert result.label_quality == LabelQuality.WEAK
    assert result.label_distance is None


def test_check_label_with_invalid_positions_checks_whole_article_as_weak() -> None:
    text = "Материал содержит пометку: иностранный агент."
    article = make_article(text)
    match = make_match(text, mention_start=999, mention_end=1000)

    result = check_label(article, match)

    assert result.label_found is True
    assert result.label_quality == LabelQuality.WEAK
    assert result.label_distance is None


def test_check_label_does_not_match_label_inside_larger_word() -> None:
    text = "Илья Варламов упомянул искусственный токен супериноагентство."
    article = make_article(text)

    result = check_label(article, make_match(text))

    assert result.label_found is False
    assert result.label_quality == LabelQuality.ABSENT

