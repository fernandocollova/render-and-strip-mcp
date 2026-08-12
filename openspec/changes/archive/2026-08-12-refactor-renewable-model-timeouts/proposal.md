## Why

Model-request timeouts currently impose one fixed deadline even while the provider is actively
streaming useful reasoning. Conversely, the invocation-wide deadline is named and renewed as an
idle timeout despite serving as the overall run budget.

## What Changes

- Add a renewable asynchronous timeout that resets its deadline to its configured duration.
- Renew each model request's inactivity deadline when a non-blank reasoning fragment is accepted.
- Remove the idle-aware progress wrapper and let the shared progress reporter optionally renew the
  timeout for the current model turn.
- **BREAKING** Rename `idle_timeout_seconds` to `run_timeout_seconds`, increase its default to
  3600 seconds, and renew it immediately before browser closing.
- Rename the shared reporter from `ReasoningProgressReporter` to `ProgressReporter`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `browser-guided-page-rendering`: Change model and invocation timeout semantics and browser-close
  progress behavior.
- `configurable-mcp-runtime`: Replace the idle-timeout configuration with the run-timeout setting.
- `optional-agent-progress`: Allow model-turn activity to renew its supplied timeout and include
  browser closing in operational progress.

## Impact

- Affected code: browser orchestration, stage execution, reasoning progress, runtime settings, and
  a new `RenewableTimeout` utility.
- Affected configuration: TOML and `RENDER_AND_STRIP_MCP_AGENT__RUN_TIMEOUT_SECONDS`; the retired
  idle-timeout key is rejected by strict settings validation.
- Affected tests and documentation: timeout, progress, agent-loop, browser-agent, configuration,
  example TOML, and README coverage.
