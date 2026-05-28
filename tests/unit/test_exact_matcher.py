from fa_checker.domain.enums import EntityType, MatchType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.matching.exact import find_exact_matches


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_entry(
    full_name: str = "Варламов Илья Александрович",
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id="person-1",
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_exact_matcher_finds_full_person_name() -> None:
    article = make_article("В статье упоминается Варламов Илья Александрович.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].match_type == MatchType.EXACT
    assert matches[0].match_score == 1.0
    assert matches[0].requires_disambiguation is False
    assert matches[0].mention_text == "варламов илья александрович"


def test_exact_matcher_finds_name_surname_as_strong_match() -> None:
    article = make_article("Материал написал Илья Варламов.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].match_type == MatchType.EXACT
    assert matches[0].match_score == 1.0
    assert matches[0].requires_disambiguation is False
    assert matches[0].mention_text == "илья варламов"


def test_exact_matcher_marks_surname_only_as_weak_alias() -> None:
    article = make_article("В тексте встречается только Варламов.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].match_type == MatchType.ALIAS
    assert matches[0].match_score == 0.55
    assert matches[0].requires_disambiguation is True
    assert matches[0].mention_text == "варламов"


def test_exact_matcher_marks_surname_initials_as_weak_alias() -> None:
    article = make_article("В тексте указан Варламов И.А.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].match_type == MatchType.ALIAS
    assert matches[0].match_score == 0.55
    assert matches[0].requires_disambiguation is True
    assert matches[0].mention_text == "варламов и.а."


def test_exact_matcher_marks_initial_surname_as_weak_alias() -> None:
    article = make_article("В тексте указан И. Варламов.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].match_type == MatchType.ALIAS
    assert matches[0].match_score == 0.55
    assert matches[0].requires_disambiguation is True
    assert matches[0].mention_text == "и. варламов"


def test_exact_matcher_does_not_create_initial_match_without_dot() -> None:
    article = make_article("Варламов и его команда выпустили материал.")

    matches = find_exact_matches(article, [make_entry()])

    assert len(matches) == 1
    assert matches[0].mention_text == "варламов"
    assert "." not in matches[0].mention_text


def test_exact_matcher_does_not_match_alias_inside_larger_word() -> None:
    article = make_article("В тексте есть слово антимедуза.")
    entry = make_entry("Медуза", entity_type=EntityType.MEDIA)

    assert find_exact_matches(article, [entry]) == []


def test_exact_matcher_returns_empty_list_when_no_aliases_found() -> None:
    article = make_article("В тексте нет нужных имен.")

    assert find_exact_matches(article, [make_entry()]) == []


def test_exact_matcher_does_not_duplicate_same_alias_at_same_position() -> None:
    article = make_article("В тексте есть Илья Варламов.")
    entry = make_entry(aliases=["Илья Варламов", "  Илья\u00a0Варламов  "])

    matches = find_exact_matches(article, [entry])

    assert len(matches) == 1
    assert matches[0].mention_text == "илья варламов"
    assert matches[0].evidence[0].text == "илья варламов"
    assert matches[0].evidence[0].start == matches[0].mention_start
    assert matches[0].evidence[0].end == matches[0].mention_end
