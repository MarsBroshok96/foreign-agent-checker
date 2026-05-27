"""Author matching placeholder."""

from fa_checker.domain.models import Article, CandidateMatch, RegistryEntry


def check_author(article: Article, entries: list[RegistryEntry]) -> list[CandidateMatch]:
    raise NotImplementedError("Author checking is not implemented in the scaffold phase.")

