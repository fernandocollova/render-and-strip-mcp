## Purpose

Provide browser-agent-guided rendering of a page and return only its cleaned final HTML.
## Requirements
### Requirement: Render-and-strip MCP tool input and result
The MCP server SHALL expose a Streamable HTTP tool named `render_and_strip_page` that accepts a non-empty HTTP(S) initial URL and non-empty natural-language browser task. It SHALL reject a plain-HTTP URL by default and accept it only when `allow_plain_http` is enabled. It SHALL always reject URL schemes other than HTTP(S). On success, the tool SHALL return only one cleaned HTML string produced after successful collection through a supported strategy. For retained-document collection, that string SHALL represent the one final page document. For paginated-document collection, it SHALL contain the captured page documents assembled in source order. On failure, the tool SHALL return an MCP tool error and SHALL NOT return partial HTML.

#### Scenario: Successful retained-document rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose retained-document pipeline completes within its limits
- **THEN** the tool returns only cleaned HTML from the greedily expanded final page state

#### Scenario: Successful browser-guided rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose selected supported collection pipeline completes within its limits
- **THEN** the tool returns only the cleaned HTML produced by that completed collection strategy

#### Scenario: Successful paginated rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose paginated-document pipeline reaches semantic or natural completion within its limits
- **THEN** the tool returns only one cleaned HTML document containing all captured page documents in source order

#### Scenario: Invalid tool input
- **WHEN** a caller supplies an empty URL or task, a non-HTTP(S) URL, or a plain-HTTP URL while `allow_plain_http` is disabled
- **THEN** the tool returns a validation error before opening a Playwright MCP session

#### Scenario: Plain HTTP is explicitly enabled
- **WHEN** a caller supplies a plain-HTTP initial URL and `allow_plain_http` is enabled
- **THEN** the tool permits initial navigation

### Requirement: Official Playwright MCP agent session
The tool SHALL use a new FastMCP client session to connect to the configured HTTP endpoint of the documented, tested official Playwright MCP interface for each invocation. The configured remote server SHALL be launched with `--isolated` and SHALL NOT enable `--shared-browser-context`. The server SHALL reserve `browser_tabs`, `browser_snapshot`, and `browser_close` for Python orchestration and SHALL exclude `browser_run_code_unsafe`, `browser_file_upload`, `browser_drop`, and `browser_install` from model access. It SHALL translate every remaining eligible tool's name, description, and input JSON Schema into a LiteLLM/OpenAI callable-tool schema. Every eligible remote name SHALL already be valid for an OpenAI function tool; an invalid or duplicate name SHALL fail with a clear tool error rather than receive a compatibility mapping. After a successful model-requested remote MCP call completes, the agent SHALL apply the optional configured settle grace, restore and validate the tracked original tab, capture a fresh orchestration-owned browser snapshot, update compact stage-local state, and continue until the model submits the current stage's valid local completion call. The settle grace SHALL default to `0` seconds and SHALL NOT be treated as proof of generic page readiness. The server SHALL close the remote browser session after DOM collection or failure.

#### Scenario: Model-directed browser action
- **WHEN** the model returns a valid eligible Playwright MCP tool call during a stage
- **THEN** the server invokes the corresponding remote MCP tool, applies any configured settle grace, restores and validates the tracked page, captures a fresh browser snapshot, and supplies the resulting state to the next model turn

#### Scenario: Page state remains semantically pending
- **WHEN** a fresh observation shows a loading indicator, a missing expected action effect, or another semantic sign that the current stage is not ready to complete
- **THEN** the model does not complete the stage, uses eligible browser tools to wait for or investigate the expected state, and receives another fresh observation after each action

#### Scenario: Discovered tools are exposed to the model
- **WHEN** the official Playwright MCP server publishes browser-action tools
- **THEN** the server supplies eligible tools' descriptions and input semantics through deterministic OpenAI-compatible schemas without local action-specific wrappers

#### Scenario: Reserved or hard-excluded tool is discovered
- **WHEN** the official Playwright MCP server publishes an orchestration-reserved or hard-excluded tool
- **THEN** the server does not include that tool in the model's callable-tool list

#### Scenario: Required official capability is absent
- **WHEN** the connected Playwright MCP server does not provide the documented navigation, tab management, browser snapshot, top-level location evaluation, final top-level document retrieval, or browser-close capability
- **THEN** the tool returns a descriptive MCP tool error without returning HTML

#### Scenario: Required official capability schema is incompatible
- **WHEN** a connected Playwright MCP server publishes one of the pinned required tools with incompatible input properties, required fields, types, or enum values
- **THEN** the tool returns a descriptive compatibility error without browser-agent execution

#### Scenario: Unsupported Playwright-like MCP implementation
- **WHEN** a configured remote MCP server does not satisfy the documented official Playwright MCP interface
- **THEN** the tool returns a descriptive compatibility error without attempting browser-agent execution

#### Scenario: Consecutive tool invocations use separate contexts
- **WHEN** two `render_and_strip_page` invocations use the configured isolated Playwright MCP server
- **THEN** the second invocation cannot observe pages, cookies, or web storage created by the first invocation

### Requirement: LiteLLM browser-agent invocation
The server SHALL obtain the LiteLLM model identifier, OpenAI-compatible API base URL, API key, and maximum output-token setting from runtime configuration. The maximum output-token setting SHALL default to 1024 and SHALL bound each inner model turn. Every inner model request SHALL set `stream=True`, eligible Playwright callable tools, `tool_choice="auto"`, `temperature=0`, `parallel_tool_calls=False`, and `num_retries=0`. The server SHALL omit provider-specific optional parameters including reasoning effort, seed, and response format. The configured endpoint SHALL support OpenAI-compatible streamed chat function-tool calls with those parameters.

#### Scenario: Default model turn configuration
- **WHEN** the application creates an inner model request without an overridden maximum output-token setting
- **THEN** it requests at most 1024 output tokens, streams the response, enables automatic sequential tool selection, uses zero temperature, and does not retry the request

#### Scenario: Provider emits no reasoning
- **WHEN** the configured model supports tool calling but does not support a provider-specific reasoning parameter
- **THEN** the application does not send a reasoning parameter and continues the browser-agent loop normally

#### Scenario: Model stream does not complete normally
- **WHEN** a streamed model turn is interrupted, reaches its output-token limit, contains malformed or incomplete tool-call data, requests an unknown tool, returns invalid JSON arguments, returns multiple tool calls, or ends for a reason other than normal completion
- **THEN** the tool returns an MCP tool error without extracting or returning HTML

### Requirement: Dependency error propagation
The server SHALL map LiteLLM context-window exceptions to a context-exhausted MCP tool error, other LiteLLM/OpenAI exceptions to an MCP tool error containing the dependency message, and remote FastMCP `ToolError` exceptions to an MCP tool error containing the remote message. Unexpected exceptions SHALL use FastMCP's normal error conversion. No dependency error SHALL produce partial HTML.

#### Scenario: Remote Playwright tool fails
- **WHEN** the FastMCP client raises `ToolError` for a Playwright MCP call
- **THEN** the outer tool fails with an MCP tool error containing the remote error text and performs cleanup

#### Scenario: Model provider fails
- **WHEN** LiteLLM raises an OpenAI-compatible provider exception
- **THEN** the outer tool fails with an MCP tool error containing the provider error text and performs cleanup

### Requirement: Compact current-page model context
The server SHALL start every inner model turn with a fresh conversation containing exactly one stage-specific system message and one user message. The user message SHALL contain the original caller task, the current stage's explicitly permitted prior-stage input, a deterministic stage-local model-action log, the current top-level URL, and the newest fresh browser observation. Access and discovery SHALL receive no prior-stage report. Reconstruction SHALL receive the full access checkpoint. Collection SHALL receive the selected strategy through its strategy-specific instructions and SHALL NOT receive the checkpoint, discovery evidence, or reconstruction evidence. Discovery and collection turns following a browser action SHALL additionally include the immediately preceding fresh observation needed to assess whether page/view content was retained. Initial and reset navigation SHALL NOT appear in model-action logs. The system message SHALL describe only the current stage's objective and completion contract. Eligible Playwright schemas and the current stage's local completion schema SHALL be supplied through the request's `tools` parameter. For each known eligible remote tool, a tool-specific formatter SHALL record the tool name, selected structural arguments, success/failure status, and resulting current URL. It SHALL omit typed text, form values, JavaScript source, file paths, and dropped-data values completely and record only their field names and character/item counts; it SHALL NOT hard-truncate those payload strings. The server SHALL NOT use model content or optional progress to construct the action log. Except for the explicit discovery and collection comparison pair, it SHALL omit earlier raw browser observations and completed assistant/tool message pairs and SHALL NOT include an orphaned `role="tool"` message.

#### Scenario: Current-page cleaning completes without a model browser action
- **WHEN** a caller asks to clean or return content from the initially loaded page
- **THEN** the model still establishes an access checkpoint, discovers collection applicability, reconstructs the checkpoint, and completes retained-document collection before extraction without requiring a remote browser action

#### Scenario: Later browser interaction uses current state
- **WHEN** a stage has completed multiple browser actions and requires another model turn
- **THEN** the next request contains the original task, permitted stage inputs, stage-local deterministic action log, current URL, and newest fresh observation without prior assistant/tool message history

#### Scenario: Discovery compares a probe transition
- **WHEN** discovery completes a browser action intended to reveal more content
- **THEN** its next model turn contains the fresh observations from immediately before and after that action

#### Scenario: Reasoning progress is absent
- **WHEN** the model emits no reasoning progress during multiple browser actions or stages
- **THEN** the server still constructs deterministic stage-local action logs and current-page context from remote tool calls and orchestration-owned snapshots

#### Scenario: Tool has no specific action formatter
- **WHEN** an eligible tool from a compatible Playwright MCP version has no tool-specific summary formatter
- **THEN** the server logs a warning and records a generic action containing the tool name, argument names without values, success/failure status, and resulting current URL

#### Scenario: Newest observation exceeds model context
- **WHEN** the compact stage request exceeds the configured endpoint's context capacity
- **THEN** the tool returns a context-exhausted MCP tool error without truncating required observations or retrying with reduced history

### Requirement: Post-action top-level location invariant
The server SHALL use the documented official Playwright MCP navigation and location-evaluation capabilities to record the initial navigation's final top-level origin. After settling each browser-affecting action and immediately before extraction, it SHALL reject the invocation if the tracked page's observed top-level location differs from that origin. It SHALL reject an observed plain-HTTP location unless `allow_plain_http` is enabled. The origin comparison SHALL use scheme, host, and effective port. This requirement SHALL apply to observed post-action locations and SHALL NOT claim to restrict subresource requests or undetected intermediate locations.

#### Scenario: Initial redirect establishes the origin
- **WHEN** the initial URL redirects to a different origin before the agent begins browser actions
- **THEN** the server records the redirected document origin as the allowed origin

#### Scenario: HTTPS redirect downgrades to HTTP
- **WHEN** an HTTPS initial URL redirects to a plain-HTTP location while `allow_plain_http` is disabled
- **THEN** the tool returns an MCP tool error and does not return HTML

#### Scenario: Agent action changes origin
- **WHEN** a model-requested browser action changes the top-level document to a different origin after initial navigation
- **THEN** the tool returns an MCP tool error and does not return HTML

### Requirement: Secondary browser outputs are ignored
The server SHALL track the tab used for initial navigation as the only page eligible for final DOM extraction. It SHALL reserve remote tab-management tools for internal orchestration and SHALL NOT make them available to the model. After each browser-affecting action, it SHALL reselect the original tab when a popup or new tab becomes active. A secondary tab or download SHALL not contribute to or replace the final page output. If the original tab no longer exists, the invocation SHALL fail.

#### Scenario: Browser action opens a new tab
- **WHEN** a model-requested action opens a popup or new tab
- **THEN** the server uses internal tab management to reselect the original tab and excludes the secondary page from final extraction

#### Scenario: Browser action starts a download
- **WHEN** a model-requested action starts a download
- **THEN** the server does not return the downloaded content and continues tracking the initial top-level page

### Requirement: Bounded agent execution
The server SHALL enforce configurable inclusive per-stage limits for model turns and model-directed browser actions for access, discovery, reconstruction, retained-document collection, and each pagination-advance iteration, plus a configurable positive hard paginated-document limit, an invocation-wide idle limit, and operation limits. The defaults SHALL be 12 model turns and 30 model-directed browser actions for each stage invocation; 25 captured paginated documents; 600 idle seconds; 20 navigation seconds; 15 seconds for each other browser operation; 90 model-request seconds; 0 settle-grace seconds; and 10 cleanup seconds. The idle deadline SHALL reset when the agent receives non-blank model reasoning or reports an operational milestone. The existing final-turn, browser-action, timeout, cleanup, and no-partial-output rules SHALL apply to every new stage invocation and document capture. Per-page stage limits SHALL reset for each pagination iteration, while the idle limit and paginated-document limit SHALL remain invocation-wide.

#### Scenario: Browser action limit is exceeded
- **WHEN** any model-guided stage invocation requests more browser actions than its configured maximum
- **THEN** the server terminates the invocation with an MCP tool error and does not return collected pages

#### Scenario: Paginated-document limit is exceeded
- **WHEN** another potentially relevant result page remains after the configured number of documents has been captured
- **THEN** the server terminates the invocation with an MCP tool error and does not return assembled or partial HTML

#### Scenario: Stage completes on its final turn
- **WHEN** a stage submits its valid completion report on its final permitted model turn
- **THEN** the server accepts that completion without a model-turn limit error

#### Scenario: Final turn requests another browser action
- **WHEN** a stage uses its final permitted model turn to request a browser action
- **THEN** the server rejects the action before remote execution because mandatory stage completion can no longer occur within the turn allowance

#### Scenario: Model completes within limits
- **WHEN** every required stage submits its valid completion report within its limits without the idle timeout expiring
- **THEN** the server proceeds to final document cleaning or assembly after collection completion

#### Scenario: Browser-agent processing starts
- **WHEN** a valid tool invocation begins browser-agent processing
- **THEN** the server starts its isolated browser session without waiting for an application-level concurrency slot

#### Scenario: Cleanup follows timeout or cancellation
- **WHEN** processing fails, times out, or is cancelled
- **THEN** browser cleanup runs once under cancellation shielding for no longer than the configured cleanup timeout

#### Scenario: Cleanup also fails
- **WHEN** browser cleanup fails after an earlier processing error
- **THEN** the outer tool preserves the earlier error and records the cleanup failure without replacing it

#### Scenario: Cleanup is the only failure
- **WHEN** processing succeeds but mandatory browser cleanup fails
- **THEN** the outer tool returns an MCP cleanup error instead of HTML

### Requirement: Paginated visible-document capture and assembly
For paginated collection, the server SHALL capture every visibility-filtered top-level document while it is current and before the next-page action replaces it. After successful semantic or natural completion, it SHALL apply the semantic cleaning policy using each captured document's own top-level URL for link resolution and SHALL assemble the cleaned bodies into one valid HTML document in capture order. A single captured document SHALL preserve the existing cleaned output shape. The configured output-byte limit SHALL apply to the complete assembled UTF-8 result.

#### Scenario: Relative links occur on multiple pages
- **WHEN** captured page documents contain relative links and have different top-level page URLs
- **THEN** each link is resolved against the URL of the document in which it appeared before assembly

#### Scenario: Multiple cleaned documents are assembled
- **WHEN** paginated collection captures more than one page and completes successfully
- **THEN** the result is one valid HTML document containing each complete cleaned body in capture order

#### Scenario: Assembled output exceeds the byte limit
- **WHEN** the complete assembled UTF-8 HTML exceeds the configured output maximum
- **THEN** the invocation fails without returning a smaller or partial document
