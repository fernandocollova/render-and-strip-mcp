## Why

The service currently returns the final rendered DOM without ensuring that ordinary lazy, collapsed, or incrementally appended page content has been revealed. Callers that ask for page data therefore receive incomplete results unless they already know which browser interactions to request.

## What Changes

- **BREAKING**: Make greedy content discovery and expansion the default behavior of the existing `render_and_strip_page(url, task)` tool, including requests that previously cleaned the initially loaded page without browser interaction.
- Separate browser work into access, strategy-discovery, reconstruction, and collection stages while preserving one isolated browser session and one final HTML-only result.
- Have the access model produce a validated semantic checkpoint containing the target page or view state, reconstruction instructions, and verification conditions without treating the browser task as a fine-grained extraction query.
- Have discovery inspect and, where needed, safely probe page behavior and select only the retained-final-document strategy implemented by this change; classify every unproven or unsupported behavior as `unknown` and fail without returning partial HTML.
- Reconstruct the data-ready checkpoint from the caller's initial URL with a fresh, checkpoint-guided model run before collection.
- Implement retained-final-document collection by directing the model to exhaust relevant non-destructive scrolling, lazy loading, additive controls, and simultaneously retainable expansions before final DOM extraction.
- Replace unconditional post-action sleeping with fresh orchestration-owned snapshots after remote actions complete, while retaining the existing settle setting as an optional grace period that defaults to zero and allowing the model to request semantic waits when page state is visibly pending.
- Apply the configured model-turn and browser-action limits separately to each model-driven stage while retaining one total invocation timeout and the existing all-or-nothing result policy.
- Emit rate-limited operational milestones for navigation and each pipeline stage through the same invocation-wide progress policy as streamed model reasoning.
- Introduce a small strategy dispatch boundary so later changes can add collection strategies without restructuring access, discovery, reconstruction, or final extraction.

## Capabilities

### New Capabilities
- `greedy-page-content-collection`: Semantic access checkpoints, behavior discovery, checkpoint reconstruction, retained-final-document collection, unsupported-behavior failure, and extensible collection-strategy dispatch.

### Modified Capabilities
- `browser-guided-page-rendering`: Replace the single generic browser-agent loop with staged model-guided rendering and extract the final document only after successful greedy collection.
- `configurable-mcp-runtime`: Define existing model-turn and browser-action settings as per-stage limits while preserving one invocation-wide total timeout.
- `optional-agent-progress`: Extend the existing invocation-wide reasoning-progress stream with rate-limited operational milestones without suppressing model reasoning.

## Impact

- Browser orchestration, model prompts and completion contracts, model-tool catalog handling, execution-limit accounting, and domain errors will change.
- The public MCP tool name, arguments, HTML-only success type, same-origin policy, original-tab policy, Playwright MCP dependency, and semantic HTML cleaner remain unchanged.
- Unit tests will gain deterministic staged-model and browser-state fixtures; integration fixtures will cover retained expansions and semantic waits without depending on nondeterministic model navigation.
- README and example configuration documentation will describe greedy defaults, staged limits, optional settle grace, operational progress, and explicit failure for unsupported or unbounded collection.
