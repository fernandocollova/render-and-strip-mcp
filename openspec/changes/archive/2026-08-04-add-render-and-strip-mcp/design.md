## Context

The repository has no application code. The new application must expose one Streamable HTTP MCP tool that begins at a caller-provided HTTPS URL by default, lets an LLM direct a remote Playwright MCP server to complete a caller-provided task, and returns only cleaned HTML from the final rendered page. A setting permits plain HTTP for the local test fixture. Local Docker Compose services exist solely to exercise the remote browser/MCP/model dependencies; application code must receive their endpoints through settings.

The settings layout will follow the referenced application: a top-level Pydantic `BaseSettings` model, nested validated settings models, TOML loading, environment overrides through `__`, and rejection of unknown configuration fields.

## Goals / Non-Goals

**Goals:**

- Provide a bounded, asynchronous browser-agent tool over Streamable HTTP.
- Accept HTTPS initial URLs by default, with an explicit setting for plain HTTP.
- Support any OpenAI-compatible endpoint through LiteLLM, requiring tool calling but not reasoning output.
- Use the Playwright MCP's HTTP transport for all browser interaction.
- Enforce that actions after initial navigation leave the browser on the initial document's final origin only.
- Return a complete, clean HTML document containing visible semantic top-level-page content only.
- Make deployment endpoints, credentials, limits, and optional output/progress caps configurable.
- Supply reproducible local infrastructure and automated tests without coupling runtime code to Compose hostnames.

**Non-Goals:**

- User authentication, URL allowlists, SSRF protection, credential management, or sandbox hardening beyond the selected post-action top-level location invariant.
- Support for iframes, shadow-root contents, file upload/download workflows, screenshots, or returning browser traces.
- Unconfigured plain-HTTP URLs and all URL schemes other than HTTP(S).
- Compatibility with arbitrary Playwright-like MCP implementations or automatic inference of their proprietary browser tool semantics.
- Guaranteeing a particular model's private reasoning or making reasoning progress part of the agent protocol.
- Article-only readability extraction, markdown output, HTML truncation, persistent browser sessions, or multi-page aggregation.

## Decisions

### One FastMCP tool with a short success contract

Expose `render_and_strip_page(url, task)` through a FastMCP server configured for Streamable HTTP. The tool returns a string containing complete clean HTML on success and raises an MCP tool error on failure. It does not return action logs, URL metadata, partial HTML, or an envelope around the HTML.

This keeps the caller contract aligned with the requested result and avoids clients needing to parse a custom status schema. An alternative structured result was rejected because it would violate the HTML-only success requirement.

### Async tool-calling agent through the FastMCP client and official Playwright MCP

For each invocation, use a new `fastmcp.Client` session to connect to the configured official Playwright MCP HTTP endpoint. The client manages MCP HTTP transport, connection lifecycle, tool discovery, and remote tool calls. Discover the complete remote tool list; reserve `browser_tabs` and `browser_close` for Python orchestration; and exclude `browser_run_code_unsafe`, `browser_file_upload`, `browser_drop`, and `browser_install` from model access. Translate each remaining eligible tool's name, description, and input JSON Schema into LiteLLM's OpenAI function-tool shape. Eligible remote names must already be valid OpenAI function names; an incompatible configured server fails clearly rather than receiving a compatibility mapping.

The agent loop will:

1. Navigate to the initial URL and record the final top-level document origin after its initial redirect chain.
2. Stream a LiteLLM completion containing the caller task, agent constraints, and remote tool schemas.
3. Accumulate streamed content, tool-call fragments, and optional reasoning fragments.
4. Execute requested Playwright MCP tools through `Client.call_tool`, update deterministic current-page state from their results, and start the next model turn with that compact state until the model completes without requesting another tool.
5. Read the final top-level document and clean it.

Eligible remote browser-action tools retain their descriptions and input semantics rather than being wrapped in local click/type/scroll abstractions. Translation is limited to the OpenAI-compatible function envelope after name, description, and schema validation. The runtime supports the documented interface of the official Playwright MCP release tested by this project; it does not promise compatibility with arbitrary Playwright-like MCP servers. At connection time it checks the pinned required-tool input schemas, while eligible tools must have valid OpenAI names, non-empty descriptions, and supported schemas. Python directly uses that interface for initial navigation, tab restoration, current-location evaluation, final-document evaluation, and cleanup. A remote server missing or deviating from those required capabilities fails clearly. A direct Playwright dependency was rejected because it would duplicate the remote MCP integration.

The model's normal completion and tool-call fields drive the loop. `reasoning_content` is never used to determine whether a turn, tool call, or task has completed.

### Deterministic LiteLLM invocation defaults

The LLM settings provide the LiteLLM model identifier, OpenAI-compatible API base URL, API key, and `max_output_tokens`, defaulting to 1024. Every inner model turn sets `stream=True`, uses the eligible Playwright tool schemas, sets `tool_choice="auto"`, requests `temperature=0`, sets `parallel_tool_calls=False`, and sets `num_retries=0`. Provider-specific or optional parameters, including `reasoning_effort`, `seed`, and `response_format`, are omitted.

`max_output_tokens` is a per-turn completion limit, not a limit for the complete browser task. It cannot be inferred portably from an OpenAI-compatible endpoint: model metadata and configured context size are not part of the standard API. Requesting the entire model context window as output would risk exceeding the context budget once the system prompt, tool schemas, and prior tool results are included. The fixed default bounds generation while keeping room for agent context.

MCP `tools/call` requests do not carry a standard caller deadline, so the service cannot derive a browser-agent budget from the outer client. It retains its configured per-model-request and total-invocation timeouts and responds to request cancellation when the underlying transport reports it.

The supported model endpoint contract is narrower than generic text-completion compatibility: it must accept OpenAI-compatible chat messages, streamed function-tool calls, automatic tool choice, the configured output-token limit, zero temperature, and disabled parallel tool calls. It must stream complete tool-call identifiers, names, and JSON arguments. Unsupported parameters, malformed or incomplete streams, unknown tools, invalid JSON arguments, multiple tool calls in one turn, and terminal reasons other than a normal completed response are tool errors; the application does not silently modify or retry those requests.

### Compact current-page model context

Every inner LLM turn starts a fresh model conversation rather than replaying raw assistant tool-call and tool-result history. The request uses exactly one system message containing the browser-agent instructions and one user message containing the original caller task, deterministic action log, current top-level URL, and newest browser observation. Eligible Playwright schemas are supplied through the request's `tools` parameter. The newest observation is ordinary user-message current-state context; fresh turns never contain an orphaned `role="tool"` message.

Python builds the action log from executed remote tool names, selected structural arguments, result success/failure status, and the resulting current URL. Each known eligible tool has a small tool-specific formatter. Payload arguments such as typed text, form values, JavaScript source, file paths, and dropped data are omitted as complete values rather than truncated; the summary records only their field names and character/item counts. Structural arguments such as element descriptions, targets, key names, booleans, and navigation destinations may be retained in full.

When a future compatible Playwright MCP version exposes an eligible tool without a formatter, a generic formatter records the tool name, argument names without values, success/failure status, and resulting current URL, and emits a warning log naming the unsupported formatter. This fallback lets the tool remain usable without copying arbitrary unknown payloads into model context. The log never derives content from model responses or optional reasoning progress. Earlier raw browser observations and assistant/tool message pairs are omitted.

If the system prompt, task, tool schemas, compact action log, newest browser observation, and requested 1024 output tokens still exceed the endpoint's context capacity, the tool fails with an MCP context-exhausted error. It does not truncate the newest observation or make a context-recovery retry.

Dependency error handling remains intentionally small. Catch `litellm.ContextWindowExceededError` for the explicit context-exhausted result, catch the shared `openai.OpenAIError` base for other LiteLLM/provider failures, and catch `fastmcp.exceptions.ToolError` for remote Playwright MCP failures. Re-raise an outward FastMCP `ToolError` with the dependency exception text. Unexpected programming errors are left to FastMCP's normal exception-to-MCP-error behavior rather than receiving an exhaustive mapping.

### Isolated browser context per invocation

The configured official Playwright MCP server SHALL run with `--isolated` and without `--shared-browser-context`. Its isolated mode gives each MCP client session an in-memory browser context whose storage is discarded when the browser session closes. The Python tool opens one MCP client session per invocation and calls the official `browser_close` capability in a `finally` path after final DOM collection or an error.

This prevents browser pages, cookies, local storage, and navigation state from leaking between tool invocations. Isolated contexts can run concurrently in the same browser process. The server exposes a configurable maximum concurrent invocation setting whose default is `0`, meaning no application-imposed concurrency cap; a positive value limits simultaneously active browser-agent sessions.

### Post-action top-level location invariant

The caller-provided initial URL must use HTTPS unless `allow_plain_http` is enabled; only HTTP(S) URLs are accepted in either mode. The initial URL's final redirect destination establishes the tracked page's allowed `(scheme, host, effective port)` origin. Evaluate the tracked page's top-level location after initial navigation, after settling each browser-affecting remote call, and immediately before extraction. Fail if that observed location uses disallowed plain HTTP or differs from the allowed origin.

This is deliberately a post-action and pre-extraction location invariant, not a claim that the page never made cross-origin requests or temporarily visited another location. It permits normal HTTPS redirects while rejecting a final HTTPS-to-HTTP downgrade by default. Enabling plain HTTP allows the deterministic Compose fixture site. This satisfies the requested lightweight protocol/origin checking without adding network interception or browser security policy.

### Restore the original tab and ignore secondary browser outputs

Track the tab used for initial navigation as the only page eligible for final DOM extraction. Do not expose official Playwright MCP tab-management tools to the LLM; reserve them for Python orchestration. After each browser-affecting action, Python lists tabs and reselects the original tab if a popup or new tab became active. It does not inspect or return secondary tabs. If the original tab no longer exists, the invocation fails. Downloads are not inspected or returned. This keeps the one-page clean-HTML contract deterministic without adding download or multi-tab workflow support.

### Bounded execution, optional output caps

Use validated agent settings with defaults of 12 model turns, 30 browser actions, 600 seconds total invocation time, 20 seconds per navigation, 15 seconds per browser action, 90 seconds per model request, a 2-second settle delay, and a 10-second cleanup timeout. The total timer starts when the outer tool begins, includes concurrency waiting, browser/model work, settling, extraction, and cleaning, and ends before cleanup. Cleanup runs once in a cancellation-shielded `finally` block and may extend execution by at most its configured cleanup timeout. Exceeding any execution bound raises an MCP error and does not return partial HTML.

Settings also provide an optional clean-HTML byte limit, a total reasoning-progress item limit, and a minimum progress-notification interval. A value of `0` disables the corresponding application limit. A nonzero HTML limit raises an error before returning output; it never truncates a document. Each non-empty normalized LiteLLM `reasoning_content` delta counts as one reasoning item across the entire outer MCP invocation. Once the configured item limit is reached, later reasoning deltas are still consumed from the model stream but are not forwarded as progress.

This balances deterministic control of browser work with the requested unlimited-by-default result/progress behavior. Unbounded application output remains subject to transport, client, memory, and model-context limits.

### Optional reasoning progress

When LiteLLM exposes streamed reasoning text, report it through the FastMCP request context as optional progress messages. If `reasoning_progress_min_interval_seconds` is `0`, emit each accepted reasoning item immediately. When it is positive, buffer accepted item text in arrival order and coalesce it into the next notification after the interval. Flush pending text at the end of an inner model turn or the outer invocation even when the interval has not elapsed. `reasoning_progress_max_items` counts accepted deltas across all inner turns; `0` means unlimited. Report cumulative accepted-item count as MCP `progress`, use the configured nonzero maximum as `total`, and place the emitted reasoning text in `message`.

Reasoning text and delta boundaries are provider-dependent, so the item count is intentionally approximate: equivalent reasoning may arrive as one large delta or many small deltas. LiteLLM cannot synthesize reasoning for an endpoint that omits it. Stage/action progress is not substituted when reasoning is absent. Missing caller progress support or a progress-delivery failure disables further progress notifications and logs a warning without changing model streaming, browser execution, or the final result.

### Render-aware semantic HTML cleaning

Retrieve only the final top-level document. Before serialization, evaluate a cloned top-level DOM in the rendered page and remove elements hidden by a `hidden` attribute, `aria-hidden="true"`, a hidden ancestor, closed `<details>` content other than its `<summary>`, or computed `display:none`, `visibility:hidden|collapse`, `content-visibility:hidden`, or `opacity:0`. Remove `<template>` and inert content. Keep offscreen content because the requested scope is the whole page; do not attempt occlusion or clipping analysis. Iframe documents and shadow-root internals remain excluded. Pass the resulting HTML to Beautiful Soup using Python's built-in `html.parser` for deterministic structural cleanup.

Use the pinned official `browser_evaluate` contract for location, visibility-aware DOM cloning, and final HTML retrieval. Accept its expected textual result shape; a remote `ToolError`, error-marked result, missing textual result, or malformed HTML result fails the outer tool with no partial output. No broad provider-specific MCP result adapter is introduced.

The cleaner emits `<!doctype html>` and an `html/head/body` skeleton with UTF-8 metadata and a textual title when present. It preserves textual semantic elements for articles/sections, headings, paragraphs, line breaks, quotations, preformatted/code text, lists, details/summary, tables, links, emphasis, abbreviations, citations, addresses, and time-related inline content. Generic layout elements are unwrapped while retaining their text.

It removes executable/presentation/media/form content, comments, inline event handlers, styles/classes/IDs/data attributes, `<base>`, refresh metadata, and URL-bearing attributes other than the sanitized link destination. Navigation, aside content, elements with navigation/banner/contentinfo/complementary roles, and page-level headers/footers outside `main` or `article` are removed; headers/footers inside `main` or `article` are unwrapped so their text remains. A non-empty image `alt` value becomes plain `[Image: ...]` text before the image is removed.

Relative links are resolved against the final page URL. Fragment, HTTPS, `mailto:`, and `tel:` destinations are retained; HTTP is retained only when plain HTTP is enabled. Other schemes, credentials in URLs, and invalid destinations lose their `href` while retaining link text. The cleaner retains only `href`/`title` on links, `colspan`/`rowspan`/`scope` on table cells, `datetime` on time elements, and semantic `title` values on abbreviations. If a link has no readable text but has an `aria-label`, that label becomes its text and the attribute is removed.

Beautiful Soup is selected for a small, inspectable prototype dependency. A readability/article extractor was rejected because the required output is visible semantic content across a page, not just an inferred primary article.

### Settings and local infrastructure are separate

Create a package-level settings module with server, Playwright MCP, LLM, agent, and cleaner/output nested settings. The CLI accepts an optional TOML path, loads defaults when it is absent, configures logging, and starts the Streamable HTTP FastMCP server. Sensitive API keys are supplied through settings/environment, not hardcoded in application logic.

Docker Compose will define a pinned official Playwright MCP image, which already bundles headless Chromium, launched with `--isolated` and without `--shared-browser-context`; a llama.cpp service; and a deterministic static test-site service launched with Python's built-in HTTP server. No separate browser service is needed. A dedicated model-image Dockerfile owns one default model URL and SHA-256, verifies every downloaded model, and accepts custom model URL and SHA-256 build-argument pairs. Compose supplies test-infrastructure endpoint and model values without making them application defaults. The integration configuration explicitly enables plain HTTP to reach the fixture. A Compose-backed devcontainer starts the dependencies and application using internal endpoints while keeping its UV environment outside the mounted workspace. The README will state that this is the tested configuration and that external deployments are responsible for supplying required settings and an isolated compatible Playwright MCP endpoint.

## Risks / Trade-offs

- [A custom OpenAI-compatible model server emits malformed or unsupported streamed tool/reasoning fields] → Require tool calling, validate accumulated calls, and treat missing reasoning as normal; test the configured llama.cpp model explicitly.
- [A configured Playwright MCP server is not compatible with the tested official interface] → Declare the supported upstream interface/version, verify its required tools at connection time, and fail with a descriptive prerequisite error before the agent loop.
- [Unbounded clean HTML or reasoning progress exceeds an MCP client, proxy, or model context limit] → Keep configurable byte/rate limits with unlimited defaults; surface transport failures as MCP errors.
- [The newest browser observation exceeds the model context capacity on its own] → Return a clear MCP context-exhausted error without truncating the observed browser state.
- [A model loops, calls invalid tools, or cannot complete a task] → Apply model-turn, tool-action, request, and total wall-clock bounds with no partial success output.
- [Unlimited concurrent invocations consume shared browser-process resources] → Keep the requested unlimited default while offering a positive configurable cap for constrained deployments.
- [Arbitrary browser actions can leave the intended site] → Verify the final top-level origin after each action and fail on a change; this does not provide general browser or network isolation, which is out of scope.
- [Computed visibility and semantic-page-chrome detection are imperfect across dynamic sites] → Use deterministic removal rules, preserve core semantic text, and cover representative fixtures; no article-extraction quality guarantee is made.

## Migration Plan

This is a new standalone application with no existing runtime or persisted data to migrate. Deploy by supplying a TOML configuration or equivalent environment variables that point to reachable Playwright MCP and model HTTP endpoints, then run the Streamable HTTP server. Roll back by stopping the new server and removing its local Compose services; no data migration is required.

## Open Questions

None.
