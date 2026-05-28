"""Registry repository placeholder."""

from datetime import date
from pathlib import Path

from fa_checker.domain.models import RegistryEntry
from fa_checker.registry.parser import parse_registry_xlsx


def load_registry_from_xlsx(
    path: str | Path,
    registry_source_url: str,
    snapshot_date: date | None = None,
) -> list[RegistryEntry]:
    """Load registry entries from a local XLSX snapshot."""
    return parse_registry_xlsx(path, registry_source_url, snapshot_date)


class RegistryRepository:
    """In-memory placeholder for registry entries."""

    def __init__(self, entries: list[RegistryEntry] | None = None) -> None:
        self._entries = entries or []

    def list_entries(self) -> list[RegistryEntry]:
        return list(self._entries)
