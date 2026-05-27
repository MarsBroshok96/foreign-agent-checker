"""Rambler article loading adapter placeholder."""

from fa_checker.domain.models import Article


class RamblerLoader:
    """Placeholder loader for Rambler articles."""

    def load(self, url: str) -> Article:
        raise NotImplementedError("Rambler loading is not implemented in the scaffold phase.")

