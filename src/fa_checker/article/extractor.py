"""Article extraction placeholder."""

from fa_checker.domain.models import Article


class ArticleExtractor:
    """Placeholder extractor for article HTML."""

    def extract(self, url: str, html: str) -> Article:
        raise NotImplementedError("Article extraction is not implemented in the scaffold phase.")

