"""Tests for command-line server startup."""

from __future__ import annotations

from pathlib import Path

import render_and_strip_mcp.cli as cli_module
from render_and_strip_mcp.config import Settings


def valid_settings() -> Settings:
    """Build valid settings for CLI wiring tests."""

    return Settings.model_validate(
        {
            "playwright_mcp": {"endpoint": "https://browser.example/mcp"},
            "llm": {
                "model": "test-model",
                "api_base": "https://model.example/v1",
                "api_key": "test-key",
            },
        }
    )


def test_cli_loads_the_optional_configuration_path(monkeypatch, tmp_path: Path) -> None:
    """CLI wiring loads, configures, then starts with its positional path."""

    configuration_path = tmp_path / "render-and-strip.toml"
    expected_settings = valid_settings()
    observed: dict[str, object] = {}

    monkeypatch.setattr(cli_module.sys, "argv", ["render-and-strip-mcp", str(configuration_path)])
    monkeypatch.setattr(
        cli_module,
        "load_settings",
        lambda supplied_path: observed.setdefault("path", supplied_path) and expected_settings,
    )
    monkeypatch.setattr(
        cli_module,
        "configure_logging",
        lambda settings: observed.setdefault("logging", settings),
    )
    monkeypatch.setattr(
        cli_module,
        "main",
        lambda settings: observed.setdefault("settings", settings),
    )

    cli_module.cli()

    assert observed == {
        "path": configuration_path,
        "logging": expected_settings,
        "settings": expected_settings,
    }


def test_main_starts_streamable_http_server(monkeypatch) -> None:
    """Startup creates the FastMCP application with configured bind settings."""

    observed: dict[str, object] = {}

    class FakeServer:
        def run(self, **kwargs: object) -> None:
            observed["run"] = kwargs

    def create_fake_server(configured_settings: Settings) -> FakeServer:
        observed["settings"] = configured_settings
        return FakeServer()

    monkeypatch.setattr(cli_module, "create_server", create_fake_server)

    expected_settings = valid_settings()
    cli_module.main(expected_settings)

    assert observed == {
        "settings": expected_settings,
        "run": {"transport": "streamable-http", "host": "127.0.0.1", "port": 8000},
    }
