"""Targeted Playwright capture of one visibility-filtered selected content region."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag
from fastmcp import Client

from .errors import BrowserAgentError
from .mcp_results import extract_json_string_result
from .stage_models import SelectedRegion

VISIBLE_SELECTED_REGION_EXPRESSION = """(selectedElement) => {
  if (!(selectedElement instanceof Element)) return null;
  const isInsideClosedDetails = (element) => {
    let node = element;
    while (node.parentElement) {
      const parent = node.parentElement;
      if (parent.tagName === 'DETAILS' && !parent.open && node.tagName !== 'SUMMARY') return true;
      node = parent;
    }
    return false;
  };
  const isHidden = (element) => {
    if (element.tagName === 'TEMPLATE' || element.hasAttribute('inert') || element.inert)
      return true;
    if (element.hidden || element.getAttribute('aria-hidden')?.trim().toLowerCase() === 'true')
      return true;
    if (isInsideClosedDetails(element)) return true;
    const style = getComputedStyle(element);
    return style.display === 'none' || style.visibility === 'hidden' ||
      style.visibility === 'collapse' || style.contentVisibility === 'hidden' ||
      Number.parseFloat(style.opacity) === 0;
  };
  const cloneVisibleNode = (source) => {
    if (source.nodeType === Node.ELEMENT_NODE && isHidden(source)) return null;
    const clone = source.cloneNode(false);
    for (const child of source.childNodes) {
      const visibleChild = cloneVisibleNode(child);
      if (visibleChild) clone.appendChild(visibleChild);
    }
    return clone;
  };
  const regionClone = cloneVisibleNode(selectedElement);
  return regionClone ? regionClone.outerHTML : null;
}"""


@dataclass(frozen=True)
class CapturedContent:
    """One selected visibility-filtered region and its top-level source URL."""

    html: str
    source_url: str


async def fetch_visible_selected_region(
    client: Client,
    selected_region: SelectedRegion,
    timeout_seconds: float,
) -> str:
    """Capture a current snapshot target through Playwright MCP's pinned targeted contract."""

    result = await client.call_tool(
        "browser_evaluate",
        {
            "function": VISIBLE_SELECTED_REGION_EXPRESSION,
            "element": selected_region.element,
            "target": selected_region.target,
        },
        timeout=timeout_seconds,
    )
    region_html = extract_json_string_result(result)
    if not is_single_content_element(region_html):
        raise BrowserAgentError(
            "Playwright browser_evaluate returned malformed selected-region HTML."
        )
    return region_html


def is_single_content_element(region_html: str) -> bool:
    """Accept one complete element subtree, never a document or full-body fallback."""

    parsed_region = BeautifulSoup(region_html, "html.parser")
    top_level_nodes = [
        node
        for node in parsed_region.contents
        if not isinstance(node, NavigableString) or node.strip()
    ]
    if len(top_level_nodes) != 1 or not isinstance(top_level_nodes[0], Tag):
        return False
    root = top_level_nodes[0]
    if root.name in {"html", "body"}:
        return False
    return f"</{root.name}>" in region_html.lower()
