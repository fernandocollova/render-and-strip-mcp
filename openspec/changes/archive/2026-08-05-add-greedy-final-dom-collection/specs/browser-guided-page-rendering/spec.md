## MODIFIED Requirements

### Requirement: Render-and-strip MCP tool input and result
The MCP server SHALL expose a Streamable HTTP tool named `render_and_strip_page` that accepts a non-empty HTTP(S) initial URL and non-empty natural-language browser task. It SHALL reject a plain-HTTP URL by default and accept it only when `allow_plain_http` is enabled. It SHALL always reject URL schemes other than HTTP(S). On success, the tool SHALL return only the cleaned HTML string produced after successful greedy retained-final-document collection. On failure, the tool SHALL return an MCP tool error and SHALL NOT return partial HTML.

#### Scenario: Successful browser-guided rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose access, discovery, reconstruction, and collection stages complete within their limits
- **THEN** the tool returns only cleaned HTML from the greedily expanded final page state

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

### Requirement: Bounded agent execution
The server SHALL enforce configurable inclusive per-stage limits for model turns and model-directed browser actions, plus configurable limits for total invocation time, per-navigation operation, other browser operations, each model request, optional post-action settle grace, and cleanup. The defaults SHALL be 12 model turns and 30 model-directed browser actions for each of access, discovery, reconstruction, and collection; 600 total seconds; 20 navigation seconds; 15 seconds for each other browser operation; 90 model-request seconds; 0 settle-grace seconds; and 10 cleanup seconds. A stage MAY submit valid local completion on its final permitted model turn. Subject to the model-turn allowance, it MAY execute exactly its configured browser-action maximum and SHALL reject an additional action before execution. If the final permitted model turn requests a browser action, the stage SHALL reject that action before execution because no turn remains for mandatory completion. Initial, reset, and model-directed navigation calls SHALL each use the navigation timeout. Other model-directed browser calls, orchestration tab operations, location evaluation, snapshots, and final extraction SHALL each independently use the browser-action timeout; these deadlines SHALL NOT form one composite action timeout. Total time SHALL begin when browser-agent invocation processing begins and include validation, every stage, reset, browser and model work, optional grace periods, extraction, and cleaning. Cleanup SHALL run once in a cancellation-shielded `finally` block and MAY extend execution only by its cleanup timeout.

#### Scenario: Browser action limit is exceeded
- **WHEN** any model-guided stage requests more browser actions than the configured per-stage maximum
- **THEN** the server terminates the invocation with an MCP tool error and does not return the current page

#### Scenario: Stage completes on its final turn
- **WHEN** a stage submits its valid local completion call on its final permitted model turn
- **THEN** the server accepts that completion without a model-turn limit error

#### Scenario: Final turn requests another browser action
- **WHEN** a stage uses its final permitted model turn to request a browser action
- **THEN** the server rejects the action before remote execution because mandatory stage completion can no longer occur within the turn allowance

#### Scenario: Model completes within limits
- **WHEN** every model-guided stage submits its valid completion report within its inclusive per-stage limits and before the total timeout expires
- **THEN** the server proceeds to final-page extraction after collection completion

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
