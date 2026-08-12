"""Pytest configuration and service endpoints for Compose integration tests."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register Compose test controls and endpoint overrides."""

    compose_group = parser.getgroup("compose integration")
    compose_group.addoption(
        "--skip-compose-integration",
        action="store_true",
        help="Skip tests against the available Docker Compose services.",
    )
    compose_group.addoption(
        "--compose-app-endpoint",
        default="http://app:8000/mcp",
        help="Compose application MCP endpoint.",
        metavar="URL",
    )
    compose_group.addoption(
        "--compose-fixture-url",
        default="http://test-site:8081/",
        help="Compose static fixture site URL.",
        metavar="URL",
    )
    compose_group.addoption(
        "--compose-model-api-base",
        default="http://llama-cpp:8080/v1",
        help="Compose OpenAI-compatible model API base URL.",
        metavar="URL",
    )
    compose_group.addoption(
        "--compose-playwright-endpoint",
        default="http://playwright-mcp:8931/mcp",
        help="Compose Playwright MCP endpoint.",
        metavar="URL",
    )


@pytest.fixture(scope="session")
def compose_integration_enabled(pytestconfig: pytest.Config) -> None:
    """Skip real-service tests only when the caller explicitly opts out."""

    if pytestconfig.getoption("skip_compose_integration"):
        pytest.skip("skipped by --skip-compose-integration")


@pytest.fixture(scope="session")
def compose_application_endpoint(
    compose_integration_enabled: None,
    pytestconfig: pytest.Config,
) -> str:
    """Return the configured Compose application MCP endpoint."""

    return str(pytestconfig.getoption("compose_app_endpoint"))


@pytest.fixture(scope="session")
def compose_fixture_url(
    compose_integration_enabled: None,
    pytestconfig: pytest.Config,
) -> str:
    """Return the configured Compose static fixture URL."""

    return str(pytestconfig.getoption("compose_fixture_url"))


@pytest.fixture(scope="session")
def compose_model_catalog_url(
    compose_integration_enabled: None,
    pytestconfig: pytest.Config,
) -> str:
    """Return the configured Compose model-catalog URL."""

    model_api_base = str(pytestconfig.getoption("compose_model_api_base"))
    return f"{model_api_base.rstrip('/')}/models"


@pytest.fixture(scope="session")
def compose_playwright_endpoint(
    compose_integration_enabled: None,
    pytestconfig: pytest.Config,
) -> str:
    """Return the configured Compose Playwright MCP endpoint."""

    return str(pytestconfig.getoption("compose_playwright_endpoint"))
