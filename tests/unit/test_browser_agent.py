"""Tests for staged browser-session orchestration and fresh snapshots."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.agent_context import PageState
from render_and_strip_mcp.agent_loop import StageRunResult
from render_and_strip_mcp.config import Settings
from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.playwright_tools import PlaywrightSession, ToolCatalog
from render_and_strip_mcp.stage_models import (
    AccessCheckpoint,
    DiscoveryReport,
    ReconstructionReport,
)


def settings(**agent_values: object) -> Settings:
    """Build valid application settings with optional agent-policy overrides."""

    return Settings.model_validate(
        {
            "playwright_mcp": {"endpoint": "https://browser.example/mcp"},
            "llm": {
                "model": "test-model",
                "api_base": "https://model.example/v1",
                "api_key": "test-key",
            },
            "agent": agent_values,
        }
    )


def text_result(text: str, is_error: bool = False) -> CallToolResult:
    """Create a textual official-MCP result for fake remote calls."""

    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=None,
        meta=None,
        is_error=is_error,
    )


class FakeBrowserClient:
    """Minimal official-MCP behavior with snapshots and optional action popup state."""

    def __init__(self, locations: list[str], cleanup_error: bool = False):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.timeouts: list[tuple[str, object | None]] = []
        self._locations = iter(locations)
        self._action_completed = False
        self._original_tab_selected = False
        self._cleanup_error = cleanup_error

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
        **kwargs: object,
    ) -> CallToolResult:
        self.calls.append((tool_name, arguments))
        self.timeouts.append((tool_name, kwargs.get("timeout")))
        if tool_name == "browser_navigate":
            return text_result("### Page\n- Page URL: https://example.test/start")
        if tool_name == "browser_tabs":
            if arguments["action"] == "select":
                self._original_tab_selected = True
                return text_result("### Result\n- 0: (current) [Start](https://example.test/start)")
            if self._action_completed and not self._original_tab_selected:
                return text_result(
                    "### Result\n- 0: [Start](https://example.test/start)\n"
                    "- 1: (current) [Popup](https://example.test/popup)"
                )
            return text_result("### Result\n- 0: (current) [Start](https://example.test/start)")
        if tool_name == "browser_snapshot":
            return text_result("### Page\n- Fresh snapshot")
        if tool_name == "browser_evaluate":
            if arguments["function"] != "() => location.href":
                return text_result('### Result\n"<html><head></head><body>Done</body></html>"')
            return text_result(
                f"### Result\n{json.dumps(next(self._locations))}\n### Ran Playwright code"
            )
        if tool_name == "browser_close":
            return text_result("cleanup failed", is_error=self._cleanup_error)
        self._action_completed = True
        return text_result("### Page\n- Stale action result")


class RecordingProgressReporter:
    """Record progress-reporter calls made by browser orchestration."""

    def __init__(self):
        self.operational_statuses: list[str] = []
        self.flush_count = 0

    async def accept(self, reasoning_fragment: str) -> None:
        """Accept model reasoning without recording it in orchestration-only tests."""

    async def accept_operational_status(self, status: str) -> None:
        self.operational_statuses.append(status)

    async def flush_if_needed(self) -> None:
        self.flush_count += 1


def install_fake_session(monkeypatch: pytest.MonkeyPatch, client: FakeBrowserClient) -> None:
    """Replace the HTTP session opener with a deterministic session context."""

    @asynccontextmanager
    async def fake_session(endpoint: str):
        yield PlaywrightSession(
            client=client,  # type: ignore[arg-type]
            tool_catalog=ToolCatalog([], {"browser_click": "browser_click"}),
        )

    monkeypatch.setattr(browser_agent_module, "open_playwright_session", fake_session)


def install_successful_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    invoke_access_action: bool = False,
) -> list[str]:
    """Install deterministic reports for all stages and record stage/collection order."""

    pipeline_events: list[str] = []

    async def fake_run_stage(*arguments: object, **keyword_arguments: object) -> StageRunResult:
        completion_tool = arguments[3]
        initial_state = arguments[5]
        execute_action = arguments[6]
        assert isinstance(initial_state, PageState)
        assert callable(execute_action)
        stage_name = completion_tool.stage_name  # type: ignore[union-attr]
        pipeline_events.append(stage_name)
        if stage_name == "access":
            page_state = initial_state
            if invoke_access_action:
                page_state = await execute_action("browser_click", {})
                assert page_state.observation == "### Page\n- Fresh snapshot"
            return StageRunResult(
                AccessCheckpoint(
                    target_state="Report view",
                    reconstruction_instructions=[],
                    verification=["Report is visible."],
                ),
                page_state,
            )
        if stage_name == "discovery":
            return StageRunResult(
                DiscoveryReport(
                    strategy="retained-final-document", evidence=["Static retained document."]
                ),
                initial_state,
            )
        if stage_name == "reconstruction":
            checkpoint = arguments[8]
            assert isinstance(checkpoint, AccessCheckpoint)
            assert checkpoint.reconstruction_instructions == []
            return StageRunResult(
                ReconstructionReport(verified=True, evidence=["Report is visible."]), initial_state
            )
        raise AssertionError(f"Unexpected stage {stage_name}")

    async def fake_collection(*arguments: object, **keyword_arguments: object) -> PageState:
        pipeline_events.append("collection")
        page_state = arguments[4]
        assert isinstance(page_state, PageState)
        return page_state

    monkeypatch.setattr(browser_agent_module, "run_stage", fake_run_stage)
    monkeypatch.setitem(
        browser_agent_module.COLLECTION_STRATEGIES,
        "retained-final-document",
        fake_collection,
    )
    return pipeline_events


def test_agent_runs_stages_in_order_and_extracts_once_after_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a complete retained-document pipeline produces the one final cleaned HTML result."""

    client = FakeBrowserClient(["https://example.test/start"] * 4)
    install_fake_session(monkeypatch, client)
    pipeline_events = install_successful_pipeline(monkeypatch)

    final_html = asyncio.run(
        browser_agent_module.BrowserAgent(
            settings(),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run("https://example.test/", "clean")
    )

    assert "<body>Done</body>" in final_html
    assert pipeline_events == ["access", "discovery", "reconstruction", "collection"]
    assert [tool_name for tool_name, _ in client.calls].count("browser_evaluate") == 5
    assert client.calls[-1] == ("browser_close", {})


def test_agent_emits_labelled_operational_milestones_without_stage_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline operations use reporter APIs without exposing report fields or flush policy."""

    client = FakeBrowserClient(["https://example.test/start"] * 4)
    install_fake_session(monkeypatch, client)
    install_successful_pipeline(monkeypatch)
    reporter = RecordingProgressReporter()

    asyncio.run(
        browser_agent_module.BrowserAgent(settings(), reporter).run(  # type: ignore[arg-type]
            "https://example.test/", "clean"
        )
    )

    assert reporter.operational_statuses == [
        "Initial navigation",
        "Access",
        "Discovery",
        "Reset",
        "Reconstruction",
        "Collection",
        "Final extraction and cleaning",
    ]
    assert reporter.flush_count == 1


def test_agent_action_restores_original_tab_and_uses_fresh_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-action state comes from the original-tab snapshot, never the action result text."""

    client = FakeBrowserClient(["https://example.test/start"] * 5)
    install_fake_session(monkeypatch, client)
    install_successful_pipeline(monkeypatch, invoke_access_action=True)

    asyncio.run(
        browser_agent_module.BrowserAgent(
            settings(),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run("https://example.test/", "click")
    )

    action_index = client.calls.index(("browser_click", {}))
    assert client.calls[action_index + 1] == ("browser_tabs", {"action": "list"})
    assert ("browser_tabs", {"action": "select", "index": 0}) in client.calls
    assert client.calls[action_index + 4] == ("browser_snapshot", {})


def test_agent_applies_independent_navigation_and_action_operation_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Navigation, actions, snapshots, and URL reads retain separate configured deadlines."""

    client = FakeBrowserClient(["https://example.test/start"] * 5)
    install_fake_session(monkeypatch, client)
    install_successful_pipeline(monkeypatch, invoke_access_action=True)

    asyncio.run(
        browser_agent_module.BrowserAgent(
            settings(navigation_timeout_seconds=7, browser_action_timeout_seconds=3),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run("https://example.test/", "click")
    )

    assert client.timeouts[0] == ("browser_navigate", 7)
    assert ("browser_click", 3) in client.timeouts
    assert ("browser_snapshot", 3) in client.timeouts
    assert ("browser_evaluate", 3) in client.timeouts


def test_zero_settle_grace_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default fresh-state boundary does not add an application-level fixed delay."""

    client = FakeBrowserClient(["https://example.test/start"] * 4)
    install_fake_session(monkeypatch, client)
    install_successful_pipeline(monkeypatch)
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(browser_agent_module.asyncio, "sleep", record_sleep)

    asyncio.run(
        browser_agent_module.BrowserAgent(
            settings(),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run("https://example.test/", "clean")
    )

    assert sleeps == []


def test_agent_rejects_cross_origin_fresh_action_and_still_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A popup or remote action cannot move the tracked original tab to another origin."""

    client = FakeBrowserClient(
        ["https://example.test/start", "https://example.test/start", "https://other.test/next"]
    )
    install_fake_session(monkeypatch, client)
    install_successful_pipeline(monkeypatch, invoke_access_action=True)

    with pytest.raises(BrowserAgentError, match="left the initial document origin"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "click")
        )

    assert client.calls[-1] == ("browser_close", {})


def test_unknown_discovery_fails_before_reset_collection_or_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambiguous collection behavior never returns the currently rendered partial document."""

    client = FakeBrowserClient(["https://example.test/start"] * 2)
    install_fake_session(monkeypatch, client)
    reports = iter(
        [
            AccessCheckpoint(
                target_state="Report view",
                reconstruction_instructions=[],
                verification=["Report visible."],
            ),
            DiscoveryReport(strategy="unknown", evidence=["Replacement behavior is ambiguous."]),
        ]
    )

    async def unknown_discovery(*arguments: object, **keyword_arguments: object) -> StageRunResult:
        report = next(reports)
        initial_state = arguments[5]
        assert isinstance(initial_state, PageState)
        return StageRunResult(report, initial_state)

    monkeypatch.setattr(browser_agent_module, "run_stage", unknown_discovery)

    with pytest.raises(BrowserAgentError, match="could not establish"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )

    assert [tool_name for tool_name, _ in client.calls].count("browser_navigate") == 1
    assert not any(
        tool_name == "browser_evaluate" and arguments["function"] != "() => location.href"
        for tool_name, arguments in client.calls
    )


def test_failed_reconstruction_fails_before_collection_or_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reset page that cannot verify the checkpoint cannot proceed to final HTML."""

    client = FakeBrowserClient(["https://example.test/start"] * 3)
    install_fake_session(monkeypatch, client)
    reports = iter(
        [
            AccessCheckpoint(
                target_state="Report view",
                reconstruction_instructions=[],
                verification=["Report visible."],
            ),
            DiscoveryReport(strategy="retained-final-document", evidence=["Static."]),
            ReconstructionReport(verified=False, evidence=["Report is missing."]),
        ]
    )

    async def failed_reconstruction(
        *arguments: object, **keyword_arguments: object
    ) -> StageRunResult:
        report = next(reports)
        initial_state = arguments[5]
        assert isinstance(initial_state, PageState)
        return StageRunResult(report, initial_state)

    monkeypatch.setattr(browser_agent_module, "run_stage", failed_reconstruction)

    with pytest.raises(BrowserAgentError, match="did not verify"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )

    assert not any(
        tool_name == "browser_evaluate" and arguments["function"] != "() => location.href"
        for tool_name, arguments in client.calls
    )


def test_agent_rejects_invalid_input_before_opening_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disallowed HTTP is rejected without connecting to the remote browser."""

    monkeypatch.setattr(
        browser_agent_module,
        "open_playwright_session",
        lambda endpoint: (_ for _ in ()).throw(AssertionError("session should not open")),
    )

    with pytest.raises(BrowserAgentError, match="Plain HTTP"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("http://example.test/", "task")
        )


def test_cleanup_preserves_primary_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cleanup errors are logged without replacing an earlier processing failure."""

    client = FakeBrowserClient(["https://example.test/start"] * 2, cleanup_error=True)
    install_fake_session(monkeypatch, client)

    async def fail_stage(*arguments: object, **keyword_arguments: object) -> StageRunResult:
        raise BrowserAgentError("primary failure")

    monkeypatch.setattr(browser_agent_module, "run_stage", fail_stage)

    with pytest.raises(BrowserAgentError, match="primary failure"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )

    assert "cleanup failed" in caplog.text
