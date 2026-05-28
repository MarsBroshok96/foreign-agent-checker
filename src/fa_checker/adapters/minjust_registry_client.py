"""Ministry of Justice registry download and cache helpers."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from fa_checker.adapters.http_client import fetch_bytes, fetch_text
from fa_checker.domain.models import RegistryEntry
from fa_checker.registry.repository import load_registry_from_xlsx

CACHE_FILENAME = "minjust_registry_latest.xlsx"
EXCEL_SIGNATURES = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")
REGISTRY_BASE_URL_RE = re.compile(r"ExternalApi\.setBaseUrl\(['\"]([^'\"]+)['\"]\)")
REGISTRY_ID_RE = re.compile(r"(?:let|const|var)\s+id\s*=\s*['\"]([^'\"]+)['\"]")


class RegistryDownloadError(RuntimeError):
    """Raised when registry snapshot discovery or saving fails."""


def is_cache_fresh(
    path: str | Path,
    ttl_hours: int = 24,
    now: datetime | None = None,
) -> bool:
    """Return whether a local cache file exists and is within the TTL."""
    cache_path = Path(path)
    if not cache_path.exists():
        return False
    if not _has_excel_signature(cache_path):
        return False

    current_time = _as_utc(now or datetime.now(UTC))
    modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
    return current_time - modified_at <= timedelta(hours=ttl_hours)


def find_registry_download_url(page_html: str, page_url: str) -> str:
    """Discover the registry export URL from an official registry page."""
    soup = BeautifulSoup(page_html, "html.parser")
    anchors = soup.find_all("a", href=True)

    for anchor in anchors:
        if "загрузить реестр" in anchor.get_text(" ", strip=True).lower():
            href = str(anchor["href"]).strip()
            if _is_usable_href(href):
                return urljoin(page_url, href)

    for anchor in anchors:
        href = str(anchor["href"]).strip()
        if _is_usable_href(href) and _looks_like_excel_href(href):
            return urljoin(page_url, href)

    dynamic_export_url = _find_dynamic_registry_export_url(page_html)
    if dynamic_export_url is not None:
        return dynamic_export_url

    msg = "Could not find registry XLSX download link on registry page."
    raise RegistryDownloadError(msg)


def download_registry_snapshot(registry_page_url: str, destination_path: str | Path) -> Path:
    """Download the current registry snapshot to a local XLSX path."""
    destination = Path(destination_path)
    page_html = fetch_text(registry_page_url)
    download_url = find_registry_download_url(page_html, registry_page_url)
    content = fetch_bytes(download_url, verify_tls=False)
    if not _looks_like_excel_content(content):
        msg = f"Downloaded registry snapshot from {download_url!r} is not an Excel file."
        raise RegistryDownloadError(msg)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    except OSError as exc:
        msg = f"Could not save registry snapshot to {destination}: {exc}"
        raise RegistryDownloadError(msg) from exc

    return destination


def get_cached_registry_snapshot(
    cache_dir: str | Path,
    registry_page_url: str,
    ttl_hours: int = 24,
    force_refresh: bool = False,
    now: datetime | None = None,
) -> Path:
    """Return a fresh cached registry snapshot path, downloading if needed."""
    cache_path = Path(cache_dir) / CACHE_FILENAME
    if not force_refresh and is_cache_fresh(cache_path, ttl_hours=ttl_hours, now=now):
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return download_registry_snapshot(registry_page_url, cache_path)


def load_minjust_registry_entries(
    cache_dir: str | Path,
    registry_page_url: str,
    ttl_hours: int = 24,
    force_refresh: bool = False,
) -> list[RegistryEntry]:
    """Load parsed registry entries from the cached local snapshot."""
    snapshot_path = get_cached_registry_snapshot(
        cache_dir=cache_dir,
        registry_page_url=registry_page_url,
        ttl_hours=ttl_hours,
        force_refresh=force_refresh,
    )
    return load_registry_from_xlsx(snapshot_path, registry_source_url=registry_page_url)


def _looks_like_excel_href(href: str) -> bool:
    lowered = href.lower()
    return (
        lowered.endswith(".xlsx")
        or lowered.endswith(".xls")
        or ".xlsx?" in lowered
        or ".xls?" in lowered
    )


def _is_usable_href(href: str) -> bool:
    lowered = href.strip().lower()
    return bool(lowered) and lowered != "#" and not lowered.startswith("javascript:")


def _find_dynamic_registry_export_url(page_html: str) -> str | None:
    base_url_match = REGISTRY_BASE_URL_RE.search(page_html)
    registry_id_match = REGISTRY_ID_RE.search(page_html)
    if base_url_match is None or registry_id_match is None:
        return None
    base_url = base_url_match.group(1).rstrip("/")
    registry_id = registry_id_match.group(1)
    return f"{base_url}/rest/registry/{registry_id}/export?"


def _looks_like_excel_content(content: bytes) -> bool:
    return content.startswith(EXCEL_SIGNATURES)


def _has_excel_signature(path: Path) -> bool:
    try:
        return _looks_like_excel_content(path.read_bytes()[:8])
    except OSError:
        return False


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MinjustRegistryClient:
    """Compatibility wrapper around cached registry loading."""

    def fetch_entries(self) -> list[RegistryEntry]:
        raise NotImplementedError("Registry loading is not implemented in the scaffold phase.")
