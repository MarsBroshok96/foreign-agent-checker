"""Ministry of Justice registry client placeholder."""

from fa_checker.domain.models import RegistryEntry


class MinjustRegistryClient:
    """Placeholder client for the official foreign-agent registry."""

    def fetch_entries(self) -> list[RegistryEntry]:
        raise NotImplementedError("Registry loading is not implemented in the scaffold phase.")

