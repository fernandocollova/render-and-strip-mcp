## Why

The renderer can greedily reveal content only when it remains in one final DOM, so ordinary numbered or next-page result sets are rejected even when every page is safely readable. It needs bounded multi-document pagination that composes the existing retained-document behavior on each page and uses the caller's natural-language task to decide when later pages are no longer relevant.

## What Changes

- Add a `paginated-documents` discovery and collection strategy for same-origin result pages whose next-page action replaces the current document.
- Run existing retained-document collection independently on every visited page, capture that page before navigation replaces it, and combine all captured pages into one cleaned result.
- Let a model-guided page-advance stage interpret any semantic stopping condition in the original task, retain compact cross-page progress, and default to the site's natural terminal page when the task has no explicit cutoff.
- Continue when the model cannot prove later pages are irrelevant; stop only at a semantic cutoff or natural terminal page.
- Add a configurable hard document limit. Reaching it before semantic or natural completion fails without returning partial HTML.
- Preserve whole boundary-page documents and do not follow per-record detail links such as GitHub release `Read more` links.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `greedy-page-content-collection`: Add discovery, reconstruction, progress handoff, completion, and safety requirements for composed paginated-document collection.
- `browser-guided-page-rendering`: Permit bounded multi-document capture and assembly while preserving same-origin, visible-document, cleaning, timeout, and no-partial-result guarantees.

## Impact

- Affects browser-agent orchestration, stage models and prompts, collection strategy dispatch, document cleaning/assembly, runtime agent settings, and focused unit tests.
- The public tool signature remains `render_and_strip_page(url, task)`; semantic cutoff wording stays in `task`.
- Configuration gains a maximum paginated-document setting.
- No new external dependency or GitHub-specific behavior is introduced.
