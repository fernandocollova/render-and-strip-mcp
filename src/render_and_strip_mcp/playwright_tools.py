"""OpenAI-schema translation for discovered Playwright MCP tools."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

from fastmcp import Client
from mcp.types import Tool

from .errors import StageToolCollisionError, ToolSchemaError
from .stage_models import CompletionTool

RESERVED_TOOL_NAMES = frozenset({"browser_tabs", "browser_snapshot", "browser_close"})
EXCLUDED_TOOL_NAMES = frozenset(
    {"browser_run_code_unsafe", "browser_file_upload", "browser_drop", "browser_install"}
)
OPENAI_TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$ref",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "if",
        "then",
        "else",
        "patternProperties",
        "dependentRequired",
        "dependentSchemas",
        "unevaluatedProperties",
    }
)


@dataclass(frozen=True)
class ToolCatalog:
    """Eligible tools and reversible names for a single remote MCP session."""

    openai_tools: list[dict[str, object]]
    remote_name_by_model_name: dict[str, str]
    completion_tool: CompletionTool | None = None

    def restricted_to(self, allowed_remote_names: Set[str]) -> ToolCatalog:
        """Retain only discovered remote tools named by an allowlist intersection."""

        allowed_model_names = allowed_remote_names.intersection(self.remote_name_by_model_name)
        retained_schema_names = set(allowed_model_names)
        if self.completion_tool is not None:
            retained_schema_names.add(self.completion_tool.name)
        return ToolCatalog(
            openai_tools=[
                tool
                for tool in self.openai_tools
                if cast(dict[str, object], tool["function"])["name"] in retained_schema_names
            ],
            remote_name_by_model_name={
                model_name: remote_name
                for model_name, remote_name in self.remote_name_by_model_name.items()
                if model_name in allowed_model_names
            },
            completion_tool=self.completion_tool,
        )

    def with_completion_tool(self, completion_tool: CompletionTool) -> ToolCatalog:
        """Add one locally routed stage-completion schema to this request's catalog."""

        if completion_tool.name in self.remote_name_by_model_name:
            raise StageToolCollisionError(
                f"Local completion tool {completion_tool.name!r} conflicts with a remote "
                "Playwright tool."
            )
        validate_input_schema(
            completion_tool.name,
            completion_tool.report_type.model_json_schema(),
        )
        return ToolCatalog(
            openai_tools=[*self.openai_tools, completion_tool.openai_schema],
            remote_name_by_model_name=self.remote_name_by_model_name,
            completion_tool=completion_tool,
        )


@dataclass(frozen=True)
class PlaywrightSession:
    """A client connection and callable catalog for one Playwright MCP session."""

    client: Client
    tool_catalog: ToolCatalog


@asynccontextmanager
async def open_playwright_session(endpoint: str) -> AsyncGenerator[PlaywrightSession]:
    """Open one HTTP MCP client session and discover its callable tools."""

    async with Client(endpoint) as client:
        discovered_tools = await client.list_tools()
        yield PlaywrightSession(client=client, tool_catalog=build_tool_catalog(discovered_tools))


def build_tool_catalog(tools: list[Tool]) -> ToolCatalog:
    """Translate eligible remote tools to deterministic OpenAI function-tool schemas."""

    remote_name_by_model_name: dict[str, str] = {}
    openai_tools: list[dict[str, object]] = []

    for tool in sorted(tools, key=lambda discovered_tool: discovered_tool.name):
        if tool.name in RESERVED_TOOL_NAMES or tool.name in EXCLUDED_TOOL_NAMES:
            continue
        if not OPENAI_TOOL_NAME.fullmatch(tool.name):
            raise ToolSchemaError(f"Tool {tool.name!r} has an invalid OpenAI function name.")
        if tool.name in remote_name_by_model_name:
            raise ToolSchemaError(f"Playwright MCP published duplicate tool {tool.name!r}.")
        validate_input_schema(tool.name, tool.inputSchema)
        if not isinstance(tool.description, str) or not tool.description.strip():
            raise ToolSchemaError(f"Tool {tool.name!r} must have a description.")
        remote_name_by_model_name[tool.name] = tool.name
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
        )

    return ToolCatalog(
        openai_tools=openai_tools,
        remote_name_by_model_name=remote_name_by_model_name,
    )


def validate_input_schema(tool_name: str, input_schema: object) -> None:
    """Reject tool schemas outside the portable OpenAI function-schema subset."""

    if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
        raise ToolSchemaError(f"Tool {tool_name!r} must have an object input schema.")
    validate_schema_fragment(tool_name, input_schema, "input schema")


def validate_schema_fragment(tool_name: str, schema: dict[str, Any], location: str) -> None:
    """Validate one schema object recursively without silently discarding semantics."""

    unsupported_keywords = UNSUPPORTED_SCHEMA_KEYWORDS.intersection(schema)
    if unsupported_keywords:
        unsupported = ", ".join(sorted(unsupported_keywords))
        raise ToolSchemaError(
            f"Tool {tool_name!r} has unsupported {location} keywords: {unsupported}."
        )

    schema_type = schema.get("type")
    if schema_type is not None and not isinstance(schema_type, str):
        raise ToolSchemaError(f"Tool {tool_name!r} has a non-string type in {location}.")
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ToolSchemaError(f"Tool {tool_name!r} has invalid properties in {location}.")
        for property_name, property_schema in properties.items():
            if not isinstance(property_name, str) or not isinstance(property_schema, dict):
                raise ToolSchemaError(
                    f"Tool {tool_name!r} has invalid property data in {location}."
                )
            validate_schema_fragment(tool_name, property_schema, f"{location}.{property_name}")
    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list) or not all(isinstance(item, str) for item in required)
    ):
        raise ToolSchemaError(f"Tool {tool_name!r} has invalid required fields in {location}.")
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise ToolSchemaError(f"Tool {tool_name!r} has unsupported tuple items in {location}.")
        validate_schema_fragment(tool_name, items, f"{location}.items")
