from fa_checker.config import Settings


def test_registry_cache_settings_have_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.registry_cache_dir == "data/registry"
    assert settings.registry_cache_ttl_hours == 24
