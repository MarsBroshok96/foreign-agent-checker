"""Fuzzy matching placeholder."""

from fa_checker.domain.models import Article, CandidateMatch, RegistryEntry


def find_fuzzy_matches(article: Article, entries: list[RegistryEntry]) -> list[CandidateMatch]:
    raise NotImplementedError("Fuzzy matching is not implemented in the scaffold phase.")

