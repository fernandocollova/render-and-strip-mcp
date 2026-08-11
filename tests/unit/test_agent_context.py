"""Tests for compact browser-action context formatting."""

import logging

import pytest

from render_and_strip_mcp.agent_context import (
    AccessStage,
    BrowserToolArguments,
    CollectionStage,
    DiscoveryStage,
    PageState,
    PaginationAdvanceStage,
    ReconstructionStage,
    Stage,
    format_browser_action,
)
from render_and_strip_mcp.stage_models import AccessCheckpoint

ACCESS_AND_RECONSTRUCTION_TOOLS = frozenset(
    {
        "browser_click",
        "browser_drag",
        "browser_fill_form",
        "browser_find",
        "browser_handle_dialog",
        "browser_hover",
        "browser_navigate",
        "browser_navigate_back",
        "browser_press_key",
        "browser_select_option",
        "browser_type",
        "browser_wait_for",
    }
)
DISCOVERY_AND_COLLECTION_TOOLS = frozenset(
    {
        "browser_click",
        "browser_find",
        "browser_hover",
        "browser_press_key",
        "browser_wait_for",
    }
)


@pytest.mark.parametrize(
    ("stage", "expected_tools"),
    [
        (AccessStage(), ACCESS_AND_RECONSTRUCTION_TOOLS),
        (
            ReconstructionStage(AccessCheckpoint(target_state="View", verification=["Visible"])),
            ACCESS_AND_RECONSTRUCTION_TOOLS,
        ),
        (DiscoveryStage(), DISCOVERY_AND_COLLECTION_TOOLS),
        (CollectionStage("retained-final-document"), DISCOVERY_AND_COLLECTION_TOOLS),
        (
            PaginationAdvanceStage(1),
            frozenset({"browser_click", "browser_wait_for"}),
        ),
    ],
)
def test_stages_define_immutable_browser_tool_policies(
    stage: Stage, expected_tools: frozenset[str]
) -> None:
    """Each stage exposes only its immutable model-directed browser actions."""

    assert isinstance(stage.allowed_browser_tools, frozenset)
    assert stage.allowed_browser_tools == expected_tools
    assert "browser_evaluate" not in stage.allowed_browser_tools


def test_related_stages_share_browser_tool_policy_instances() -> None:
    """Stages with identical policies reuse the same immutable set."""

    assert AccessStage.allowed_browser_tools is ReconstructionStage.allowed_browser_tools
    assert DiscoveryStage.allowed_browser_tools is CollectionStage.allowed_browser_tools


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
