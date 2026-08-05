"""Deterministic, compact model context for browser-agent turns."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .stage_models import AccessCheckpoint, DiscoveryStrategy, StageName

logger = logging.getLogger(__name__)

STAGE_SYSTEM_PROMPTS: dict[StageName, str] = {
    "access": (
        "Reach the caller's requested page, report, view, or filter state. Treat the task as "
        "page/view retrieval, not a request to extract individual facts. Rediscover controls "
        "from the current observation. If the state is visibly pending, use an eligible semantic "
        "wait or investigation action. Complete only by calling complete_access with a semantic "
        "target state, any reconstruction instructions, and verification conditions."
    ),
    "discovery": (
        "Inspect the current target page/view for relevant reveal mechanisms. Safely probe when "
        "needed to establish behavior, without a fixed probe count. Choose retained-final-document "
        "only when revealed target content can coexist in the final visible document; choose "
        "unknown for unsafe, unproven, replacing, virtualized, mixed, or ambiguous behavior. "
        "Use semantic waits while effects are pending. Complete only by calling complete_discovery "
        "with strategy and evidence."
    ),
    "reconstruction": (
        "Reconstruct the supplied semantic checkpoint from the reset page. Rediscover current "
        "controls; never replay stale references. Follow its semantic instructions, use eligible "
        "semantic waits for pending effects, and assess every verification condition. Complete "
        "only by calling complete_reconstruction with verified and evidence."
    ),
    "collection": (
        "Exhaust non-destructive, retained-document reveal mechanisms for the requested page/view, "
        "including scrolling, lazy loading, additive controls, and expansions that can remain open "
        "simultaneously. Use semantic waits for visibly pending effects. Preserve earlier target "
        "content and make a final verification sweep for no new content, unused relevant controls, "
        "pending state, or lost content. Complete only by calling complete_collection with "
        "complete and evidence."
    ),
}

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
class PageState:
    """Fresh orchestration-owned state for the tracked original browser tab."""

    observation: str
    current_url: str
    succeeded: bool = True


BrowserActionResult = PageState


def build_stage_messages(
    stage_name: StageName,
    task: str,
    action_log: list[str],
    current_state: PageState,
    checkpoint: AccessCheckpoint | None = None,
    strategy: DiscoveryStrategy | None = None,
    preceding_state: PageState | None = None,
) -> list[dict[str, str]]:
    """Build the exact fresh system and user messages for one inner model turn."""

    serialized_actions = "\n".join(action_log) if action_log else "(no model-directed actions yet)"
    message_parts = [
        f"Task:\n{task}\n\n"
        f"Actions:\n{serialized_actions}\n\n"
        f"Current top-level URL:\n{current_state.current_url}\n\n"
        f"Newest fresh browser observation:\n{current_state.observation}"
    ]
    if stage_name == "reconstruction":
        if checkpoint is None:
            raise ValueError("Reconstruction context requires an access checkpoint.")
        message_parts.append("\n\nAccess checkpoint:\n" + checkpoint.model_dump_json(indent=2))
    if stage_name == "collection":
        if strategy is None:
            raise ValueError("Collection context requires a selected strategy.")
        message_parts.append(f"\n\nSelected collection strategy:\n{strategy}")
    if stage_name in {"discovery", "collection"} and preceding_state is not None:
        message_parts.append(
            "\n\nFresh browser observation immediately before the latest model action:\n"
            f"URL: {preceding_state.current_url}\n{preceding_state.observation}"
        )
    return [
        {"role": "system", "content": STAGE_SYSTEM_PROMPTS[stage_name]},
        {"role": "user", "content": "".join(message_parts)},
    ]


def format_browser_action(
    tool_name: str,
    arguments: Mapping[str, Any],
    result: PageState,
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
