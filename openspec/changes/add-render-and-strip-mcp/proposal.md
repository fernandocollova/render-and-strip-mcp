## Why

Webpages that are rendered and explored interactively contain useful textual information mixed with media, styling, scripts, and interface chrome. MCP clients need a single tool that can direct a browser to complete a task and then receive the final page as clean semantic HTML.

## What Changes

- Add a Streamable HTTP FastMCP server exposing a page-rendering tool that accepts an HTTPS initial URL by default, with configured plain-HTTP support for local testing, and a natural-language browser task.
- Drive a tested official Playwright MCP HTTP interface through a FastMCP client and an OpenAI-compatible, LiteLLM-backed tool-calling agent; translate its eligible browser-action tools for the model and use bounded deterministic LLM invocation defaults with compact current-page context.
- Enforce a post-action top-level location invariant, apply the configured HTTPS/plain-HTTP policy, internally restore the original tab after popups, ignore downloads, and fail requests that exceed configured model, browser-action, or time limits.
- Clean the final top-level rendered DOM into visible semantic HTML and return HTML only on success.
- Forward provider-supplied reasoning deltas as optional MCP progress without making reasoning availability a requirement for agent execution.
- Add Pydantic/TOML settings and Docker Compose infrastructure for the official Playwright MCP image with bundled Chromium, llama.cpp, and a deterministic Python HTTP fixture site while keeping application endpoints configurable.

## Capabilities

### New Capabilities
- `browser-guided-page-rendering`: Run a bounded LLM-directed Playwright MCP session from an initial URL and browser task.
- `semantic-html-cleaning`: Transform the final top-level rendered document into clean visible semantic HTML.
- `optional-agent-progress`: Report available model reasoning as optional MCP progress without coupling it to task execution.
- `configurable-mcp-runtime`: Configure and run the Streamable HTTP MCP server and its external dependencies independently of local test infrastructure.

### Modified Capabilities

None.

## Impact

- Adds a Python/UV application package, FastMCP server/client usage, LiteLLM, DOM-cleaning dependencies, configuration models, tests, and Docker Compose files.
- Introduces a Streamable HTTP MCP API that returns clean HTML or an MCP tool error.
- Requires an OpenAI-compatible model endpoint with tool calling; reasoning-stream support remains optional.
- Requires reachable HTTP endpoints for the model server and a compatible official Playwright MCP server at runtime; the remote MCP must use isolated, non-shared browser contexts and Compose pins a tested upstream release.
