"""Deterministic, compact model context for browser-agent turns."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from .stage_models import (
    ACCESS_COMPLETION_TOOL,
    COLLECTION_COMPLETION_TOOL,
    DISCOVERY_COMPLETION_TOOL,
    RECONSTRUCTION_COMPLETION_TOOL,
    AccessCheckpoint,
    CompletionTool,
    DiscoveryStrategy,
    StageName,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArgumentKind:
    """Formatting strategy for one browser-tool argument kind."""

    renderer: Callable[[object], str]

    def format(self, value: object) -> str:
        """Render one argument value according to this kind's policy."""

        return self.renderer(value)


def _format_structural_argument(value: object) -> str:
    """Preserve a structural argument value in deterministic JSON."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _format_payload_argument(value: object) -> str:
    """Describe payload size without preserving its value."""

    if isinstance(value, str):
        description = f"{len(value)} chars omitted"
    elif isinstance(value, (list, tuple, set, frozenset, dict)):
        description = f"{len(value)} items omitted"
    else:
        description = "value omitted"
    return f"<{description}>"


class BrowserToolArguments:
    """Format arguments according to the policy for each known browser tool.

    Action summaries are included in subsequent model turns. Formatting keeps that history compact
    and useful while preventing arbitrary payloads, such as typed text or evaluated code, from
    being copied back into model context.
    """

    _STRUCTURAL: ClassVar[ArgumentKind] = ArgumentKind(_format_structural_argument)
    _PAYLOAD: ClassVar[ArgumentKind] = ArgumentKind(_format_payload_argument)
    _KINDS: ClassVar[dict[str, dict[str, ArgumentKind]]] = {
        "browser_click": {
            "element": _STRUCTURAL,
            "target": _STRUCTURAL,
            "doubleClick": _STRUCTURAL,
            "button": _STRUCTURAL,
            "modifiers": _STRUCTURAL,
        },
        "browser_console_messages": {
            "level": _STRUCTURAL,
            "all": _STRUCTURAL,
            "filename": _PAYLOAD,
        },
        "browser_drag": {
            "startElement": _STRUCTURAL,
            "startTarget": _STRUCTURAL,
            "endElement": _STRUCTURAL,
            "endTarget": _STRUCTURAL,
        },
        "browser_evaluate": {
            "element": _STRUCTURAL,
            "target": _STRUCTURAL,
            "function": _PAYLOAD,
            "filename": _PAYLOAD,
        },
        "browser_fill_form": {"fields": _PAYLOAD},
        "browser_find": {"text": _PAYLOAD, "regex": _PAYLOAD},
        "browser_handle_dialog": {"accept": _STRUCTURAL, "promptText": _PAYLOAD},
        "browser_hover": {"element": _STRUCTURAL, "target": _STRUCTURAL},
        "browser_navigate": {"url": _STRUCTURAL},
        "browser_navigate_back": {},
        "browser_network_request": {
            "index": _STRUCTURAL,
            "part": _STRUCTURAL,
            "filename": _PAYLOAD,
        },
        "browser_network_requests": {
            "static": _STRUCTURAL,
            "filter": _PAYLOAD,
            "filename": _PAYLOAD,
        },
        "browser_press_key": {"key": _STRUCTURAL},
        "browser_resize": {"width": _STRUCTURAL, "height": _STRUCTURAL},
        "browser_select_option": {
            "element": _STRUCTURAL,
            "target": _STRUCTURAL,
            "values": _PAYLOAD,
        },
        "browser_snapshot": {
            "target": _STRUCTURAL,
            "depth": _STRUCTURAL,
            "boxes": _STRUCTURAL,
            "filename": _PAYLOAD,
        },
        "browser_take_screenshot": {
            "element": _STRUCTURAL,
            "target": _STRUCTURAL,
            "type": _STRUCTURAL,
            "fullPage": _STRUCTURAL,
            "scale": _STRUCTURAL,
            "filename": _PAYLOAD,
        },
        "browser_type": {
            "element": _STRUCTURAL,
            "target": _STRUCTURAL,
            "text": _PAYLOAD,
            "submit": _STRUCTURAL,
            "slowly": _STRUCTURAL,
        },
        "browser_wait_for": {
            "time": _STRUCTURAL,
            "text": _PAYLOAD,
            "textGone": _PAYLOAD,
        },
    }

    @classmethod
    def format(cls, tool_name: str, arguments: Mapping[str, Any]) -> str | None:
        """Format known tool arguments, or return None when the tool has no policy."""

        argument_kinds = cls._KINDS.get(tool_name)
        if argument_kinds is None:
            return None

        summary_parts = [
            f"{name}={argument_kinds[name].format(arguments[name])}"
            for name in sorted(argument_kinds)
            if name in arguments
        ]
        unknown_arguments = sorted(set(arguments) - set(argument_kinds))
        summary_parts.extend(f"{name}=<omitted>" for name in unknown_arguments)
        return ", ".join(summary_parts)


@dataclass(frozen=True)
class PageState:
    """Fresh orchestration-owned state for the tracked original browser tab."""

    observation: str
    current_url: str
    succeeded: bool = True


BrowserActionResult = PageState


class Stage:
    """Build shared model context for one stage-specific completion contract."""

    stage_name: ClassVar[StageName]
    system_prompt: ClassVar[str]
    completion_tool: ClassVar[CompletionTool]
    include_preceding_state: ClassVar[bool] = False

    def build_messages(
        self,
        task: str,
        action_log: list[str],
        current_state: PageState,
        preceding_state: PageState | None = None,
    ) -> list[dict[str, str]]:
        """Build the exact fresh system and user messages for one inner model turn."""

        serialized_actions = (
            "\n".join(action_log) if action_log else "(no model-directed actions yet)"
        )
        message_parts = [
            f"Task:\n{task}",
            f"Actions:\n{serialized_actions}",
            f"Current top-level URL:\n{current_state.current_url}",
            f"Newest fresh browser observation:\n{current_state.observation}",
            *self.additional_context(),
        ]
        if self.include_preceding_state and preceding_state is not None:
            message_parts.append(
                "Fresh browser observation immediately before the latest model action:\n"
                f"URL: {preceding_state.current_url}\n{preceding_state.observation}"
            )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n\n".join(message_parts)},
        ]

    def additional_context(self) -> list[str]:
        """Return context required only by this concrete stage."""

        return []


class AccessStage(Stage):
    """Reach and describe the caller's requested semantic page state."""

    stage_name = "access"
    system_prompt = (
        "Reach the caller's requested page, report, view, or filter state. Treat the task as "
        "page/view retrieval, not a request to extract individual facts. Rediscover controls "
        "from the current observation. If the state is visibly pending, use an eligible semantic "
        "wait or investigation action. Complete only by calling complete_access with a semantic "
        "target state, any reconstruction instructions, and verification conditions."
    )
    completion_tool = ACCESS_COMPLETION_TOOL


class DiscoveryStage(Stage):
    """Determine whether target content supports retained-document collection."""

    stage_name = "discovery"
    system_prompt = (
        "Inspect the current target page/view for relevant reveal mechanisms. Safely probe when "
        "needed to establish behavior, without a fixed probe count. Choose retained-final-document "
        "only when revealed target content can coexist in the final visible document; choose "
        "unknown for unsafe, unproven, replacing, virtualized, mixed, or ambiguous behavior. "
        "Use semantic waits while effects are pending. Complete only by calling complete_discovery "
        "with strategy and evidence."
    )
    completion_tool = DISCOVERY_COMPLETION_TOOL
    include_preceding_state = True


@dataclass(frozen=True)
class ReconstructionStage(Stage):
    """Restore and verify one required access checkpoint after reset."""

    checkpoint: AccessCheckpoint

    stage_name = "reconstruction"
    system_prompt = (
        "Reconstruct the supplied semantic checkpoint from the reset page. Rediscover current "
        "controls; never replay stale references. Follow its semantic instructions, use eligible "
        "semantic waits for pending effects, and assess every verification condition. Complete "
        "only by calling complete_reconstruction with verified and evidence."
    )
    completion_tool = RECONSTRUCTION_COMPLETION_TOOL

    def additional_context(self) -> list[str]:
        """Expose the semantic checkpoint that this stage must restore."""

        return ["Access checkpoint:\n" + self.checkpoint.model_dump_json(indent=2)]


@dataclass(frozen=True)
class CollectionStage(Stage):
    """Exhaust content according to one selected discovery strategy."""

    strategy: DiscoveryStrategy

    stage_name = "collection"
    system_prompt = (
        "Exhaust non-destructive, retained-document reveal mechanisms for the requested page/view, "
        "including scrolling, lazy loading, additive controls, and expansions that can remain open "
        "simultaneously. Use semantic waits for visibly pending effects. Preserve earlier target "
        "content and make a final verification sweep for no new content, unused relevant controls, "
        "pending state, or lost content. Complete only by calling complete_collection with "
        "complete and evidence."
    )
    completion_tool = COLLECTION_COMPLETION_TOOL
    include_preceding_state = True

    def additional_context(self) -> list[str]:
        """Expose the strategy selected by discovery."""

        return [f"Selected collection strategy:\n{self.strategy}"]


def format_browser_action(
    tool_name: str,
    arguments: Mapping[str, Any],
    result: PageState,
) -> str:
    """Create a deterministic action summary without copying payload argument values.

    The action log is sent on subsequent model turns, so formatting keeps that context compact and
    prevents arbitrary payloads from being copied back to the model.
    """

    argument_summary = BrowserToolArguments.format(tool_name, arguments)
    if argument_summary is None:
        logger.warning("No dedicated action formatter is defined for Playwright tool %s", tool_name)
        argument_summary = ", ".join(f"{name}=<omitted>" for name in sorted(arguments))
    status = "success" if result.succeeded else "failure"
    return f"{tool_name}({argument_summary}) -> {status}; current URL: {result.current_url}"
