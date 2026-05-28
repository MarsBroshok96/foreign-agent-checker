import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from openpyxl import Workbook

from fa_checker.adapters import minjust_registry_client
from fa_checker.adapters.minjust_registry_client import (
    CACHE_FILENAME,
    RegistryDownloadError,
    download_registry_snapshot,
    find_registry_download_url,
    get_cached_registry_snapshot,
    is_cache_fresh,
    load_minjust_registry_entries,
)
from fa_checker.domain.enums import EntityType

PAGE_URL = "https://minjust.gov.ru/ru/pages/reestr-inostryannykh-agentov/"


def test_is_cache_fresh_returns_false_for_missing_file(tmp_path) -> None:
    assert is_cache_fresh(tmp_path / "missing.xlsx") is False


def test_is_cache_fresh_returns_true_for_fresh_file(tmp_path) -> None:
    path = tmp_path / "registry.xlsx"
    path.write_bytes(b"PK\x03\x04content")
    now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    timestamp = now.timestamp()

    os.utime(path, (timestamp, timestamp))

    assert is_cache_fresh(path, ttl_hours=24, now=now) is True


def test_is_cache_fresh_returns_false_for_stale_file(tmp_path) -> None:
    path = tmp_path / "registry.xlsx"
    path.write_bytes(b"PK\x03\x04content")
    now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    old_timestamp = (now - timedelta(hours=25)).timestamp()

    os.utime(path, (old_timestamp, old_timestamp))

    assert is_cache_fresh(path, ttl_hours=24, now=now) is False


def test_is_cache_fresh_returns_false_for_html_cache(tmp_path) -> None:
    path = tmp_path / "registry.xlsx"
    path.write_text("<!DOCTYPE html><html></html>", encoding="utf-8")
    now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    timestamp = now.timestamp()

    os.utime(path, (timestamp, timestamp))

    assert is_cache_fresh(path, ttl_hours=24, now=now) is False


def test_find_registry_download_url_prefers_anchor_text() -> None:
    html = '<a href="/files/export.xlsx">Загрузить реестр</a>'

    assert find_registry_download_url(html, PAGE_URL) == "https://minjust.gov.ru/files/export.xlsx"


def test_find_registry_download_url_falls_back_to_excel_href() -> None:
    html = '<a href="/files/export.xlsx">Download</a>'

    assert find_registry_download_url(html, PAGE_URL) == "https://minjust.gov.ru/files/export.xlsx"


def test_find_registry_download_url_uses_dynamic_export_when_download_anchor_is_hash() -> None:
    html = """
    <script>
      let id = '39b95df9-9a68-6b6d-e1e3-e6388507067e';
      ExternalApi.setBaseUrl('https://reestrs.minjust.gov.ru');
    </script>
    <a href="#" id="registry_download_xls">Загрузить реестр</a>
    """

    assert find_registry_download_url(html, PAGE_URL) == (
        "https://reestrs.minjust.gov.ru/rest/registry/"
        "39b95df9-9a68-6b6d-e1e3-e6388507067e/export?"
    )


def test_find_registry_download_url_raises_when_link_missing() -> None:
    with pytest.raises(RegistryDownloadError, match="Could not find"):
        find_registry_download_url("<html></html>", PAGE_URL)


def test_get_cached_registry_snapshot_uses_fresh_cache(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / CACHE_FILENAME
    cache_path.write_bytes(b"PK\x03\x04cached")
    now = datetime.now(UTC)
    import os

    os.utime(cache_path, (now.timestamp(), now.timestamp()))

    def fail_download(*args, **kwargs):
        raise AssertionError("download should not be called")

    monkeypatch.setattr(minjust_registry_client, "download_registry_snapshot", fail_download)

    assert get_cached_registry_snapshot(tmp_path, PAGE_URL, now=now) == cache_path


def test_get_cached_registry_snapshot_downloads_when_missing(monkeypatch, tmp_path) -> None:
    def fake_download(registry_page_url, destination_path):
        destination = Path(destination_path)
        destination.write_bytes(b"downloaded")
        return destination

    monkeypatch.setattr(minjust_registry_client, "download_registry_snapshot", fake_download)

    path = get_cached_registry_snapshot(tmp_path, PAGE_URL)

    assert path == tmp_path / CACHE_FILENAME
    assert path.read_bytes() == b"downloaded"


def test_get_cached_registry_snapshot_force_refresh_downloads(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / CACHE_FILENAME
    cache_path.write_bytes(b"cached")
    calls = []

    def fake_download(registry_page_url, destination_path):
        calls.append(registry_page_url)
        destination = Path(destination_path)
        destination.write_bytes(b"fresh")
        return destination

    monkeypatch.setattr(minjust_registry_client, "download_registry_snapshot", fake_download)

    path = get_cached_registry_snapshot(tmp_path, PAGE_URL, force_refresh=True)

    assert path == cache_path
    assert cache_path.read_bytes() == b"fresh"
    assert calls == [PAGE_URL]


def test_download_registry_snapshot_writes_discovered_xlsx(monkeypatch, tmp_path) -> None:
    def fake_fetch_text(url):
        assert url == PAGE_URL
        return '<a href="/files/export.xlsx">Загрузить реестр</a>'

    def fake_fetch_bytes(url, verify_tls=True):
        assert url == "https://minjust.gov.ru/files/export.xlsx"
        assert verify_tls is False
        return b"PK\x03\x04xlsx-bytes"

    monkeypatch.setattr(minjust_registry_client, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(minjust_registry_client, "fetch_bytes", fake_fetch_bytes)
    destination = tmp_path / "nested" / "registry.xlsx"

    result = download_registry_snapshot(PAGE_URL, destination)

    assert result == destination
    assert destination.read_bytes() == b"PK\x03\x04xlsx-bytes"


def test_download_registry_snapshot_rejects_non_excel_content(monkeypatch, tmp_path) -> None:
    def fake_fetch_text(url):
        assert url == PAGE_URL
        return '<a href="/files/export.xlsx">Загрузить реестр</a>'

    def fake_fetch_bytes(url, verify_tls=True):
        assert url == "https://minjust.gov.ru/files/export.xlsx"
        assert verify_tls is False
        return b"<!DOCTYPE html><html></html>"

    monkeypatch.setattr(minjust_registry_client, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(minjust_registry_client, "fetch_bytes", fake_fetch_bytes)
    destination = tmp_path / "registry.xlsx"

    with pytest.raises(RegistryDownloadError, match="not an Excel file"):
        download_registry_snapshot(PAGE_URL, destination)

    assert not destination.exists()


def test_load_minjust_registry_entries_uses_cached_xlsx(monkeypatch, tmp_path) -> None:
    xlsx_path = tmp_path / "registry.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registry_id", "full_name", "entity_type"])
    sheet.append(["1", "Варламов Илья Александрович", "person"])
    workbook.save(xlsx_path)

    def fake_get_cached_registry_snapshot(*args, **kwargs):
        return xlsx_path

    monkeypatch.setattr(
        minjust_registry_client,
        "get_cached_registry_snapshot",
        fake_get_cached_registry_snapshot,
    )

    entries = load_minjust_registry_entries(tmp_path, PAGE_URL)

    assert len(entries) == 1
    assert entries[0].full_name == "Варламов Илья Александрович"
    assert entries[0].entity_type == EntityType.PERSON
    assert entries[0].registry_source_url == PAGE_URL
