"""Tests for staged browser-session orchestration and fresh snapshots."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.agent_context import PageState, ReconstructionStage, Stage
from render_and_strip_mcp.agent_loop import StageRunner, StageRunResult
from render_and_strip_mcp.config import Settings
from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.playwright_tools import PlaywrightSession, ToolCatalog
from render_and_strip_mcp.rendered_document import RenderedDocument
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

    def __init__(
        self,
        locations: list[str],
        cleanup_error: bool = False,
        document_html: list[str] | None = None,
    ):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.timeouts: list[tuple[str, object | None]] = []
        self._locations = iter(locations)
        self._action_completed = False
        self._original_tab_selected = False
        self._cleanup_error = cleanup_error
        self._document_html = iter(document_html or ["<html><head></head><body>Done</body></html>"])

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
                return text_result(f"### Result\n{json.dumps(next(self._document_html))}")
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

    async def fake_run_stage(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del task
        stage_name = stage.stage_name
        pipeline_events.append(stage_name)
        if stage_name == "access":
            page_state = initial_state
            if invoke_access_action:
                page_state = await self.execute_browser_action("browser_click", {})
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
            assert isinstance(stage, ReconstructionStage)
            assert stage.checkpoint.reconstruction_instructions == []
            return StageRunResult(
                ReconstructionReport(verified=True, evidence=["Report is visible."]), initial_state
            )
        raise AssertionError(f"Unexpected stage {stage_name}")

    async def fake_collection(
        stage_runner: StageRunner,
        task: str,
        initial_state: PageState,
        capture_document: object,
        max_paginated_documents: int,
    ) -> list[RenderedDocument]:
        del stage_runner, task, initial_state
        assert callable(capture_document)
        assert max_paginated_documents == 25
        pipeline_events.append("collection")
        return [await capture_document()]

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", fake_run_stage)
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


def test_agent_dispatches_paginated_collection_and_assembles_captured_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The paginated handler receives capture, limit, and ordered output orchestration."""

    page_one_url = "https://example.test/results?page=1"
    page_two_url = "https://example.test/results?page=2"
    client = FakeBrowserClient(
        ["https://example.test/start"] * 3 + [page_one_url, page_two_url],
        document_html=[
            "<html><body><p>First page</p></body></html>",
            "<html><body><p>Second page</p></body></html>",
        ],
    )
    install_fake_session(monkeypatch, client)

    async def fake_run_stage(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, task
        if stage.stage_name == "access":
            return StageRunResult(
                AccessCheckpoint(target_state="Results", verification=["Results visible."]),
                initial_state,
            )
        if stage.stage_name == "discovery":
            return StageRunResult(
                DiscoveryReport(
                    strategy="paginated-documents",
                    evidence=["Next replaced the same-origin results document."],
                ),
                initial_state,
            )
        if stage.stage_name == "reconstruction":
            return StageRunResult(
                ReconstructionReport(verified=True, evidence=["Results visible."]), initial_state
            )
        raise AssertionError(f"Unexpected stage {stage.stage_name}")

    async def fake_paginated_collection(
        stage_runner: StageRunner,
        task: str,
        initial_state: PageState,
        capture_document: object,
        max_paginated_documents: int,
    ) -> list[RenderedDocument]:
        del stage_runner, task, initial_state
        assert callable(capture_document)
        assert max_paginated_documents == 7
        return [await capture_document(), await capture_document()]

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", fake_run_stage)
    monkeypatch.setitem(
        browser_agent_module.COLLECTION_STRATEGIES,
        "paginated-documents",
        fake_paginated_collection,
    )

    final_html = asyncio.run(
        browser_agent_module.BrowserAgent(
            settings(max_paginated_documents=7),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run("https://example.test/", "collect results")
    )

    assert final_html.index("First page") < final_html.index("Second page")
    assert final_html.count("<section>") == 2


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

    async def unknown_discovery(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, stage, task
        report = next(reports)
        return StageRunResult(report, initial_state)

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", unknown_discovery)

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
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, stage, task
        report = next(reports)
        return StageRunResult(report, initial_state)

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", failed_reconstruction)

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

    async def fail_stage(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, stage, task, initial_state
        raise BrowserAgentError("primary failure")

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", fail_stage)

    with pytest.raises(BrowserAgentError, match="primary failure"):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )

    assert "cleanup failed" in caplog.text
