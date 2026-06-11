"""Application configuration using Pydantic Settings."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Content bot settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(description="Telegram Bot API token")
    anthropic_api_key: str = Field(description="Anthropic API key")
    vault_path: Path = Field(
        default=Path("./vault"),
        description="Path to the Obsidian-style vault directory with skills and notes",
    )
    author_name: str = Field(
        default="",
        description=(
            "Name/persona the bot writes as (e.g. 'Alex'). "
            "Leave empty for neutral first person. The real voice lives in the skills."
        ),
    )
    telegram_channel: str = Field(
        default="",
        description="Target Telegram channel username without @ (optional, for context)",
    )
    deepgram_api_key: str = Field(
        default="",
        description="Deepgram API key for voice transcription (optional)",
    )
    # NoDecode stops pydantic-settings from JSON-decoding the env value, so the
    # validator below can accept a plain comma/space-separated list.
    allowed_user_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="List of Telegram user IDs allowed to use the bot",
    )

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_user_ids(cls, value: object) -> object:
        """Accept comma/space-separated IDs (e.g. '123,456') as well as JSON."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [int(x) for x in re.split(r"[,\s]+", stripped) if x]
        return value


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings instance."""
    return Settings()
