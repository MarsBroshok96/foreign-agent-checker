from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import RegistryEntry
from fa_checker.registry.alias_builder import AliasSet, build_aliases


def make_entry(
    full_name: str,
    entity_type: EntityType,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_person_full_name_aliases() -> None:
    aliases = build_aliases(
        make_entry("Варламов Илья Александрович", EntityType.PERSON)
    )

    assert isinstance(aliases, AliasSet)
    assert "варламов илья александрович" in aliases.strong
    assert "варламов илья" in aliases.strong
    assert "илья варламов" in aliases.strong
    assert "варламов" in aliases.weak
    assert "варламов" not in aliases.strong


def test_person_initial_aliases_are_weak_and_dotted() -> None:
    aliases = build_aliases(
        make_entry("Варламов Илья Александрович", EntityType.PERSON)
    )

    assert "варламов и." in aliases.weak
    assert "и. варламов" in aliases.weak
    assert "варламов и.а." in aliases.weak
    assert "варламов и. а." in aliases.weak
    assert "и.а. варламов" in aliases.weak
    assert "и. а. варламов" in aliases.weak
    assert "варламов и" not in aliases.weak
    assert "варламов и а" not in aliases.weak
    assert "и варламов" not in aliases.weak
    assert "варламов и." not in aliases.strong


def test_person_explicit_aliases_are_normalized_and_included() -> None:
    aliases = build_aliases(
        make_entry(
            "Варламов Илья Александрович",
            EntityType.PERSON,
            aliases=["  Илья\u00a0Варламов  ", "И. Варламов"],
        )
    )

    assert "илья варламов" in aliases.strong
    assert "и. варламов" in aliases.strong


def test_organization_legal_prefix_simplification() -> None:
    aliases = build_aliases(make_entry("ООО Ромашка", EntityType.ORGANIZATION))

    assert "ооо ромашка" in aliases.strong
    assert "ромашка" in aliases.strong


def test_short_organization_aliases_are_weak() -> None:
    aliases = build_aliases(
        make_entry("АО РБ", EntityType.ORGANIZATION, aliases=["ТВ"])
    )

    assert "тв" in aliases.weak
    assert "рб" in aliases.weak
    assert "тв" not in aliases.strong
    assert "рб" not in aliases.strong
