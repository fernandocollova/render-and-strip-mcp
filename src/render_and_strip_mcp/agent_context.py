"""Deterministic, compact model context for browser-agent turns."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = (
    "You are a browser agent. The service has already loaded the caller's requested initial "
    "page and will extract clean HTML after you finish. If the caller only asks to clean the "
    "current page, reply exactly TASK_COMPLETE without a tool call. Do not call browser tools "
    "or functions for that task. Otherwise, use the supplied Playwright tools only when "
    "necessary to complete the caller's task.\n"
    "Use one tool call at a time. Work only with the current top-level page and finish by "
    "responding without a tool call when the task is complete. Do not ask the caller for "
    "clarification."
)

ArgumentKind = Literal["structural", "payload"]
TOOL_ARGUMENT_KINDS: dict[str, dict[str, ArgumentKind]] = {
    "browser_click": {
        "element": "structural",
        "target": "structural",
        "doubleClick": "structural",
        "button": "structural",
        "modifiers": "structural",
    },
    "browser_console_messages": {"level": "structural", "all": "structural", "filename": "payload"},
    "browser_drag": {
        "startElement": "structural",
        "startTarget": "structural",
        "endElement": "structural",
        "endTarget": "structural",
    },
    "browser_evaluate": {
        "element": "structural",
        "target": "structural",
        "function": "payload",
        "filename": "payload",
    },
    "browser_fill_form": {"fields": "payload"},
    "browser_find": {"text": "payload", "regex": "payload"},
    "browser_handle_dialog": {"accept": "structural", "promptText": "payload"},
    "browser_hover": {"element": "structural", "target": "structural"},
    "browser_navigate": {"url": "structural"},
    "browser_navigate_back": {},
    "browser_network_request": {"index": "structural", "part": "structural", "filename": "payload"},
    "browser_network_requests": {
        "static": "structural",
        "filter": "payload",
        "filename": "payload",
    },
    "browser_press_key": {"key": "structural"},
    "browser_resize": {"width": "structural", "height": "structural"},
    "browser_select_option": {
        "element": "structural",
        "target": "structural",
        "values": "payload",
    },
    "browser_snapshot": {
        "target": "structural",
        "depth": "structural",
        "boxes": "structural",
        "filename": "payload",
    },
    "browser_take_screenshot": {
        "element": "structural",
        "target": "structural",
        "type": "structural",
        "fullPage": "structural",
        "scale": "structural",
        "filename": "payload",
    },
    "browser_type": {
        "element": "structural",
        "target": "structural",
        "text": "payload",
        "submit": "structural",
        "slowly": "structural",
    },
    "browser_wait_for": {"time": "structural", "text": "payload", "textGone": "payload"},
}


@dataclass(frozen=True)
class BrowserActionResult:
    """Compact state from one completed browser action."""

    observation: str
    current_url: str
    succeeded: bool = True


def build_model_messages(
    task: str,
    action_log: list[str],
    current_url: str,
    newest_observation: str,
) -> list[dict[str, str]]:
    """Build the exact fresh system and user messages for one inner model turn."""

    serialized_actions = "\n".join(action_log) if action_log else "(no model-directed actions yet)"
    user_message = (
        f"Task:\n{task}\n\n"
        f"Actions:\n{serialized_actions}\n\n"
        f"Current top-level URL:\n{current_url}\n\n"
        f"Newest browser observation:\n{newest_observation}"
    )
    return [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": user_message},
    ]


def format_browser_action(
    tool_name: str,
    arguments: Mapping[str, Any],
    result: BrowserActionResult,
) -> str:
    """Create a deterministic action summary without copying payload argument values."""

    argument_kinds = TOOL_ARGUMENT_KINDS.get(tool_name)
    if argument_kinds is None:
        logger.warning("No dedicated action formatter is defined for Playwright tool %s", tool_name)
        argument_summary = ", ".join(f"{name}=<omitted>" for name in sorted(arguments))
    else:
        argument_summary = _format_known_tool_arguments(arguments, argument_kinds)
    status = "success" if result.succeeded else "failure"
    return f"{tool_name}({argument_summary}) -> {status}; current URL: {result.current_url}"


def _format_known_tool_arguments(
    arguments: Mapping[str, Any], argument_kinds: Mapping[str, ArgumentKind]
) -> str:
    """Format explicitly structural arguments and count known payload arguments."""

    summary_parts: list[str] = []
    for name in sorted(argument_kinds):
        if name not in arguments:
            continue
        value = arguments[name]
        if argument_kinds[name] == "structural":
            summary_parts.append(f"{name}={json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        else:
            summary_parts.append(f"{name}=<{_payload_size(value)}>")
    unknown_arguments = sorted(set(arguments) - set(argument_kinds))
    summary_parts.extend(f"{name}=<omitted>" for name in unknown_arguments)
    return ", ".join(summary_parts)


def _payload_size(value: object) -> str:
    """Describe payload size without preserving any payload value."""

    if isinstance(value, str):
        return f"{len(value)} chars omitted"
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return f"{len(value)} items omitted"
    return "value omitted"
