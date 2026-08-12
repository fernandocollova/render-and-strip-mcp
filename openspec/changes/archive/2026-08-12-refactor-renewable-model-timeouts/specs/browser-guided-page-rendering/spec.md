## MODIFIED Requirements

### Requirement: Bounded agent execution
The server SHALL enforce configurable inclusive per-stage limits for model turns and model-directed browser actions for access, discovery, reconstruction, retained-document collection, and each pagination-advance iteration, plus a configurable positive hard paginated-document limit, an invocation-wide run limit, and operation limits. The defaults SHALL be 12 model turns and 30 model-directed browser actions for each stage invocation; 25 captured paginated documents; 3600 run seconds; 20 navigation seconds; 15 seconds for each other browser operation; 90 model-request inactivity seconds; 0 settle-grace seconds; and 10 cleanup seconds. A model request deadline SHALL reset when the agent receives a non-blank model reasoning fragment during that request. The run deadline SHALL reset immediately before browser closing. The existing final-turn, browser-action, timeout, cleanup, and no-partial-output rules SHALL apply to every new stage invocation and document capture. Per-page stage limits SHALL reset for each pagination iteration, while the run limit and paginated-document limit SHALL remain invocation-wide.

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

#### Scenario: Model emits active reasoning within its original request deadline
- **WHEN** a model turn receives a non-blank reasoning fragment before its current model-request deadline
- **THEN** the server resets that model turn's deadline to the configured model-request duration from receipt of the fragment

#### Scenario: Model reasoning is absent or blank
- **WHEN** a model turn receives no reasoning fragments or only blank reasoning fragments
- **THEN** the model-request deadline is not renewed

#### Scenario: Model completes within limits
- **WHEN** every required stage submits its valid completion report within its limits without the run timeout expiring
- **THEN** the server proceeds to final document cleaning or assembly after collection completion

#### Scenario: Browser-agent processing starts
- **WHEN** a valid tool invocation begins browser-agent processing
- **THEN** the server starts its isolated browser session without waiting for an application-level concurrency slot

#### Scenario: Browser cleanup begins
- **WHEN** browser-agent processing reaches its browser-closing step
- **THEN** the server resets the active run deadline to the configured run duration before closing the remote browser

#### Scenario: Cleanup follows timeout or cancellation
- **WHEN** processing fails, times out, or is cancelled
- **THEN** browser cleanup runs once under cancellation shielding for no longer than the configured cleanup timeout

#### Scenario: Cleanup also fails
- **WHEN** browser cleanup fails after an earlier processing error
- **THEN** the outer tool preserves the earlier error and records the cleanup failure without replacing it

#### Scenario: Cleanup is the only failure
- **WHEN** processing succeeds but mandatory browser cleanup fails
- **THEN** the outer tool returns an MCP cleanup error instead of HTML
