## Why

The public caller task currently carries instructions about browser-agent state and tool use even though the MCP service—not its caller—controls the initial navigation and model prompt. This leaks an internal implementation detail into the public contract and makes ordinary current-page cleaning requests needlessly prescriptive.

## What Changes

- Add internal browser-agent prompt guidance that tells the model the requested page has already been loaded and that it must complete without browser calls when the caller only asks to clean the current page.
- Preserve model-directed browser actions for caller tasks that genuinely require interaction or navigation after the initial page load.
- Simplify the Compose end-to-end request so it sends only the caller's page-cleaning task rather than internal execution instructions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `browser-guided-page-rendering`: The browser-agent model context must communicate the internally completed initial navigation and conditionally prevent unnecessary browser actions for current-page-only cleaning.

## Impact

- Affects browser-agent system prompt construction and its unit tests.
- Updates the Compose-backed end-to-end request fixture.
- Does not change the public MCP tool parameters, runtime configuration, dependencies, or cleaned-HTML result format.
