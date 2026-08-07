"""Pinned official browser_evaluate retrieval of a visible top-level document."""

from __future__ import annotations

from bs4 import BeautifulSoup
from fastmcp import Client

from .errors import BrowserAgentError
from .mcp_results import extract_json_string_result

VISIBLE_DOCUMENT_EXPRESSION = """() => {
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
  const documentClone = cloneVisibleNode(document.documentElement);
  return documentClone ? documentClone.outerHTML : '<html><head></head><body></body></html>';
}"""


async def fetch_visible_top_level_document(client: Client, timeout_seconds: float) -> str:
    """Retrieve the visibility-filtered DOM through the tested browser_evaluate contract."""

    result = await client.call_tool(
        "browser_evaluate",
        {"function": VISIBLE_DOCUMENT_EXPRESSION},
        timeout=timeout_seconds,
    )
    document_html = extract_json_string_result(result)
    if not is_complete_html_document(document_html):
        raise BrowserAgentError("Playwright browser_evaluate returned malformed document HTML.")
    return document_html


def is_complete_html_document(document_html: str) -> bool:
    """Check the expected document-shaped result before semantic cleanup."""

    normalized_html = document_html.strip().lower()
    if not normalized_html.startswith("<html") or "</html>" not in normalized_html:
        return False
    return BeautifulSoup(document_html, "html.parser").html is not None
