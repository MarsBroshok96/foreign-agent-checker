import json

import pytest

from fa_checker.agent.context_profiles import (
    ContextProfile,
    find_context_profile,
    load_context_profiles,
)


def test_load_context_profiles_returns_empty_for_missing_file(tmp_path) -> None:
    assert load_context_profiles(tmp_path / "missing.json") == []


def test_load_context_profiles_loads_json_list(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            [
                {
                    "registry_id": "560",
                    "entity_name": "Варламов Илья Александрович",
                    "entity_type": "person",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = load_context_profiles(path)

    assert len(profiles) == 1
    assert profiles[0].entity_name == "Варламов Илья Александрович"


def test_load_context_profiles_old_shape_still_loads(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "registry_id": "560",
                        "entity_name": "Варламов Илья Александрович",
                        "entity_type": "person",
                        "descriptors": ["блогер"],
                        "known_projects": ["varlamov.ru"],
                        "known_domains": ["varlamov.ru"],
                        "common_mentions": ["Илья Варламов"],
                        "notes": "Auxiliary context only.",
                        "sources": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = load_context_profiles(path)

    assert len(profiles) == 1
    assert profiles[0].role_or_category is None
    assert profiles[0].disambiguation_hints == []


def test_load_context_profiles_loads_profiles_object(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "registry_id": "1208",
                        "entity_name": "Проект «После»",
                        "descriptors": ["медиа-проект"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = load_context_profiles(path)

    assert profiles == [
        ContextProfile(
            registry_id="1208",
            entity_name="Проект «После»",
            descriptors=["медиа-проект"],
        )
    ]


def test_load_context_profiles_loads_enriched_fields(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "registry_id": "1208",
                        "entity_name": "Проект «После»",
                        "role_or_category": "media project",
                        "short_description": "Нейтральное описание для различения.",
                        "disambiguation_hints": ["Контекст с изданием может быть релевантен."],
                        "negative_context_hints": ["После дождя не является упоминанием."],
                        "primary_language": "ru",
                        "confidence": "High",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = load_context_profiles(path)

    profile = profiles[0]
    assert profile.role_or_category == "media project"
    assert profile.short_description == "Нейтральное описание для различения."
    assert profile.disambiguation_hints == ["Контекст с изданием может быть релевантен."]
    assert profile.negative_context_hints == ["После дождя не является упоминанием."]
    assert profile.primary_language == "ru"
    assert profile.confidence == "high"


def test_load_context_profiles_invalid_json_raises_value_error(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid context profile JSON"):
        load_context_profiles(path)


def test_load_context_profiles_invalid_structure_raises_value_error(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps([{"registry_id": "1"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid context profile structure"):
        load_context_profiles(path)


def test_find_context_profile_finds_by_registry_id() -> None:
    profiles = [
        ContextProfile(registry_id="560", entity_name="Варламов Илья Александрович"),
        ContextProfile(registry_id="1208", entity_name="Проект «После»"),
    ]

    profile = find_context_profile(
        profiles,
        registry_id="1208",
        entity_name="Варламов Илья Александрович",
    )

    assert profile is not None
    assert profile.entity_name == "Проект «После»"


def test_find_context_profile_falls_back_to_normalized_entity_name() -> None:
    profiles = [ContextProfile(entity_name="Варламов Илья Александрович")]

    profile = find_context_profile(
        profiles,
        registry_id="missing",
        entity_name="ВАРЛАМОВ  ИЛЬЯ АЛЕКСАНДРОВИЧ",
    )

    assert profile is not None
    assert profile.entity_name == "Варламов Илья Александрович"


def test_find_context_profile_returns_none_when_no_match() -> None:
    profiles = [ContextProfile(registry_id="560", entity_name="Варламов Илья")]

    assert find_context_profile(profiles, registry_id="999", entity_name="Другое") is None
