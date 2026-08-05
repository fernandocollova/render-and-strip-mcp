"""Runtime configuration for the render-and-strip MCP server."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import AnyHttpUrl, BaseModel, Field, FiniteFloat, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Port: TypeAlias = Annotated[int, Field(ge=1, le=65535)]
NonNegativeInteger: TypeAlias = Annotated[int, Field(ge=0)]
PositiveInteger: TypeAlias = Annotated[int, Field(gt=0)]
NonNegativeSeconds: TypeAlias = Annotated[FiniteFloat, Field(ge=0)]
PositiveSeconds: TypeAlias = Annotated[FiniteFloat, Field(gt=0)]


class StrictSettingsModel(BaseModel):
    """A nested settings section that rejects misspelled configuration keys."""

    model_config = {"extra": "forbid"}


class ServerSettings(StrictSettingsModel):
    """Streamable HTTP listener settings."""

    host: str = "127.0.0.1"
    port: Port = 8000


class PlaywrightMcpSettings(StrictSettingsModel):
    """Connection settings for the official Playwright MCP server."""

    endpoint: AnyHttpUrl


class LlmSettings(StrictSettingsModel):
    """OpenAI-compatible LiteLLM endpoint settings."""

    model: Annotated[str, Field(min_length=1)]
    api_base: AnyHttpUrl
    api_key: SecretStr
    max_output_tokens: PositiveInteger = 1024


class AgentSettings(StrictSettingsModel):
    """Browser-agent request policy and execution bounds."""

    allow_plain_http: bool = False
    max_model_turns: PositiveInteger = 12
    max_browser_actions: PositiveInteger = 30
    total_timeout_seconds: PositiveSeconds = 600
    navigation_timeout_seconds: PositiveSeconds = 20
    browser_action_timeout_seconds: PositiveSeconds = 15
    model_request_timeout_seconds: PositiveSeconds = 90
    page_settle_seconds: NonNegativeSeconds = 0
    cleanup_timeout_seconds: PositiveSeconds = 10


class OutputSettings(StrictSettingsModel):
    """Clean HTML output bounds."""

    max_html_bytes: NonNegativeInteger = 0


class ProgressSettings(StrictSettingsModel):
    """Optional model-reasoning progress policy."""

    reasoning_progress_max_items: NonNegativeInteger = 0
    reasoning_progress_min_interval_seconds: NonNegativeSeconds = 0


class LoggingSettings(StrictSettingsModel):
    """Application logging settings."""

    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"


class Settings(BaseSettings):
    """Validated runtime settings loaded from TOML and environment variables."""

    model_config = SettingsConfigDict(
        extra="forbid",
        env_nested_delimiter="__",
        env_prefix="RENDER_AND_STRIP_MCP_",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    playwright_mcp: PlaywrightMcpSettings
    llm: LlmSettings
    agent: AgentSettings = Field(default_factory=AgentSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    progress: ProgressSettings = Field(default_factory=ProgressSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


def load_settings(configuration_path: Path | None = None) -> Settings:
    """Load TOML configuration, with TOML values retaining settings-source precedence."""

    if configuration_path is None or not configuration_path.exists():
        return Settings()

    with configuration_path.open("rb") as configuration_file:
        configuration: dict[str, Any] = tomllib.load(configuration_file)
    return Settings(**configuration)
