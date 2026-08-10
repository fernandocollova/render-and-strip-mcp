"""Tests for strict request-local staged browser-collection reports."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from render_and_strip_mcp.errors import MalformedStageCompletionError
from render_and_strip_mcp.playwright_tools import validate_input_schema
from render_and_strip_mcp.stage_models import (
    ACCESS_COMPLETION_TOOL,
    COLLECTION_COMPLETION_TOOL,
    DISCOVERY_COMPLETION_TOOL,
    PAGINATION_ADVANCE_COMPLETION_TOOL,
    RECONSTRUCTION_COMPLETION_TOOL,
    AccessCheckpoint,
    CollectionReport,
    CompletionTool,
    DiscoveryReport,
    PaginationAdvanceReport,
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
    collection = CollectionReport(
        complete=True,
        evidence=["No relevant controls remain."],
        selected_region_element="Release list",
        selected_region_target="e42",
    )
    pagination = PaginationAdvanceReport(
        status="advanced",
        progress="Captured pages 1-2; releases remain newer than the requested cutoff.",
        evidence=["Activated the enabled Next control and observed page 2."],
    )

    assert checkpoint.reconstruction_instructions == ["Open the product report."]
    assert discovery.strategy == "retained-final-document"
    assert reconstruction.verified is True
    assert collection.complete is True
    assert collection.selected_region.target == "e42"
    assert pagination.status == "advanced"


def test_discovery_accepts_paginated_documents_strategy() -> None:
    """Discovery can select proven replacing same-origin result pagination."""

    report = DiscoveryReport(
        strategy="paginated-documents",
        evidence=["The enabled Next control replaced page 1 with same-origin page 2."],
    )

    assert report.strategy == "paginated-documents"


@pytest.mark.parametrize(
    ("model_type", "arguments"),
    [
        (AccessCheckpoint, {"target_state": " ", "verification": ["Visible."]}),
        (AccessCheckpoint, {"target_state": "Visible.", "verification": [" "]}),
        (DiscoveryReport, {"strategy": "other", "evidence": ["Observed."]}),
        (DiscoveryReport, {"strategy": "unknown", "evidence": []}),
        (ReconstructionReport, {"verified": True, "evidence": [" "]}),
        (
            CollectionReport,
            {
                "complete": True,
                "evidence": [],
                "selected_region_element": "Report",
                "selected_region_target": "e42",
            },
        ),
        (
            CollectionReport,
            {
                "complete": True,
                "evidence": ["Complete."],
                "selected_region_element": " ",
                "selected_region_target": "e42",
            },
        ),
        (
            CollectionReport,
            {
                "complete": True,
                "evidence": ["Complete."],
                "selected_region_element": "Report",
                "selected_region_target": " ",
            },
        ),
        (CollectionReport, {"complete": True, "evidence": ["Complete."]}),
        (
            PaginationAdvanceReport,
            {"status": "stopped", "progress": "At page 2.", "evidence": ["Terminal."]},
        ),
        (
            PaginationAdvanceReport,
            {"status": "complete", "progress": " ", "evidence": ["Terminal."]},
        ),
        (
            PaginationAdvanceReport,
            {"status": "complete", "progress": "At terminal page.", "evidence": []},
        ),
        (
            PaginationAdvanceReport,
            {"status": "complete", "progress": "x" * 4001, "evidence": ["Terminal."]},
        ),
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

    with pytest.raises(MalformedStageCompletionError, match=r"complete_access.*malformed"):
        ACCESS_COMPLETION_TOOL.parse({"target_state": "Ready", "verification": []})

    assert ACCESS_COMPLETION_TOOL.openai_schema["function"]["name"] == "complete_access"  # type: ignore[index]


@pytest.mark.parametrize(
    "completion_tool",
    [
        ACCESS_COMPLETION_TOOL,
        DISCOVERY_COMPLETION_TOOL,
        RECONSTRUCTION_COMPLETION_TOOL,
        COLLECTION_COMPLETION_TOOL,
        PAGINATION_ADVANCE_COMPLETION_TOOL,
    ],
)
def test_completion_tool_schemas_describe_every_report_field(
    completion_tool: CompletionTool,
) -> None:
    """Model-visible completion schemas explain every field they require or accept."""

    function = completion_tool.openai_schema["function"]
    assert isinstance(function, dict)
    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    properties = parameters["properties"]
    assert isinstance(properties, dict)
    for property_schema in properties.values():
        assert isinstance(property_schema, dict)
        description = property_schema.get("description")
        assert isinstance(description, str) and description.strip()
    validate_input_schema(completion_tool.name, parameters)


def test_collection_completion_schema_is_flat() -> None:
    """The model-facing collection contract contains no reference-based nested schema."""

    function = COLLECTION_COMPLETION_TOOL.openai_schema["function"]
    assert isinstance(function, dict)
    parameters = function["parameters"]
    assert isinstance(parameters, dict)

    assert "$defs" not in parameters
    assert "$ref" not in repr(parameters)
    assert parameters["required"] == [
        "complete",
        "evidence",
        "selected_region_element",
        "selected_region_target",
    ]
