"""Registry alias builder placeholder."""

from fa_checker.domain.models import RegistryEntry


def build_aliases(entry: RegistryEntry) -> list[str]:
    """Return configured aliases until deterministic alias generation is implemented."""
    return list(entry.aliases)

