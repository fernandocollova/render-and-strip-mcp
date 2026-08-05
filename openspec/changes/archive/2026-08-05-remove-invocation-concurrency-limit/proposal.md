## Why

The server no longer needs to bound application-level browser-session concurrency. Retaining the configurable semaphore adds configuration, queueing, and timeout behavior without supporting the intended lightweight page-rendering workload.

## What Changes

- Remove application-level concurrency gating from browser-agent invocation startup.
- Remove the `agent.max_concurrent_invocations` TOML and environment configuration setting.
- **BREAKING** Existing configurations that set `max_concurrent_invocations` are no longer accepted.
- Remove concurrency-specific documentation and tests while retaining all other execution, timeout, cancellation, and browser-cleanup controls.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configurable-mcp-runtime`: Remove the maximum concurrent invocation setting and its request-policy behavior.
- `browser-guided-page-rendering`: Remove concurrency queueing from the bounded-execution contract while retaining the invocation timeout and cleanup guarantees.

## Impact

- Affected code: runtime settings, FastMCP server wiring, browser-agent orchestration, and the invocation-gate module.
- Affected configuration: `agent.max_concurrent_invocations` and `RENDER_AND_STRIP_MCP_AGENT__MAX_CONCURRENT_INVOCATIONS` are removed.
- Affected documentation and tests: the example TOML, README request-policy section, configuration tests, and session-control tests.
