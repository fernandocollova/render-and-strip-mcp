## Why

The configured progress interval currently applies from invocation start as well as between
deliveries. Tests incorrectly assumed the first progress fragment bypassed a positive interval.

## What Changes

- Preserve the initial progress delay for positive `reasoning_progress_min_interval_seconds` values.
- Clarify the interval requirement and scenarios for the first progress batch.
- Update progress-reporter tests to assert the configured initial delay and FIFO batching behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `optional-agent-progress`: Clarify that a positive delivery interval delays the first eligible
  progress batch until the interval has elapsed from invocation start.

## Impact

- `src/render_and_strip_mcp/reasoning_progress.py`
- `tests/unit/test_reasoning_progress.py`
- `openspec/specs/optional-agent-progress/spec.md`
