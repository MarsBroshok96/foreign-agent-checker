import pytest

from fa_checker.article.metadata import extract_source_domain, is_rambler_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.rambler.ru/news/example",
        "https://rambler.ru/example",
        "http://news.rambler.ru/example",
    ],
)
def test_is_rambler_url_accepts_rambler_hosts(url: str) -> None:
    assert is_rambler_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://rambler.ru.evil.com/example",
        "not-a-url",
        "",
    ],
)
def test_is_rambler_url_rejects_invalid_or_lookalike_hosts(url: str) -> None:
    assert is_rambler_url(url) is False


def test_extract_source_domain_returns_normalized_hostname() -> None:
    assert extract_source_domain("HTTPS://News.Rambler.Ru/example") == "news.rambler.ru"


def test_extract_source_domain_rejects_invalid_url() -> None:
    with pytest.raises(ValueError, match="absolute http or https URL"):
        extract_source_domain("not-a-url")

