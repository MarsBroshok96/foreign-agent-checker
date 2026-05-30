from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.matching.author import check_article_author


def make_article(author: str | None) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        author=author,
        text="Текст статьи.",
    )


def make_entry(
    full_name: str,
    aliases: list[str] | None = None,
    entity_type: EntityType = EntityType.PERSON,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=full_name,
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_check_article_author_returns_no_author() -> None:
    result = check_article_author(make_article(None), [])

    assert result.status == "no_author"
    assert result.requires_human_review is False


def test_check_article_author_full_name_strong_match() -> None:
    result = check_article_author(
        make_article("Варламов Илья Александрович"),
        [make_entry("Варламов Илья Александрович")],
    )

    assert result.status == "strong_match"
    assert result.match_score == 1.0
    assert result.requires_human_review is False


def test_check_article_author_name_surname_strong_match() -> None:
    result = check_article_author(
        make_article("Илья Варламов"),
        [make_entry("Варламов Илья Александрович")],
    )

    assert result.status == "strong_match"


def test_check_article_author_surname_only_weak_match() -> None:
    result = check_article_author(
        make_article("Варламов"),
        [make_entry("Варламов Илья Александрович")],
    )

    assert result.status == "weak_match"
    assert result.match_score == 0.55
    assert result.requires_human_review is True


def test_check_article_author_one_token_pseudonym_is_weak() -> None:
    result = check_article_author(
        make_article("Белый"),
        [make_entry('Вайсман Анатолий Александрович "Белый"', aliases=["Белый"])],
    )

    assert result.status == "weak_match"
    assert result.entity_name == 'Вайсман Анатолий Александрович "Белый"'


def test_check_article_author_does_not_use_substring_matching() -> None:
    result = check_article_author(
        make_article("Белый Андрей"),
        [make_entry('Вайсман Анатолий Александрович "Белый"', aliases=["Белый"])],
    )

    assert result.status == "no_match"


def test_check_article_author_no_match() -> None:
    result = check_article_author(
        make_article("Редакция"),
        [make_entry("Варламов Илья Александрович")],
    )

    assert result.status == "no_match"
    assert result.requires_human_review is False


def test_check_article_author_strong_match_wins_over_weak_match() -> None:
    result = check_article_author(
        make_article("Илья Варламов"),
        [
            make_entry("Илья Иванович", aliases=["Илья"]),
            make_entry("Варламов Илья Александрович"),
        ],
    )

    assert result.status == "strong_match"
    assert result.entity_name == "Варламов Илья Александрович"
