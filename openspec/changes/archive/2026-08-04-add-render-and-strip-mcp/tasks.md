## 1. Project and runtime setup

- [x] 1.1 Create the UV Python package layout, package entry point, and dependency declarations for FastMCP server/client support, LiteLLM, Pydantic settings, Beautiful Soup, and pytest tooling.
- [x] 1.2 Implement nested validated Pydantic settings for the Streamable HTTP server, Playwright MCP endpoint, LiteLLM endpoint/model/credentials/maximum output tokens, agent and cleanup limits, plain-HTTP permission, maximum concurrent invocations, optional HTML limit, reasoning-progress maximum items, and reasoning-progress minimum interval; keep fields without defaults required so Pydantic fails naturally when absent.
- [x] 1.3 Implement TOML settings loading, nested environment overrides, CLI configuration-path handling, logging setup, and Streamable HTTP server startup.
- [x] 1.4 Add configuration and CLI tests covering defaults, TOML validation, environment overrides, unknown fields, plain-HTTP/concurrency settings, and server startup wiring.

## 2. Playwright MCP browser agent

- [x] 2.1 Implement one asynchronous FastMCP HTTP client session per invocation for the documented, tested official Playwright MCP interface; validate its pinned navigation, tab-management, location-evaluation, final-document, and close-browser schemas.
- [x] 2.2 Reserve `browser_tabs` and `browser_close`; exclude `browser_run_code_unsafe`, `browser_file_upload`, `browser_drop`, and `browser_install`; then translate eligible tools into LiteLLM/OpenAI schemas, rejecting invalid or duplicate remote names, missing descriptions, and unsupported schemas with explicit errors.
- [x] 2.3 Implement the minimum OpenAI-compatible endpoint contract and LiteLLM streaming integration, including fragmented tool-call accumulation; set `stream=True`, `tool_choice="auto"`, `temperature=0`, `parallel_tool_calls=False`, and `num_retries=0`, and reject unsupported parameters, malformed streams, invalid/unknown/multiple tool calls, and non-normal terminal reasons.
- [x] 2.4 Implement the agent loop with exact fresh system/user messages, tool-specific action formatters that omit payload values without truncating them, a warning generic formatter for future eligible tools, current URL, newest observation, and Playwright schemas in `tools`; never emit orphaned tool-result messages.
- [x] 2.5 Reserve remote tab-management tools for Python, track and reselect the original tab after browser actions, fail if it closes, and ignore secondary tabs and downloads.
- [x] 2.6 Implement HTTP(S) initial-URL validation, initial navigation, initial-final-origin recording, post-action top-level origin/protocol checks, and clear failure handling for cross-origin or disallowed-HTTP navigation through the official MCP capabilities.
- [x] 2.7 Implement the configurable application-level concurrency gate, where zero starts unlimited browser-agent sessions and a positive value bounds simultaneous sessions.
- [x] 2.8 Enforce model-turn, browser-action, total-request, navigation, browser-action, model-request, and page-settle limits; include concurrency waiting, extraction, and cleaning in total time.
- [x] 2.9 Implement cancellation-shielded browser cleanup with the configurable cleanup timeout, preserving a primary processing error and reporting cleanup failure only when no earlier error exists.
- [x] 2.10 Implement minimal dependency error translation for LiteLLM context errors, the `openai.OpenAIError` base, and FastMCP `ToolError`, while leaving unexpected exceptions to FastMCP's normal conversion.
- [x] 2.11 Add deterministic fake-MCP/fake-LiteLLM tests for schema translation, fixed invocation parameters, exact fresh messages, context exhaustion, malformed/non-normal model streams, provider/MCP failures, tab restoration, URL invariants, concurrency/cancellation, cleanup, required capabilities, and every execution limit boundary.

## 3. Semantic rendered-HTML extraction

- [x] 3.1 Implement the pinned `browser_evaluate` calls for location and visibility-aware cloned top-level DOM retrieval; accept the expected textual result shape and fail simply on remote errors, missing text, or malformed HTML.
- [x] 3.2 Implement the specified visibility predicate without traversing iframe documents or shadow roots, retaining offscreen content and excluding hidden, inert, template, and closed-details content.
- [x] 3.3 Implement Beautiful Soup `html.parser` cleanup with the semantic element/attribute allowlist, deterministic page-chrome rules, image-alt conversion, and sanitized absolute link policy.
- [x] 3.4 Serialize the specified doctype and UTF-8 document skeleton and enforce the optional UTF-8 byte limit, where zero is unlimited and a nonzero overage fails without truncation.
- [x] 3.5 Add exact cleaner fixtures for every visibility, page-chrome, semantic element/attribute, image-alt, link-scheme, malformed-input, top-level scope, and output-size rule.

## 4. Optional reasoning progress

- [x] 4.1 Extract available LiteLLM streamed reasoning fragments independently of ordinary content and tool-call handling.
- [x] 4.2 Count non-empty normalized reasoning deltas across the outer invocation, enforce the optional maximum-item count, and emit immediate progress when the minimum interval is zero.
- [x] 4.3 Implement best-effort interval coalescing, turn/invocation-end buffer flushing, cumulative item-count progress fields, and non-fatal handling for missing or failed progress delivery.
- [x] 4.4 Add fake-clock progress tests for emitted/absent reasoning, unlimited defaults, cross-turn item limits, immediate emission, interval coalescing, final flushing, provider-dependent item boundaries, and notification failures.

## 5. Public tool, local infrastructure, and verification

- [x] 5.1 Register `render_and_strip_page(url, task)` with the FastMCP server so successful calls return only clean HTML and all failures are surfaced as MCP tool errors.
- [x] 5.2 Add Docker Compose services for the pinned official Playwright MCP image with bundled headless Chromium launched with `--isolated` and without `--shared-browser-context`, a configurable llama.cpp OpenAI-compatible model server, and a deterministic static HTTP test site served with Python's built-in HTTP server; do not add a separate browser service or put Compose values in application defaults.
- [x] 5.3 Add an example TOML configuration and README setup documentation describing model requirements, HTTP endpoints, optional reasoning progress, limits, plain-HTTP/concurrency settings, local test-stack startup, and the required isolated/non-shared Playwright MCP deployment flags; identify the Compose configuration as the tested setup.
- [x] 5.4 Run formatting, static/type checks if configured, unit tests, and an integration smoke test against the Compose dependency stack using explicit plain-HTTP enablement for the deterministic fixture; document any external-model prerequisite not available in automated tests.
- [x] 5.5 Select, record, and pin exact tested Python package versions, official Playwright MCP image tag or digest, llama.cpp image/version, MCP endpoint path/transport, and required Playwright tool names/schemas in lock files, Compose, contract tests, and README compatibility documentation.
- [x] 5.6 Build the default llama.cpp model in a dedicated checksum-verifying Dockerfile, require paired custom model URL/hash build arguments, reorganize unit and infrastructure tests, and add a Compose-backed devcontainer that starts the application and supporting services.
