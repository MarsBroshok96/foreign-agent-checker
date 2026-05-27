"""Runtime settings for the scaffolded checker."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b-instruct"
    fa_checker_log_level: str = "INFO"
    fa_checker_max_agent_steps: int = Field(default=8, ge=1)
    minjust_registry_url: str = "https://minjust.gov.ru/ru/pages/reestr-inostryannykh-agentov/"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("fa_checker_log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


def get_settings() -> Settings:
    return Settings()

