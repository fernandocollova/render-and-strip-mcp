"""Validated request-local handoffs between greedy browser-collection stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors import MalformedStageCompletionError

StageName: TypeAlias = Literal[
    "access",
    "discovery",
    "reconstruction",
    "collection",
    "pagination-advance",
]
CollectionStrategy: TypeAlias = Literal[
    "retained-final-document",
    "paginated-documents",
]
DiscoveryStrategy: TypeAlias = Literal[
    "retained-final-document",
    "paginated-documents",
    "unknown",
]
PaginationAdvanceStatus: TypeAlias = Literal["advanced", "complete"]


class StageReport(BaseModel):
    """Typed report the model returns through a local stage-completion tool.

    Subclasses define request-local handoffs between stages. Reports reject unknown fields and
    coercion so a model response cannot silently change the expected contract.
    """

    model_config = {"extra": "forbid", "strict": True}


class AccessCheckpoint(StageReport):
    """Handoff from access to reconstruction after discovery resets the page.

    It records the semantic page state to restore, not a browser-action replay log or extracted
    result data.
    """

    target_state: str = Field(
        min_length=1,
        description=(
            "Describe the user-visible page or view state to restore after reset, including "
            "relevant filters or selections. Do not include element references, selectors, "
            "action history, or extracted facts."
        ),
    )
    reconstruction_instructions: list[str] = Field(
        default_factory=list,
        description=(
            "List semantic instructions for restoring the target state after reset. Rediscover "
            "current controls; do not replay stale element references or selectors."
        ),
    )
    verification: list[str] = Field(
        min_length=1,
        description=(
            "List observable conditions that confirm the target state is restored after reset."
        ),
    )

    @field_validator("target_state")
    @classmethod
    def validate_target_state(cls, value: str) -> str:
        """Reject blank semantic target descriptions."""

        _require_semantic_text(value, "target_state")
        return value

    @field_validator("reconstruction_instructions", "verification")
    @classmethod
    def validate_semantic_text_list(cls, values: list[str], info: object) -> list[str]:
        """Reject blank instructions and verification conditions."""

        field_name = getattr(info, "field_name", "semantic evidence")
        for value in values:
            _require_semantic_text(value, field_name)
        return values


class DiscoveryReport(StageReport):
    """Handoff from discovery that selects or rejects a collection strategy.

    Its evidence explains which supported document-retention behavior was established, if any.
    """

    strategy: DiscoveryStrategy = Field(
        description=(
            "Choose retained-final-document only when relevant revealed content can coexist in "
            "one final visible document. Choose paginated-documents only when an immediate "
            "same-origin next-page action replaces the result document and each page supports "
            "retained-document collection. Otherwise choose unknown."
        )
    )
    evidence: list[str] = Field(
        min_length=1,
        description="List observations or probe results that justify the selected strategy.",
    )

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require evidence for either permitted discovery outcome."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


class ReconstructionReport(StageReport):
    """Outcome of attempting to restore an access checkpoint after reset."""

    verified: bool = Field(
        description=(
            "State whether every checkpoint verification condition was observed after reset."
        )
    )
    evidence: list[str] = Field(
        min_length=1,
        description="List observations supporting the reconstruction verification result.",
    )

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require semantic evidence for the reconstruction assessment."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


@dataclass(frozen=True)
class SelectedRegion:
    """Typed handoff for one validated current task-content element."""

    element: str
    target: str


class CollectionReport(StageReport):
    """Outcome of exhausting the selected retained-document collection strategy."""

    complete: bool = Field(
        description=(
            "State whether all relevant non-destructive retained-document reveal mechanisms were "
            "exhausted and prior target content remained visible."
        )
    )
    evidence: list[str] = Field(
        min_length=1,
        description="List observations supporting the collection-completeness result.",
    )
    selected_region_element: str = Field(
        min_length=1,
        description=(
            "Human-readable description of the one contiguous element containing all content "
            "relevant to the caller task and excluding surrounding page-level chrome."
        ),
    )
    selected_region_target: str = Field(
        min_length=1,
        description=(
            "Exact Playwright target reference for that element from the newest fresh browser "
            "observation."
        ),
    )

    @field_validator("selected_region_element", "selected_region_target")
    @classmethod
    def validate_selection_text(cls, value: str, info: object) -> str:
        """Reject blank element descriptions and snapshot targets."""

        _require_semantic_text(value, getattr(info, "field_name", "selected region"))
        return value

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require semantic evidence for the collection assessment."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values

    @property
    def selected_region(self) -> SelectedRegion:
        """Expose the two validated flat completion fields as one concrete handoff."""

        return SelectedRegion(self.selected_region_element, self.selected_region_target)


class PaginationAdvanceReport(StageReport):
    """Outcome and compact cumulative handoff from one page-advance iteration."""

    status: PaginationAdvanceStatus = Field(
        description=(
            "Report advanced only after activating one enabled immediate next-page control. "
            "Report complete only when no such control remains or established ordering proves "
            "that later pages cannot satisfy the task."
        )
    )
    progress: str = Field(
        min_length=1,
        max_length=4000,
        description=(
            "A compact cumulative semantic summary of pagination progress needed to assess later "
            "pages. Replace the prior summary; do not include raw page content or action history."
        ),
    )
    evidence: list[str] = Field(
        min_length=1,
        description="List observations supporting the advancement or completion result.",
    )

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, value: str) -> str:
        """Reject a blank cross-page progress handoff."""

        _require_semantic_text(value, "progress")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require semantic evidence for the pagination assessment."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


StageReportValue: TypeAlias = (
    AccessCheckpoint
    | DiscoveryReport
    | ReconstructionReport
    | CollectionReport
    | PaginationAdvanceReport
)


@dataclass(frozen=True)
class CompletionTool:
    """One stage's local function schema and strict report parser.

    The model calls this tool when it reaches what it needs to in the browser.
    """

    name: str
    report_type: type[StageReport]

    @property
    def openai_schema(self) -> dict[str, object]:
        """Return the model-visible function schema for submitting this report."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Complete this stage with its validated report.",
                "parameters": self.report_type.model_json_schema(),
            },
        }

    def parse(self, arguments: dict[str, object]) -> StageReportValue:
        """Validate model-returned arguments as this completion tool's report type."""

        try:
            return self.report_type.model_validate(arguments)
        except ValidationError as error:
            raise MalformedStageCompletionError(
                f"Completion tool {self.name!r} supplied a malformed report."
            ) from error


ACCESS_COMPLETION_TOOL = CompletionTool(
    "complete_access",
    AccessCheckpoint,
)
DISCOVERY_COMPLETION_TOOL = CompletionTool(
    "complete_discovery",
    DiscoveryReport,
)
RECONSTRUCTION_COMPLETION_TOOL = CompletionTool(
    "complete_reconstruction",
    ReconstructionReport,
)
COLLECTION_COMPLETION_TOOL = CompletionTool(
    "complete_collection",
    CollectionReport,
)
PAGINATION_ADVANCE_COMPLETION_TOOL = CompletionTool(
    "complete_pagination_advance",
    PaginationAdvanceReport,
)


def _require_semantic_text(value: str, field_name: str) -> None:
    """Reject values that have a string shape but no semantic content."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
