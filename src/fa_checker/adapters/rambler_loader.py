"""Rambler-specific article loading adapter."""

from fa_checker.adapters.http_client import fetch_text
from fa_checker.article.extractor import extract_article_from_html
from fa_checker.article.metadata import is_rambler_url
from fa_checker.domain.models import Article


def load_rambler_article(url: str) -> Article:
    """Fetch and extract a Rambler article by URL."""
    if not is_rambler_url(url):
        msg = "URL must belong to rambler.ru or one of its subdomains."
        raise ValueError(msg)
    html = fetch_text(url)
    return extract_article_from_html(url, html)


class RamblerLoader:
    """Compatibility wrapper around load_rambler_article."""

    def load(self, url: str) -> Article:
        return load_rambler_article(url)
