## 1. Collection Region Contract

- [x] 1.1 Extend collection completion reports and prompts with a validated current element description and snapshot target for one task-relevant region.
- [x] 1.2 Update collection strategy handoffs so every completed retained page passes its selected region to capture before any pagination advancement.

## 2. Selected Content Capture

- [x] 2.1 Replace whole-document retrieval with visible selected-subtree retrieval through the pinned targeted `browser_evaluate` contract.
- [x] 2.2 Update browser orchestration and request-local capture models to validate, capture, and retain each selected region with its source URL.

## 3. Uniform Semantic Normalization

- [x] 3.1 Refactor cleaning so selected regions are independently normalized and source-relative links are resolved without producing strategy-specific final documents.
- [x] 3.2 Assemble both one-region and many-region results into the same fixed document with one top-level `main`, capture-order content, no page wrappers, and aggregate size enforcement.

## 4. Verification and Documentation

- [x] 4.1 Update stage-model, collection-strategy, browser-agent, selected-content capture, cleaner, and assembly unit tests for success and failure behavior.
- [x] 4.2 Update integration fixtures and README descriptions to document selected-region output and the common normalized shape.
- [x] 4.3 Run Ruff checks, formatting verification, the complete pytest suite, and OpenSpec validation.
