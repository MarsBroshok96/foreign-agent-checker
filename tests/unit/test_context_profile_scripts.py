import importlib.util
import json
from pathlib import Path

from openpyxl import Workbook

from fa_checker.agent.context_profiles import ContextProfile, load_context_profiles
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import RegistryEntry


def load_script_module(name: str):
    path = Path(__file__).parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


merge_context_profiles = load_script_module("merge_context_profiles")
profile_coverage = load_script_module("profile_coverage")
validate_context_profiles_script = load_script_module("validate_context_profiles")


def write_profiles(path, profiles) -> None:
    path.write_text(
        json.dumps({"profiles": profiles}, ensure_ascii=False),
        encoding="utf-8",
    )


def write_registry_xlsx(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registry_id", "full_name", "entity_type"])
    sheet.append(["1", "Варламов Илья Александрович", "person"])
    sheet.append(["2", "Проект «После»", "project"])
    workbook.save(path)


def test_validate_script_succeeds_on_valid_profiles(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    write_profiles(
        path,
        [
            {
                "registry_id": "1",
                "entity_name": "Варламов Илья Александрович",
            }
        ],
    )

    summary = validate_context_profiles_script.validate_context_profiles(path)

    assert summary["valid"] is True
    assert summary["profiles_count"] == 1


def test_validate_script_fails_on_duplicate_registry_id(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    write_profiles(
        path,
        [
            {"registry_id": "1", "entity_name": "Первый"},
            {"registry_id": "1", "entity_name": "Второй"},
        ],
    )

    summary = validate_context_profiles_script.validate_context_profiles(path)

    assert summary["valid"] is False
    assert summary["duplicate_registry_ids"] == ["1"]


def test_validate_script_succeeds_with_matching_registry_snapshot(tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    profiles_path = tmp_path / "profiles.json"
    write_registry_xlsx(registry_path)
    write_profiles(
        profiles_path,
        [
            {
                "registry_id": "1",
                "entity_name": "Варламов Илья Александрович",
            }
        ],
    )

    summary = validate_context_profiles_script.validate_context_profiles(
        profiles_path,
        registry_xlsx_path=registry_path,
    )

    assert summary["valid"] is True
    assert summary["unknown_registry_ids"] == []
    assert summary["registry_name_mismatches"] == []


def test_validate_script_fails_on_unknown_registry_id(tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    profiles_path = tmp_path / "profiles.json"
    write_registry_xlsx(registry_path)
    write_profiles(
        profiles_path,
        [
            {
                "registry_id": "999",
                "entity_name": "Неизвестная запись",
            }
        ],
    )

    summary = validate_context_profiles_script.validate_context_profiles(
        profiles_path,
        registry_xlsx_path=registry_path,
    )

    assert summary["valid"] is False
    assert summary["unknown_registry_ids"] == ["999"]


def test_validate_script_fails_on_registry_name_mismatch(tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    profiles_path = tmp_path / "profiles.json"
    write_registry_xlsx(registry_path)
    write_profiles(
        profiles_path,
        [
            {
                "registry_id": "1",
                "entity_name": "Другое имя",
            }
        ],
    )

    summary = validate_context_profiles_script.validate_context_profiles(
        profiles_path,
        registry_xlsx_path=registry_path,
    )

    assert summary["valid"] is False
    assert summary["registry_name_mismatches"] == [
        {
            "registry_id": "1",
            "profile_entity_name": "Другое имя",
            "registry_entity_name": "Варламов Илья Александрович",
        }
    ]


def test_coverage_script_identifies_missing_profiles(tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    profiles_path = tmp_path / "profiles.json"
    write_registry_xlsx(registry_path)
    write_profiles(
        profiles_path,
        [{"registry_id": "1", "entity_name": "Варламов Илья Александрович"}],
    )

    summary = profile_coverage.coverage_summary(registry_path, profiles_path, limit=10)

    assert summary["registry_entries_count"] == 2
    assert summary["matched_profiles_count"] == 1
    assert summary["missing_profiles_count"] == 1
    assert summary["missing_entries"][0].full_name == "Проект «После»"


def test_missing_profile_entries_matches_by_normalized_name() -> None:
    registry_entries = [
        RegistryEntry(
            registry_id=None,
            full_name="Варламов Илья Александрович",
            entity_type=EntityType.PERSON,
            normalized_name="варламов илья александрович",
            registry_source_url="local",
        )
    ]
    profiles = [ContextProfile(entity_name="ВАРЛАМОВ ИЛЬЯ АЛЕКСАНДРОВИЧ")]

    assert profile_coverage.missing_profile_entries(registry_entries, profiles) == []


def test_merge_script_merges_profiles_by_registry_id() -> None:
    merged = merge_context_profiles.merge_profiles(
        [
            ContextProfile(
                registry_id="1",
                entity_name="Варламов Илья Александрович",
                descriptors=["блогер"],
            )
        ],
        [
            ContextProfile(
                registry_id="1",
                entity_name="Варламов Илья Александрович",
                short_description="Нейтральное описание.",
                descriptors=[],
            )
        ],
    )

    assert len(merged) == 1
    assert merged[0].descriptors == ["блогер"]
    assert merged[0].short_description == "Нейтральное описание."


def test_merge_script_preserves_existing_profiles() -> None:
    merged = merge_context_profiles.merge_profiles(
        [ContextProfile(registry_id="1", entity_name="Первый")],
        [ContextProfile(registry_id="2", entity_name="Второй")],
    )

    assert [profile.registry_id for profile in merged] == ["1", "2"]


def test_merge_script_writes_valid_json(tmp_path) -> None:
    existing_path = tmp_path / "existing.json"
    batch_path = tmp_path / "batch.json"
    output_path = tmp_path / "merged.json"
    write_profiles(existing_path, [{"registry_id": "1", "entity_name": "Первый"}])
    write_profiles(
        batch_path,
        [
            {
                "registry_id": "1",
                "entity_name": "Первый",
                "short_description": "Описание.",
            }
        ],
    )

    merge_context_profiles.merge_context_profile_files(existing_path, batch_path, output_path)

    profiles = load_context_profiles(output_path)
    assert profiles[0].short_description == "Описание."
