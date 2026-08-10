## Why

The tool currently returns different document shapes for retained and paginated collection and, for pagination, repeats whole-page chrome around every captured result page. Callers instead need one predictable semantic document containing only the task-relevant rendered content, regardless of the collection strategy.

## What Changes

- **BREAKING**: Require every successful retained-document collection stage to identify one task-relevant content region from its final fresh browser observation.
- Capture only that visibility-filtered region, excluding surrounding page-level header, navigation, sidebar, search, and footer chrome by boundary rather than by deleting semantic tags inside the region.
- Normalize all captured regions independently with the existing safety, visibility, link, and semantic-element policies.
- Return the same fixed HTML shape for one or many captures: one document skeleton whose body contains one `main` with normalized region content in source order.
- Fail without partial HTML when a selected region is missing, stale, malformed, or cannot be captured.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `greedy-page-content-collection`: Collection completion identifies and captures one task-relevant region per retained result page instead of each whole top-level document.
- `semantic-html-cleaning`: Cleaning and assembly normalize selected content regions into one strategy-independent semantic document shape.
- `browser-guided-page-rendering`: The public tool's successful output contract changes from cleaned whole-page documents to normalized selected content.

## Impact

The change affects collection completion models and prompts, rendered-content capture through the pinned Playwright MCP contract, collection strategy handoffs, semantic cleaning and assembly, browser-agent orchestration, unit fixtures, specifications, and README output documentation. The public tool signature remains unchanged and no new runtime dependency is required.
