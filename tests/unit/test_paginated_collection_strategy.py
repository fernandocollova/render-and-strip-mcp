"""Tests for composed paginated-document collection."""

from __future__ import annotations

import asyncio

import pytest

from render_and_strip_mcp.agent_context import CollectionStage, PageState, PaginationAdvanceStage
from render_and_strip_mcp.agent_loop import StageRunner, StageRunResult
from render_and_strip_mcp.collection_strategy import collect_paginated_documents
from render_and_strip_mcp.config import AgentSettings, LlmSettings
from render_and_strip_mcp.errors import (
    ExecutionLimitError,
    PaginationTransitionError,
    UnsuccessfulStageOutcomeError,
)
from render_and_strip_mcp.playwright_tools import ToolCatalog
from render_and_strip_mcp.selected_content import CapturedContent
from render_and_strip_mcp.stage_models import (
    CollectionReport,
    PaginationAdvanceReport,
    SelectedRegion,
)


class UnusedProgressReporter:
    """Satisfy the runner dependency while stage execution is replaced."""

    async def accept(self, reasoning_fragment: str) -> None:
        raise AssertionError(f"unexpected reasoning: {reasoning_fragment}")

    async def flush_if_needed(self) -> None:
        raise AssertionError("unexpected progress flush")


def stage_runner() -> StageRunner:
    """Build a runner whose stage method can be replaced by each test."""

    async def unused_action(*arguments: object) -> PageState:
        raise AssertionError(f"unexpected browser action: {arguments}")

    return StageRunner(
        LlmSettings(
            model="test-model",
            api_base="https://model.example/v1",
            api_key="test-key",
        ),
        AgentSettings(),
        ToolCatalog([], {}),
        unused_action,
        UnusedProgressReporter(),  # type: ignore[arg-type]
    )


def captured_content(page_number: int) -> CapturedContent:
    """Create one source-aware selected region for strategy tests."""

    return CapturedContent(
        html=f"<main>Page {page_number}</main>",
        source_url=f"https://example.test/results?page={page_number}",
    )


def collection_report(page_state: PageState, *, complete: bool = True) -> CollectionReport:
    """Build a collection report targeting the current page's results region."""

    return CollectionReport(
        complete=complete,
        evidence=["Page retained." if complete else "A retained reveal remains."],
        selected_region_element="Results region",
        selected_region_target=f"results-{page_state.current_url[-1]}",
    )


def test_pagination_collects_each_page_before_advancing_and_carries_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every page is retained and captured before one fresh semantic advance iteration."""

    page_one = PageState("Page 1 snapshot", "https://example.test/results?page=1")
    page_two = PageState("Page 2 snapshot", "https://example.test/results?page=2")
    events: list[str] = []

    async def run_stage(
        self: StageRunner,
        stage: CollectionStage | PaginationAdvanceStage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self
        assert task == "Collect releases through version 2.0"
        if isinstance(stage, CollectionStage):
            assert stage.strategy == "retained-final-document"
            events.append(f"collect:{initial_state.observation}")
            return StageRunResult(collection_report(initial_state), initial_state)

        events.append(f"advance:{stage.captured_region_count}")
        if stage.captured_region_count == 1:
            assert stage.progress == ""
            return StageRunResult(
                PaginationAdvanceReport(
                    status="advanced",
                    progress="Page 1 remains newer than version 2.0.",
                    evidence=["Used the enabled immediate Next control."],
                ),
                page_two,
            )
        assert stage.progress == "Page 1 remains newer than version 2.0."
        return StageRunResult(
            PaginationAdvanceReport(
                status="complete",
                progress="Pages 1-2 reach the version 2.0 boundary.",
                evidence=["Established that later ordered pages are outside the cutoff."],
            ),
            initial_state,
        )

    captures = iter([captured_content(1), captured_content(2)])

    async def capture(selected_region: SelectedRegion) -> CapturedContent:
        capture = next(captures)
        assert selected_region.target == f"results-{capture.source_url[-1]}"
        events.append(f"capture:{capture.source_url[-1]}")
        return capture

    monkeypatch.setattr(StageRunner, "run", run_stage)

    result = asyncio.run(
        collect_paginated_documents(
            stage_runner(),
            "Collect releases through version 2.0",
            page_one,
            capture,
            25,
        )
    )

    assert result == [captured_content(1), captured_content(2)]
    assert events == [
        "collect:Page 1 snapshot",
        "capture:1",
        "advance:1",
        "collect:Page 2 snapshot",
        "capture:2",
        "advance:2",
    ]


def test_pagination_does_not_capture_or_advance_an_incomplete_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-page retained collection must complete before any document becomes output-eligible."""

    page_one = PageState("Page 1", "https://example.test/results?page=1")
    captured = False

    async def run_stage(
        self: StageRunner,
        stage: CollectionStage | PaginationAdvanceStage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, task
        assert isinstance(stage, CollectionStage)
        return StageRunResult(
            collection_report(initial_state, complete=False),
            initial_state,
        )

    async def capture(selected_region: SelectedRegion) -> CapturedContent:
        nonlocal captured
        del selected_region
        captured = True
        return captured_content(1)

    monkeypatch.setattr(StageRunner, "run", run_stage)

    with pytest.raises(
        UnsuccessfulStageOutcomeError,
        match="Retained-document collection did not complete",
    ):
        asyncio.run(
            collect_paginated_documents(
                stage_runner(), "Collect all releases", page_one, capture, 25
            )
        )

    assert captured is False


def test_pagination_rejects_completion_after_a_browser_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page reached by an advance action cannot be silently omitted by reporting completion."""

    page_one = PageState("Page 1", "https://example.test/results?page=1")
    page_two = PageState("Page 2", "https://example.test/results?page=2")

    async def run_stage(
        self: StageRunner,
        stage: CollectionStage | PaginationAdvanceStage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, task
        if isinstance(stage, CollectionStage):
            return StageRunResult(collection_report(initial_state), initial_state)
        return StageRunResult(
            PaginationAdvanceReport(
                status="complete",
                progress="The next page appeared to reach the cutoff.",
                evidence=["Activated Next before assessing the newly loaded page."],
            ),
            page_two,
            browser_action_count=1,
        )

    async def capture(selected_region: SelectedRegion) -> CapturedContent:
        del selected_region
        return captured_content(1)

    monkeypatch.setattr(StageRunner, "run", run_stage)

    with pytest.raises(PaginationTransitionError, match="completion after taking a browser action"):
        asyncio.run(
            collect_paginated_documents(
                stage_runner(), "Collect all releases", page_one, capture, 25
            )
        )


@pytest.mark.parametrize("transition", ["unchanged", "repeated"])
def test_pagination_rejects_unchanged_and_repeated_page_states(
    monkeypatch: pytest.MonkeyPatch,
    transition: str,
) -> None:
    """An advanced report cannot silently duplicate an unchanged or earlier result page."""

    page_one = PageState("Page 1", "https://example.test/results?page=1")
    page_two = PageState("Page 2", "https://example.test/results?page=2")
    advance_states = iter([page_one] if transition == "unchanged" else [page_two, page_one])

    async def run_stage(
        self: StageRunner,
        stage: CollectionStage | PaginationAdvanceStage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, task
        if isinstance(stage, CollectionStage):
            return StageRunResult(collection_report(initial_state), initial_state)
        return StageRunResult(
            PaginationAdvanceReport(
                status="advanced",
                progress=f"Assessed {stage.captured_region_count} pages.",
                evidence=["An immediate Next control appeared enabled."],
            ),
            next(advance_states),
        )

    capture_count = 0

    async def capture(selected_region: SelectedRegion) -> CapturedContent:
        nonlocal capture_count
        del selected_region
        capture_count += 1
        return captured_content(capture_count)

    monkeypatch.setattr(StageRunner, "run", run_stage)

    with pytest.raises(PaginationTransitionError, match=r"unchanged|previously collected"):
        asyncio.run(
            collect_paginated_documents(
                stage_runner(), "Collect all releases", page_one, capture, 25
            )
        )

    assert capture_count == (1 if transition == "unchanged" else 2)


@pytest.mark.parametrize("status", ["complete", "advanced"])
def test_pagination_assesses_completion_at_the_document_limit(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """The maximum page succeeds only when its advance assessment establishes completion."""

    page_one = PageState("Page 1", "https://example.test/results?page=1")
    page_two = PageState("Page 2", "https://example.test/results?page=2")

    async def run_stage(
        self: StageRunner,
        stage: CollectionStage | PaginationAdvanceStage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        del self, task
        if isinstance(stage, CollectionStage):
            return StageRunResult(collection_report(initial_state), initial_state)
        return StageRunResult(
            PaginationAdvanceReport(
                status=status,  # type: ignore[arg-type]
                progress="Assessed the configured maximum page.",
                evidence=["Checked the immediate Next control and task cutoff."],
            ),
            page_two,
        )

    async def capture(selected_region: SelectedRegion) -> CapturedContent:
        del selected_region
        return captured_content(1)

    monkeypatch.setattr(StageRunner, "run", run_stage)
    collection = collect_paginated_documents(
        stage_runner(), "Collect all releases", page_one, capture, 1
    )

    if status == "complete":
        assert asyncio.run(collection) == [captured_content(1)]
    else:
        with pytest.raises(ExecutionLimitError, match="limit reached before collection completion"):
            asyncio.run(collection)
