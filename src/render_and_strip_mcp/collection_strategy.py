"""Concrete greedy collection strategies for final rendered documents."""

from __future__ import annotations

from typing import cast

from .agent_context import CollectionStage, PageState
from .agent_loop import StageRunner
from .errors import UnsuccessfulStageOutcomeError
from .stage_models import CollectionReport


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


COLLECTION_STRATEGIES = {"retained-final-document": collect_retained_final_document}
