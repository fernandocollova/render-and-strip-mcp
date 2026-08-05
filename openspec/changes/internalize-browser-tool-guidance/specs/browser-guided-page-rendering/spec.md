## MODIFIED Requirements

### Requirement: Compact current-page model context
The server SHALL start every inner model turn with a fresh conversation containing exactly one system message with browser-agent instructions and one user message with the original caller task, deterministic action log, current top-level URL, and newest browser observation. The system message SHALL state that the service has already loaded the caller's initial page before the first model turn, SHALL direct the model to end normally without a browser tool call when the caller only asks to clean the current page, and SHALL limit browser calls to actions necessary to complete other caller tasks. Eligible Playwright schemas SHALL be supplied through the request's `tools` parameter. For each known eligible tool, a tool-specific formatter SHALL record the tool name, selected structural arguments, success/failure status, and resulting current URL. It SHALL omit typed text, form values, JavaScript source, file paths, and dropped-data values completely and record only their field names and character/item counts; it SHALL NOT hard-truncate those payload strings. The server SHALL NOT use model content or optional reasoning progress to construct the log. The newest browser observation SHALL be represented as ordinary user-message current-state context. The server SHALL omit earlier raw browser observations and completed assistant/tool message pairs, and SHALL NOT include an orphaned `role="tool"` message.

#### Scenario: Current-page cleaning completes without a model browser action
- **WHEN** a caller asks only to clean the current page after the service has loaded the initial URL
- **THEN** the first model request supplies the internal loaded-page instruction, the model completes without a browser tool call, and the server extracts and cleans the already loaded page

#### Scenario: Later browser interaction uses current state
- **WHEN** the agent has completed multiple browser actions and requires another model turn
- **THEN** the next request contains the original task, deterministic action log, current URL, and newest browser observation without prior raw tool-result history

#### Scenario: Reasoning progress is absent
- **WHEN** the model emits no reasoning progress during multiple browser actions
- **THEN** the server still constructs the deterministic action log and current-page context from remote tool calls and results

#### Scenario: Tool has no specific action formatter
- **WHEN** an eligible tool from a compatible Playwright MCP version has no tool-specific summary formatter
- **THEN** the server logs a warning and records a generic action containing the tool name, argument names without values, success/failure status, and resulting current URL

#### Scenario: Newest observation exceeds model context
- **WHEN** the compact current-page model request exceeds the configured endpoint's context capacity
- **THEN** the tool returns a context-exhausted MCP tool error without truncating the newest observation or retrying with reduced history
