"""Concrete greedy collection strategies for rendered documents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, cast

from .agent_context import CollectionStage, PageState, PaginationAdvanceStage
from .agent_loop import StageRunner
from .errors import ExecutionLimitError, PaginationTransitionError, UnsuccessfulStageOutcomeError
from .rendered_document import RenderedDocument
from .stage_models import CollectionReport, CollectionStrategy, PaginationAdvanceReport

CaptureDocument: TypeAlias = Callable[[], Awaitable[RenderedDocument]]
CollectionHandler: TypeAlias = Callable[
    [StageRunner, str, PageState, CaptureDocument, int],
    Awaitable[list[RenderedDocument]],
]
PageIdentity: TypeAlias = tuple[str, str]


async def collect_retained_final_document(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
) -> PageState:
    """Exhaust retainable page/view content and reject incomplete collection evidence."""

    result = await stage_runner.run(
        CollectionStage("retained-final-document"),
        task,
        initial_state,
    )
    report = cast(CollectionReport, result.report)
    if not report.complete:
        raise UnsuccessfulStageOutcomeError("Retained-document collection did not complete.")
    return result.page_state


async def collect_retained_document_strategy(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
    capture_document: CaptureDocument,
    max_paginated_documents: int,
) -> list[RenderedDocument]:
    """Collect and capture the one final document for the retained strategy."""

    del max_paginated_documents
    await collect_retained_final_document(stage_runner, task, initial_state)
    return [await capture_document()]


async def collect_paginated_documents(
    stage_runner: StageRunner,
    task: str,
    initial_state: PageState,
    capture_document: CaptureDocument,
    max_paginated_documents: int,
) -> list[RenderedDocument]:
    """Compose retained collection and semantic advancement over replacing result pages."""

    captured_documents: list[RenderedDocument] = []
    collected_page_identities: set[PageIdentity] = set()
    pagination_progress = ""
    current_state = initial_state

    while True:
        current_state = await collect_retained_final_document(stage_runner, task, current_state)
        current_identity = _page_identity(current_state)
        if current_identity in collected_page_identities:
            raise PaginationTransitionError(
                "Paginated collection reached a previously collected page state."
            )
        collected_page_identities.add(current_identity)
        captured_documents.append(await capture_document())

        advance_result = await stage_runner.run(
            PaginationAdvanceStage(
                captured_document_count=len(captured_documents),
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
            return captured_documents
        if len(captured_documents) >= max_paginated_documents:
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
