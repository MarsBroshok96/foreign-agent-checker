"""Official registry parser placeholder."""

from fa_checker.domain.models import RegistryEntry


class RegistryParser:
    """Placeholder parser for registry snapshots."""

    def parse(self, raw_content: bytes) -> list[RegistryEntry]:
        raise NotImplementedError("Registry parsing is not implemented in the scaffold phase.")

