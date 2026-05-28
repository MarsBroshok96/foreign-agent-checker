import pytest

from fa_checker.adapters import rambler_loader
from fa_checker.adapters.rambler_loader import load_rambler_article
from fa_checker.domain.models import Article


def test_load_rambler_article_rejects_non_rambler_url() -> None:
    with pytest.raises(ValueError, match="rambler.ru"):
        load_rambler_article("https://example.org/news")


def test_load_rambler_article_fetches_and_extracts(monkeypatch) -> None:
    calls = {}

    def fake_fetch_text(url: str) -> str:
        calls["fetch_url"] = url
        return "<html>article</html>"

    def fake_extract_article_from_html(url: str, html: str) -> Article:
        calls["extract_url"] = url
        calls["html"] = html
        return Article(
            url=url,
            source_domain="www.rambler.ru",
            title="Title",
            text="Article text.",
            links=[],
        )

    monkeypatch.setattr(rambler_loader, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(
        rambler_loader,
        "extract_article_from_html",
        fake_extract_article_from_html,
    )

    article = load_rambler_article("https://www.rambler.ru/news/example")

    assert isinstance(article, Article)
    assert calls == {
        "fetch_url": "https://www.rambler.ru/news/example",
        "extract_url": "https://www.rambler.ru/news/example",
        "html": "<html>article</html>",
    }
