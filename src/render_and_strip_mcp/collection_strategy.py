"""Concrete greedy collection strategies for final rendered documents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .agent_context import PageState
from .agent_loop import StageRunResult, run_stage
from .config import AgentSettings, LlmSettings
from .errors import UnsuccessfulStageOutcomeError
from .playwright_tools import ToolCatalog
from .reasoning_progress import ReasoningProgressReporter
from .stage_models import COLLECTION_COMPLETION_TOOL, CollectionReport

BrowserAction = Callable[[str, dict[str, object]], Awaitable[PageState]]


async def collect_retained_final_document(
    llm_settings: LlmSettings,
    agent_settings: AgentSettings,
    tool_catalog: ToolCatalog,
    task: str,
    initial_state: PageState,
    execute_browser_action: BrowserAction,
    reasoning_progress: ReasoningProgressReporter | None = None,
) -> PageState:
    """Exhaust retainable page/view content and reject incomplete collection evidence."""

    result = await run_stage(
        llm_settings,
        agent_settings,
        tool_catalog,
        COLLECTION_COMPLETION_TOOL,
        task,
        initial_state,
        execute_browser_action,
        reasoning_progress,
        strategy="retained-final-document",
    )
    report = _collection_report(result)
    if not report.complete:
        raise UnsuccessfulStageOutcomeError("Retained-document collection did not complete.")
    return result.page_state


def _collection_report(result: StageRunResult) -> CollectionReport:
    """Narrow the completion type guaranteed by the collection tool schema."""

    if not isinstance(result.report, CollectionReport):
        raise UnsuccessfulStageOutcomeError("Collection returned the wrong completion report.")
    return result.report


COLLECTION_STRATEGIES = {"retained-final-document": collect_retained_final_document}
