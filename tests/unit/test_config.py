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
    assert settings.agent.max_concurrent_invocations == 0
    assert settings.agent.cleanup_timeout_seconds == 10
    assert settings.output.max_html_bytes == 0
    assert settings.progress.reasoning_progress_max_items == 0
    assert settings.progress.reasoning_progress_min_interval_seconds == 0


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
    monkeypatch.setenv("RENDER_AND_STRIP_MCP_AGENT__MAX_CONCURRENT_INVOCATIONS", "3")

    settings = load_settings(tmp_path / "missing.toml")

    assert settings.llm.model == "environment-model"
    assert settings.agent.allow_plain_http is True
    assert settings.agent.max_concurrent_invocations == 3


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


def test_request_policy_can_be_configured() -> None:
    """The plain-HTTP and application concurrency policies are validated settings."""

    settings = Settings.model_validate(
        valid_configuration()
        | {"agent": {"allow_plain_http": True, "max_concurrent_invocations": 2}}
    )

    assert settings.agent.allow_plain_http is True
    assert settings.agent.max_concurrent_invocations == 2

    with pytest.raises(ValidationError):
        Settings.model_validate(
            valid_configuration() | {"agent": {"max_concurrent_invocations": -1}}
        )
