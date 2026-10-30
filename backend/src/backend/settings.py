from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    model: str
    openai_api_key: str
    openai_base_url: str | None = None
    netra_prompt_label: str = "production"
    cors_origins: list[str] = ["*"]
    # Deliberate bug for the L1 demo: room-number changes are reported as done but never saved.
    demo_room_move_bug: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()