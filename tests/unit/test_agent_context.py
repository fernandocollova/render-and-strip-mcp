"""Tests for compact browser-action context formatting."""

import logging

import pytest

from render_and_strip_mcp.agent_context import (
    BrowserToolArguments,
    PageState,
    format_browser_action,
)


def test_known_tool_arguments_use_kind_specific_formatters() -> None:
    """Structural values remain useful while payload and unknown values are omitted."""

    summary = BrowserToolArguments.format(
        "browser_type",
        {
            "target": {"b": 2, "a": 1},
            "text": "secret",
            "unexpected": "also secret",
        },
    )

    assert summary == ('target={"a": 1, "b": 2}, text=<6 chars omitted>, unexpected=<omitted>')


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"values": ["one", "two"]}, "values=<2 items omitted>"),
        ({"values": None}, "values=<value omitted>"),
    ],
)
def test_payload_formatter_describes_non_string_values(
    arguments: dict[str, object], expected: str
) -> None:
    """Payload descriptions cover collections and scalar values without retaining them."""

    assert BrowserToolArguments.format("browser_select_option", arguments) == expected


def test_unknown_tool_arguments_are_omitted_and_warned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown tools retain no argument values and produce a maintenance warning."""

    with caplog.at_level(logging.WARNING):
        summary = format_browser_action(
            "browser_future_action",
            {"zeta": "secret", "alpha": 42},
            PageState("snapshot", "https://example.test/next", succeeded=False),
        )

    assert summary == (
        "browser_future_action(alpha=<omitted>, zeta=<omitted>) -> failure; "
        "current URL: https://example.test/next"
    )
    assert "No dedicated action formatter is defined" in caplog.text
