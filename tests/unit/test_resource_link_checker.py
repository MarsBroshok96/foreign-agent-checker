from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.matching.resource_links import (
    find_resource_link_matches,
    normalize_resource_url,
)


def make_article(links: list[str]) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text="Текст статьи.",
        links=links,
    )


def make_entry(
    full_name: str,
    resource_urls,
    registry_id: str | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=registry_id or full_name,
        full_name=full_name,
        entity_type=EntityType.PROJECT,
        normalized_name=full_name.lower(),
        registry_source_url="https://minjust.gov.ru/registry",
        raw_fields={"resource_urls": resource_urls},
    )


def test_normalize_resource_url_matches_trailing_slash_and_ignores_fragment() -> None:
    assert normalize_resource_url("HTTPS://Example.org/path/#part") == (
        "https://example.org/path"
    )


def test_find_resource_link_matches_exact_same_full_url() -> None:
    matches = find_resource_link_matches(
        make_article(["https://posle.media/about"]),
        [make_entry("Проект «После»", ["https://posle.media/about"])],
    )

    assert len(matches) == 1
    assert matches[0].entity_name == "Проект «После»"


def test_find_resource_link_matches_trailing_slash() -> None:
    matches = find_resource_link_matches(
        make_article(["https://posle.media/about/"]),
        [make_entry("Проект «После»", ["https://posle.media/about"])],
    )

    assert len(matches) == 1


def test_find_resource_link_matches_fragment_is_ignored() -> None:
    matches = find_resource_link_matches(
        make_article(["https://posle.media/about#team"]),
        [make_entry("Проект «После»", ["https://posle.media/about"])],
    )

    assert len(matches) == 1


def test_find_resource_link_matches_does_not_match_domain_only() -> None:
    matches = find_resource_link_matches(
        make_article(["https://posle.media/other"]),
        [make_entry("Проект «После»", ["https://posle.media/about"])],
    )

    assert matches == []


def test_find_resource_link_matches_does_not_match_generic_platform_domain() -> None:
    matches = find_resource_link_matches(
        make_article(["https://t.me/other"]),
        [make_entry("Проект «После»", ["https://t.me/poslemedia"])],
    )

    assert matches == []


def test_find_resource_link_matches_multiple_links_and_entries() -> None:
    matches = find_resource_link_matches(
        make_article(["https://a.example/page", "https://b.example/page"]),
        [
            make_entry("Первый проект", ["https://a.example/page"]),
            make_entry("Второй проект", ["https://b.example/page"]),
        ],
    )

    assert [match.entity_name for match in matches] == [
        "Первый проект",
        "Второй проект",
    ]


def test_find_resource_link_matches_deduplicates_duplicate_links() -> None:
    matches = find_resource_link_matches(
        make_article(["https://a.example/page", "https://a.example/page/"]),
        [make_entry("Первый проект", "https://a.example/page; https://a.example/page/")],
    )

    assert len(matches) == 1


def test_find_resource_link_matches_ignores_invalid_registry_urls() -> None:
    matches = find_resource_link_matches(
        make_article(["https://a.example/page"]),
        [make_entry("Первый проект", ["not-a-url"])],
    )

    assert matches == []
