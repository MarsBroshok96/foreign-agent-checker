"""Exact matching placeholder."""

from fa_checker.domain.models import Article, CandidateMatch, RegistryEntry


def find_exact_matches(article: Article, entries: list[RegistryEntry]) -> list[CandidateMatch]:
    raise NotImplementedError("Exact matching is not implemented in the scaffold phase.")

