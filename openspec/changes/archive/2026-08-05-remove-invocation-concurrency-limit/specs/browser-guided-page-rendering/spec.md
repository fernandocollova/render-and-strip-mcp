## MODIFIED Requirements

### Requirement: Bounded agent execution
The server SHALL enforce configurable limits for model turns, browser actions, total invocation time, per-navigation time, per-browser-action time, per-model-request time, post-action page-settle time, and cleanup time. The defaults SHALL be 12 model turns, 30 browser actions, 600 total seconds, 20 navigation seconds, 15 browser-action seconds, 90 model-request seconds, 2 settle seconds, and 10 cleanup seconds. Total time SHALL begin when browser-agent invocation processing begins and include validation, browser and model work, settling, extraction, and cleaning. Cleanup SHALL run once in a cancellation-shielded `finally` block and MAY extend execution only by its cleanup timeout.

#### Scenario: Browser action limit is exceeded
- **WHEN** the agent requests more browser actions than the configured maximum
- **THEN** the server terminates the invocation with an MCP tool error and does not return the current page

#### Scenario: Model completes within limits
- **WHEN** the model finishes without a tool call before any configured limit expires
- **THEN** the server proceeds to final-page extraction

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
