"""Registry repository placeholder."""

from fa_checker.domain.models import RegistryEntry


class RegistryRepository:
    """In-memory placeholder for registry entries."""

    def __init__(self, entries: list[RegistryEntry] | None = None) -> None:
        self._entries = entries or []

    def list_entries(self) -> list[RegistryEntry]:
        return list(self._entries)

