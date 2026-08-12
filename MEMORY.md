# Project notes

- `/home/fcollova/projects/nyc-stats` is a structure-only reference. Never copy, import, reuse, or otherwise use code from it in this project.
- Compose builds the llama.cpp model image from `docker/llama-cpp/Dockerfile`; its sole `MODEL_URL` and `MODEL_SHA256` defaults are checksum-verified, and custom models must supply both values.
- The devcontainer attaches to the Compose `app` service as UID/GID 1000 user `devcontainer`; it intentionally uses the workspace-local `.venv`.
- All test commands for this project MUST run from inside the devcontainer; do not run test suites from the host shell. The devcontainer starts `playwright-mcp`, `llama-cpp`, `test-site`, and `app`; Compose integration tests run by default using service-DNS defaults. Use `--skip-compose-integration` only when those services are intentionally unavailable.
- FastMCP 3.4.5 `Client.call_tool` returns `fastmcp.client.client.CallToolResult`, whose error field is `is_error`; use that pinned API directly rather than a camel/snake compatibility fallback.
- The Playwright MCP image is developer-controlled and pinned. Discover its tools only to build the OpenAI catalog; do not preflight fixed browser-tool names or schemas. Retain validation for the OpenAI tool-schema boundary and MCP response content.
