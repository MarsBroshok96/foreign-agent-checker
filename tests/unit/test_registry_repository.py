from datetime import date

from openpyxl import Workbook

from fa_checker.registry.repository import load_registry_from_xlsx


def test_load_registry_from_xlsx_returns_parsed_entries(tmp_path) -> None:
    path = tmp_path / "registry.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registry_id", "full_name", "entity_type"])
    sheet.append(["1", "Варламов Илья Александрович", "person"])
    workbook.save(path)

    entries = load_registry_from_xlsx(
        path,
        "https://minjust.gov.ru/registry",
        snapshot_date=date(2026, 5, 22),
    )

    assert len(entries) == 1
    assert entries[0].full_name == "Варламов Илья Александрович"
    assert entries[0].registry_snapshot_date == date(2026, 5, 22)
