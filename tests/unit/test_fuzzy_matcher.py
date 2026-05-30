from fa_checker.domain.enums import EntityType, MatchType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.matching.exact import find_exact_matches
from fa_checker.matching.fuzzy import find_fuzzy_person_matches


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_entry(
    full_name: str,
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=full_name,
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_fuzzy_catches_surname_case() -> None:
    matches = find_fuzzy_person_matches(
        make_article("Слова Варламова вызвали дискуссию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert len(matches) == 1
    assert matches[0].registry_entry.full_name == "Варламов Илья Александрович"
    assert matches[0].match_type == MatchType.FUZZY
    assert matches[0].requires_disambiguation is True


def test_fuzzy_catches_instrumental_surname() -> None:
    matches = find_fuzzy_person_matches(
        make_article("С Венедиктовым обсудили ситуацию."),
        [make_entry("Венедиктов Алексей Алексеевич")],
    )

    assert len(matches) == 1
    assert matches[0].mention_text == "венедиктовым"


def test_fuzzy_catches_multi_token_case() -> None:
    matches = find_fuzzy_person_matches(
        make_article("Илью Варламова спросили о проекте."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert len(matches) == 1
    assert matches[0].mention_text == "илью варламова"


def test_fuzzy_skips_non_person_entries() -> None:
    matches = find_fuzzy_person_matches(
        make_article("После дождя случилось событие."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )

    assert matches == []


def test_fuzzy_skips_short_one_token_person_aliases() -> None:
    matches = find_fuzzy_person_matches(
        make_article("Белый дом сделал заявление."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert matches == []


def test_fuzzy_does_not_duplicate_existing_exact_match() -> None:
    article = make_article("Илья Варламов прокомментировал ситуацию.")
    entries = [make_entry("Варламов Илья Александрович")]
    exact_matches = find_exact_matches(article, entries)

    matches = find_fuzzy_person_matches(
        article,
        entries,
        existing_matches=exact_matches,
    )

    assert matches == []


def test_fuzzy_score_is_between_zero_and_one() -> None:
    matches = find_fuzzy_person_matches(
        make_article("Слова Варламова вызвали дискуссию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert 0 <= matches[0].match_score <= 1


def test_fuzzy_evidence_contains_surrounding_context() -> None:
    matches = find_fuzzy_person_matches(
        make_article("До этого слова Варламова вызвали широкую дискуссию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert matches[0].evidence
    assert "слова" in matches[0].evidence[0].text.lower()
    assert "дискуссию" in matches[0].evidence[0].text.lower()
