"""Validated request-local handoffs between greedy browser-collection stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors import MalformedStageCompletionError

StageName: TypeAlias = Literal["access", "discovery", "reconstruction", "collection"]
DiscoveryStrategy: TypeAlias = Literal["retained-final-document", "unknown"]


class StageReport(BaseModel):
    """Base model that rejects untyped or extraneous stage-completion data."""

    model_config = {"extra": "forbid", "strict": True}


class AccessCheckpoint(StageReport):
    """Semantic state that reconstruction must restore after the discovery reset."""

    target_state: str = Field(min_length=1)
    reconstruction_instructions: list[str] = Field(default_factory=list)
    verification: list[str] = Field(min_length=1)

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
    """Validated strategy-selection evidence from the discovery stage."""

    strategy: DiscoveryStrategy
    evidence: list[str] = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require evidence for either permitted discovery outcome."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


class ReconstructionReport(StageReport):
    """Validated reconstruction verification result."""

    verified: bool
    evidence: list[str] = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require semantic evidence for the reconstruction assessment."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


class CollectionReport(StageReport):
    """Validated retained-document collection completion result."""

    complete: bool
    evidence: list[str] = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        """Require semantic evidence for the collection assessment."""

        for value in values:
            _require_semantic_text(value, "evidence")
        return values


StageReportValue: TypeAlias = (
    AccessCheckpoint | DiscoveryReport | ReconstructionReport | CollectionReport
)


@dataclass(frozen=True)
class CompletionTool:
    """One stage's local function schema and strict report parser."""

    stage_name: StageName
    name: str
    report_type: type[StageReport]

    @property
    def openai_schema(self) -> dict[str, object]:
        """Return the local completion function in OpenAI callable-tool format."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": f"Complete the {self.stage_name} stage with its validated report.",
                "parameters": self.report_type.model_json_schema(),
            },
        }

    def parse(self, arguments: dict[str, object]) -> StageReportValue:
        """Validate serialized local completion arguments at the model boundary."""

        try:
            return self.report_type.model_validate(arguments)
        except ValidationError as error:
            raise MalformedStageCompletionError(
                f"The {self.stage_name} completion report is malformed."
            ) from error


ACCESS_COMPLETION_TOOL = CompletionTool("access", "complete_access", AccessCheckpoint)
DISCOVERY_COMPLETION_TOOL = CompletionTool("discovery", "complete_discovery", DiscoveryReport)
RECONSTRUCTION_COMPLETION_TOOL = CompletionTool(
    "reconstruction", "complete_reconstruction", ReconstructionReport
)
COLLECTION_COMPLETION_TOOL = CompletionTool("collection", "complete_collection", CollectionReport)


def _require_semantic_text(value: str, field_name: str) -> None:
    """Reject values that have a string shape but no semantic content."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
