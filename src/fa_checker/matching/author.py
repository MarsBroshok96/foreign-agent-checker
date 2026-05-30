"""Deterministic article-author checks against registry aliases."""

from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.models import Article, AuthorCheckResult, RegistryEntry
from fa_checker.registry.alias_builder import build_aliases


def check_article_author(
    article: Article,
    registry_entries: list[RegistryEntry],
) -> AuthorCheckResult:
    """Compare article author exactly against strong and weak registry aliases."""
    if article.author is None or not article.author.strip():
        return AuthorCheckResult(
            author_name=article.author,
            status="no_author",
            requires_human_review=False,
            rationale="Article author is not available.",
        )

    normalized_author = normalize_for_matching(article.author)
    weak_match: AuthorCheckResult | None = None

    for entry in registry_entries:
        aliases = build_aliases(entry)
        if normalized_author in aliases.strong:
            return AuthorCheckResult(
                author_name=article.author,
                status="strong_match",
                registry_id=entry.registry_id,
                entity_name=entry.full_name,
                match_type="exact",
                match_score=1.0,
                requires_human_review=False,
                rationale="Article author matches a strong registry alias.",
            )
        if normalized_author in aliases.weak and weak_match is None:
            weak_match = AuthorCheckResult(
                author_name=article.author,
                status="weak_match",
                registry_id=entry.registry_id,
                entity_name=entry.full_name,
                match_type="alias",
                match_score=0.55,
                requires_human_review=True,
                rationale=(
                    "Article author matches a weak registry alias; "
                    "human review is required."
                ),
            )

    if weak_match is not None:
        return weak_match

    return AuthorCheckResult(
        author_name=article.author,
        status="no_match",
        requires_human_review=False,
        rationale="Article author was not found in registry aliases.",
    )
