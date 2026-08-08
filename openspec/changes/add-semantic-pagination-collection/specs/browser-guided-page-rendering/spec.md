## MODIFIED Requirements

### Requirement: Render-and-strip MCP tool input and result
The MCP server SHALL expose a Streamable HTTP tool named `render_and_strip_page` that accepts a non-empty HTTP(S) initial URL and non-empty natural-language browser task. It SHALL reject a plain-HTTP URL by default and accept it only when `allow_plain_http` is enabled. It SHALL always reject URL schemes other than HTTP(S). On success, the tool SHALL return only one cleaned HTML string produced after successful collection through a supported strategy. For retained-document collection, that string SHALL represent the one final page document. For paginated-document collection, it SHALL contain the captured page documents assembled in source order. On failure, the tool SHALL return an MCP tool error and SHALL NOT return partial HTML.

#### Scenario: Successful retained-document rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose retained-document pipeline completes within its limits
- **THEN** the tool returns only cleaned HTML from the greedily expanded final page state

#### Scenario: Successful paginated rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose paginated-document pipeline reaches semantic or natural completion within its limits
- **THEN** the tool returns only one cleaned HTML document containing all captured page documents in source order

#### Scenario: Invalid tool input
- **WHEN** a caller supplies an empty URL or task, a non-HTTP(S) URL, or a plain-HTTP URL while `allow_plain_http` is disabled
- **THEN** the tool returns a validation error before opening a Playwright MCP session

#### Scenario: Plain HTTP is explicitly enabled
- **WHEN** a caller supplies a plain-HTTP initial URL and `allow_plain_http` is enabled
- **THEN** the tool permits initial navigation

### Requirement: Bounded agent execution
The server SHALL enforce configurable inclusive per-stage limits for model turns and model-directed browser actions for access, discovery, reconstruction, retained-document collection, and each pagination-advance iteration, plus a configurable positive hard paginated-document limit and the existing invocation-wide time and operation limits. The defaults SHALL be 12 model turns and 30 model-directed browser actions for each stage invocation; 25 captured paginated documents; 600 total seconds; 20 navigation seconds; 15 seconds for each other browser operation; 90 model-request seconds; 0 settle-grace seconds; and 10 cleanup seconds. The existing final-turn, browser-action, timeout, cleanup, and no-partial-output rules SHALL apply to every new stage invocation and document capture. Per-page stage limits SHALL reset for each pagination iteration, while the total timeout and paginated-document limit SHALL remain invocation-wide.

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
- **WHEN** every required stage submits its valid completion report within its limits and before the total timeout expires
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

## ADDED Requirements

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
