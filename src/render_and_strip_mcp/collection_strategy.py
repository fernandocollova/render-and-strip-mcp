"""Concrete greedy collection strategies for selected rendered content."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, cast

from .agent_context import CollectionStage, PageState, PaginationAdvanceStage
from .agent_loop import StageRunner
from .errors import ExecutionLimitError, PaginationTransitionError, UnsuccessfulStageOutcomeError
from .selected_content import CapturedContent
from .stage_models import (
    CollectionReport,
    CollectionStrategy,
    PaginationAdvanceReport,
    SelectedRegion,
)

CaptureContent: TypeAlias = Callable[[SelectedRegion], Awaitable[CapturedContent]]
CollectionHandler: TypeAlias = Callable[
    [StageRunner, str, PageState, CaptureContent, int],
    Awaitable[list[CapturedContent]],
]
PageIdentity: TypeAlias = tuple[str, str]


async def collect_retained_final_document(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
) -> tuple[PageState, SelectedRegion]:
    """Exhaust retainable page/view content and reject incomplete collection evidence."""

    result = await stage_runner.run(
        CollectionStage("retained-final-document"),
        task,
        initial_state,
    )
    report = cast(CollectionReport, result.report)
    if not report.complete:
        raise UnsuccessfulStageOutcomeError("Retained-document collection did not complete.")
    return result.page_state, report.selected_region


async def collect_retained_document_strategy(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
    capture_content: CaptureContent,
    max_paginated_documents: int,
) -> list[CapturedContent]:
    """Collect and capture one selected region for the retained strategy."""

    del max_paginated_documents
    _, selected_region = await collect_retained_final_document(stage_runner, task, initial_state)
    return [await capture_content(selected_region)]


async def collect_paginated_documents(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
    capture_content: CaptureContent,
    max_paginated_documents: int,
) -> list[CapturedContent]:
    """Compose retained collection and semantic advancement over replacing result pages."""

    captured_content: list[CapturedContent] = []
    collected_page_identities: set[PageIdentity] = set()
    pagination_progress = ""
    current_state = initial_state

    while True:
        current_state, selected_region = await collect_retained_final_document(
            stage_runner, task, current_state
        )
        current_identity = _page_identity(current_state)
        if current_identity in collected_page_identities:
            raise PaginationTransitionError(
                "Paginated collection reached a previously collected page state."
            )
        collected_page_identities.add(current_identity)
        captured_content.append(await capture_content(selected_region))

        advance_result = await stage_runner.run(
            PaginationAdvanceStage(
                captured_region_count=len(captured_content),
                progress=pagination_progress,
            ),
            task,
            current_state,
        )
        advance_report = cast(PaginationAdvanceReport, advance_result.report)
        pagination_progress = advance_report.progress
        if advance_report.status == "complete":
            if advance_result.browser_action_count:
                raise PaginationTransitionError(
                    "Pagination reported completion after taking a browser action."
                )
            return captured_content
        if len(captured_content) >= max_paginated_documents:
            raise ExecutionLimitError(
                "Paginated-document limit reached before collection completion."
            )

        next_identity = _page_identity(advance_result.page_state)
        if next_identity == current_identity:
            raise PaginationTransitionError(
                "Pagination advancement reported success but left the page state unchanged."
            )
        if next_identity in collected_page_identities:
            raise PaginationTransitionError(
                "Pagination advancement returned to a previously collected page state."
            )
        current_state = advance_result.page_state


def _page_identity(page_state: PageState) -> PageIdentity:
    """Return the exact fresh state used for deterministic unchanged and repeat detection."""

    return page_state.current_url, page_state.observation


COLLECTION_STRATEGIES: dict[CollectionStrategy, CollectionHandler] = {
    "retained-final-document": collect_retained_document_strategy,
    "paginated-documents": collect_paginated_documents,
}
