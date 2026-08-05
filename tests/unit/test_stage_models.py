"""Tests for strict request-local staged browser-collection reports."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from render_and_strip_mcp.errors import MalformedStageCompletionError
from render_and_strip_mcp.stage_models import (
    ACCESS_COMPLETION_TOOL,
    AccessCheckpoint,
    CollectionReport,
    DiscoveryReport,
    ReconstructionReport,
)


def test_stage_reports_accept_valid_semantic_handoffs() -> None:
    """Each stage model preserves its supported typed handoff shape."""

    checkpoint = AccessCheckpoint(
        target_state="The product report is visible.",
        reconstruction_instructions=["Open the product report."],
        verification=["The product report heading is visible."],
    )
    discovery = DiscoveryReport(
        strategy="retained-final-document", evidence=["Load-more appends cards."]
    )
    reconstruction = ReconstructionReport(
        verified=True, evidence=["The report heading is visible."]
    )
    collection = CollectionReport(complete=True, evidence=["No relevant controls remain."])

    assert checkpoint.reconstruction_instructions == ["Open the product report."]
    assert discovery.strategy == "retained-final-document"
    assert reconstruction.verified is True
    assert collection.complete is True


@pytest.mark.parametrize(
    ("model_type", "arguments"),
    [
        (AccessCheckpoint, {"target_state": " ", "verification": ["Visible."]}),
        (AccessCheckpoint, {"target_state": "Visible.", "verification": [" "]}),
        (DiscoveryReport, {"strategy": "other", "evidence": ["Observed."]}),
        (DiscoveryReport, {"strategy": "unknown", "evidence": []}),
        (ReconstructionReport, {"verified": True, "evidence": [" "]}),
        (CollectionReport, {"complete": True, "evidence": []}),
    ],
)
def test_stage_reports_reject_invalid_or_empty_semantic_data(
    model_type: type[object], arguments: dict[str, object]
) -> None:
    """Blank evidence, unsupported discovery outcomes, and malformed data fail at ingress."""

    with pytest.raises(ValidationError):
        model_type.model_validate(arguments)  # type: ignore[attr-defined]


def test_completion_tool_translates_validation_failures_to_domain_error() -> None:
    """Model-supplied local tool arguments do not leak validation implementation details."""

    with pytest.raises(MalformedStageCompletionError, match="access completion"):
        ACCESS_COMPLETION_TOOL.parse({"target_state": "Ready", "verification": []})

    assert ACCESS_COMPLETION_TOOL.openai_schema["function"]["name"] == "complete_access"  # type: ignore[index]
