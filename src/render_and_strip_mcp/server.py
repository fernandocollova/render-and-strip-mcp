"""FastMCP application and its public render-and-strip tool."""

from __future__ import annotations

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from .browser_agent import BrowserAgent
from .config import Settings
from .errors import BrowserAgentError
from .reasoning_progress import ReasoningProgressReporter


def create_server(settings: Settings) -> FastMCP:
    """Create the configured MCP server with one HTML-only public tool."""

    server = FastMCP("Render and Strip MCP")

    @server.tool()
    async def render_and_strip_page(url: str, task: str, context: Context) -> str:
        """Render a page, complete a browser task, and return clean semantic HTML only."""

        reasoning_progress = ReasoningProgressReporter(
            settings.progress.reasoning_progress_max_items,
            settings.progress.reasoning_progress_min_interval_seconds,
            context.report_progress,
        )
        agent = BrowserAgent(settings, reasoning_progress)
        try:
            return await agent.run(url, task)
        except BrowserAgentError as error:
            raise ToolError(str(error)) from error

    return server
