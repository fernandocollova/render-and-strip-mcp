"""Tests for runtime settings loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from render_and_strip_mcp.config import Settings, load_settings


def valid_configuration() -> dict[str, object]:
    """Return the smallest valid configuration for settings tests."""

    return {
        "playwright_mcp": {"endpoint": "https://playwright.example/mcp"},
        "llm": {
            "model": "test-model",
            "api_base": "https://model.example/v1",
            "api_key": "test-key",
        },
    }


def write_configuration(configuration_path: Path, contents: str) -> None:
    """Write a UTF-8 TOML test configuration."""

    configuration_path.write_text(contents, encoding="utf-8")


def test_default_settings_require_external_dependencies() -> None:
    """Defaults do not supply deployment-specific endpoint or credential values."""

    with pytest.raises(ValidationError):
        Settings()


def test_settings_apply_documented_defaults() -> None:
    """Runtime policy defaults are applied around required endpoint configuration."""

    settings = Settings.model_validate(valid_configuration())

    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 8000
    assert settings.llm.max_output_tokens == 1024
    assert settings.agent.allow_plain_http is False
    assert settings.agent.max_model_turns == 12
    assert settings.agent.max_browser_actions == 30
    assert settings.agent.max_paginated_documents == 25
    assert settings.agent.run_timeout_seconds == 3600
    assert settings.agent.page_settle_seconds == 0
    assert settings.agent.cleanup_timeout_seconds == 10
    assert settings.output.max_html_bytes == 0
    assert settings.progress.reasoning_progress_max_items == 0
    assert settings.progress.reasoning_progress_min_interval_seconds == 0
    assert settings.logging.level == "INFO"


def test_toml_configuration_is_validated(tmp_path: Path) -> None:
    """An existing TOML file supplies validated nested settings."""

    configuration_path = tmp_path / "render-and-strip.toml"
    write_configuration(
        configuration_path,
        """
[server]
host = "0.0.0.0"
port = 9010

[playwright_mcp]
endpoint = "https://browser.example/mcp"

[llm]
model = "local/model"
api_base = "https://model.example/v1"
api_key = "toml-key"
max_output_tokens = 777
""",
    )

    settings = load_settings(configuration_path)

    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 9010
    assert str(settings.playwright_mcp.endpoint) == "https://browser.example/mcp"
    assert settings.llm.max_output_tokens == 777
    assert settings.llm.api_key.get_secret_value() == "toml-key"


def test_environment_populates_missing_configuration_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nested environment values provide required settings without a TOML file."""

    monkeypatch.setenv(
        "RENDER_AND_STRIP_MCP_PLAYWRIGHT_MCP__ENDPOINT", "https://browser.example/mcp"
    )
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__MODEL", "environment-model")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__API_BASE", "https://model.example/v1")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__API_KEY", "environment-key")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_AGENT__ALLOW_PLAIN_HTTP", "true")

    settings = load_settings(tmp_path / "missing.toml")

    assert settings.llm.model == "environment-model"
    assert settings.agent.allow_plain_http is True


def test_toml_values_take_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Explicit TOML values retain their documented init-source precedence."""

    configuration_path = tmp_path / "render-and-strip.toml"
    write_configuration(
        configuration_path,
        """
[playwright_mcp]
endpoint = "https://browser.example/mcp"

[llm]
model = "toml-model"
api_base = "https://model.example/v1"
api_key = "toml-key"
""",
    )
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__MODEL", "environment-model")

    assert load_settings(configuration_path).llm.model == "toml-model"


def test_unknown_settings_are_rejected(tmp_path: Path) -> None:
    """Unknown TOML fields cannot silently change application behavior."""

    configuration_path = tmp_path / "render-and-strip.toml"
    write_configuration(
        configuration_path,
        """
[playwright_mcp]
endpoint = "https://browser.example/mcp"
unexpected = "value"

[llm]
model = "model"
api_base = "https://model.example/v1"
api_key = "key"
""",
    )

    with pytest.raises(ValidationError, match="unexpected"):
        load_settings(configuration_path)


def test_plain_http_permission_can_be_configured() -> None:
    """Plain-HTTP permission is a validated request-policy setting."""

    settings = Settings.model_validate(
        valid_configuration() | {"agent": {"allow_plain_http": True}}
    )

    assert settings.agent.allow_plain_http is True

    with pytest.raises(ValidationError, match="max_concurrent_invocations"):
        Settings.model_validate(
            valid_configuration() | {"agent": {"max_concurrent_invocations": 1}}
        )


def test_paginated_document_limit_is_configurable_and_positive() -> None:
    """Pagination has an invocation-wide positive document limit with no zero sentinel."""

    settings = Settings.model_validate(
        valid_configuration() | {"agent": {"max_paginated_documents": 7}}
    )

    assert settings.agent.max_paginated_documents == 7

    with pytest.raises(ValidationError, match="max_paginated_documents"):
        Settings.model_validate(valid_configuration() | {"agent": {"max_paginated_documents": 0}})


def test_retired_concurrency_environment_setting_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nested environment variables cannot restore the retired concurrency setting."""

    monkeypatch.setenv(
        "RENDER_AND_STRIP_MCP_PLAYWRIGHT_MCP__ENDPOINT", "https://browser.example/mcp"
    )
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__MODEL", "environment-model")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__API_BASE", "https://model.example/v1")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_LLM__API_KEY", "environment-key")
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_AGENT__MAX_CONCURRENT_INVOCATIONS", "1")

    with pytest.raises(ValidationError, match="max_concurrent_invocations"):
        load_settings(tmp_path / "missing.toml")
