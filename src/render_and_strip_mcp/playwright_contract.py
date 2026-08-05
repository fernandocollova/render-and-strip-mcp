"""Pinned official Playwright MCP compatibility contract."""

from __future__ import annotations

OFFICIAL_PLAYWRIGHT_MCP_VERSION = "0.0.78"
OFFICIAL_PLAYWRIGHT_MCP_HTTP_PATH = "/mcp"
OFFICIAL_PLAYWRIGHT_MCP_IMAGE = (
    "mcr.microsoft.com/playwright/mcp:v0.0.78@"
    "sha256:3d871c22ea2d4cca0966e2cfb1860e1cb03eb7353725a3d6cffd133296fb04eb"
)
REQUIRED_CAPABILITIES = {
    "browser_navigate": "url",
    "browser_tabs": "action",
    "browser_evaluate": "function",
    "browser_close": None,
}
OFFICIAL_REQUIRED_TOOL_SCHEMAS = {
    "browser_navigate": {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
    "browser_tabs": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "new", "close", "select"]},
            "index": {"type": "number"},
            "url": {"type": "string"},
        },
        "required": ["action"],
    },
    "browser_evaluate": {
        "type": "object",
        "properties": {
            "function": {"type": "string"},
            "element": {"type": "string"},
            "target": {"type": "string"},
            "filename": {"type": "string"},
        },
        "required": ["function"],
    },
    "browser_close": {"type": "object", "properties": {}, "required": []},
}
