## Why

The current reasoning-progress policy treats the configured item maximum as an invocation-wide allowance and permits application cleanup to bypass the configured interval. This makes the configured rate difficult to reason about and allows progress delivery behavior to leak into orchestration code.

## What Changes

- Redefine `reasoning_progress_max_items` as the maximum number of reasoning fragments and operational statuses in one progress delivery; `0` remains unlimited for a delivery.
- Enforce `reasoning_progress_min_interval_seconds` between successful deliveries, including model-turn and browser-agent cleanup checks; `0` continues to deliver immediately.
- Add public `ReasoningProgressReporter.flush_if_needed()` and move all delivery eligibility decisions into the reporter.
- Deliver batches through the FastMCP context with the batch fragment count as `progress` and the ordered, newline-joined batch text as `message`.
- Preserve shared buffering, ordering, best-effort error handling, and whitespace-fragment filtering for reasoning and operational statuses.
- Update only the reasoning-progress unit tests and affected agent-loop/browser-agent tests. Playwright tool-validation behavior and its tests remain out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `optional-agent-progress`: Change item limiting and interval semantics from an invocation-wide quota with forced end-of-turn delivery to per-delivery batches with interval-respecting eligibility checks.

## Impact

- Affected code: `reasoning_progress.py`, its construction in `server.py`, and progress flush call sites in `agent_loop.py` and `browser_agent.py`.
- Affected tests: reasoning-progress tests plus the focused agent-loop and browser-agent progress call-site tests.
- The progress payload changes from cumulative progress/total to batch-size progress, using FastMCP `Context.report_progress`; no dependency or Playwright validation changes are required.
