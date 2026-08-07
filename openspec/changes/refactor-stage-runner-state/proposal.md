## Why

`run_stage` receives the same settings, tool catalog, browser executor, and progress reporter for every stage in a browser session. Grouping these stable dependencies in a runner clarifies their lifetime and removes repeated call-site wiring, while a dedicated fresh state object makes the per-stage isolation explicit.

## What Changes

- Introduce a session-scoped stage runner that owns the stable dependencies used by every stage invocation.
- Introduce a separate mutable state object created for each stage run to hold its action log, current and preceding page states, and browser-action count.
- Introduce one class per stage to own its prompt, completion tool, required context, and message extensions.
- Require the progress reporter and model reasoning sink that every application-owned execution path supplies.
- Preserve existing stage behavior, completion validation, context construction, limits, and error handling.

## Capabilities

### New Capabilities

None. This is an internal refactor with no behavior change.

### Modified Capabilities

None.

## Impact

- Affects `src/render_and_strip_mcp/agent_loop.py`, its callers, and focused unit tests.
- No external API, configuration, dependency, or browser-agent behavior changes.
