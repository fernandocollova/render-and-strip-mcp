## 1. Typed Stage Contracts

- [x] 1.1 Add strict request-local models for access checkpoints, discovery reports, reconstruction reports, and collection reports, including validation of non-empty semantic evidence and the two allowed discovery outcomes.
- [x] 1.2 Define stage-specific local completion-tool schemas and domain errors for missing, malformed, unknown, unsupported, and unsuccessful stage outcomes; add focused validation tests.
- [x] 1.3 Extend model tool catalogs and streamed tool-call parsing to distinguish locally handled completion calls from remotely executable Playwright calls, reject name collisions, and test valid and invalid routing.

## 2. Fresh Browser State

- [x] 2.1 Pin `browser_snapshot` in the tested official Playwright MCP contract, reserve it for orchestration, add a fresh-state helper with optional settle grace, and update compatibility and tool-catalog tests.
- [x] 2.2 Change successful browser-action execution to apply optional grace, restore the original tab, validate its origin, and capture a fresh page state after each model-directed action; test call ordering, zero-grace behavior, popup restoration, independent operation timeouts, and stale action-result exclusion.
- [x] 2.3 Use the same fresh-state boundary after initial and reset navigation, with navigation and browser-operation timeouts applied independently; add ordering, redirect, pending-state, and failure tests.

## 3. Stage-Aware Model Loop

- [x] 3.1 Replace the single fixed system prompt with access, discovery, reconstruction, and retained-collection prompt builders that define page/view-level retrieval, semantic waiting, and operational discovery rules; preserve redacted action summaries and expose only the permitted prior-stage inputs and required current or before/after fresh observations.
- [x] 3.2 Generalize the agent loop into a typed stage runner that requires the current local completion tool, returns its validated report and final page state, rejects ordinary terminal responses, and keeps one remote browser call per model turn.
- [x] 3.3 Enforce inclusive fresh model-turn and browser-action counters for each stage while retaining invocation-wide timeout and progress accounting; test completion on the final turn, rejection of a final-turn browser action before execution, exact action maxima, and cross-stage resets.
- [x] 3.4 Test the stage-input matrix: no prior report for access/discovery, the full checkpoint only for reconstruction, only the selected strategy for collection, and no orchestration navigation in model-action logs.

## 4. Greedy Collection Pipeline

- [x] 4.1 Implement access-stage coordination that reaches the requested target page/view and produces its semantic target, reconstruction instructions, and verification checkpoint, including the already-data-ready case without fine-grained fact extraction.
- [x] 4.2 Implement discovery coordination with explicit mechanism inspection, fresh probe transitions, safe probing without a fixed count, evidence, `retained-final-document` dispatch, and clear no-partial-result failure for `unknown` or malformed completion.
- [x] 4.3 Implement reset to the exact caller URL in the same tracked browser context followed by a fresh observation and checkpoint-guided reconstruction, including semantic waits and explicit verification without replaying old element references or discovery history.
- [x] 4.4 Implement retained-final-document collection as a plain async strategy function with an explicit strategy dispatch map, semantic waits for pending effects, final page/view exhaustion report, contradiction failure, and no handler for `unknown`.
- [x] 4.5 Refactor `BrowserAgent` to orchestrate initial navigation, all four stages, reset, final same-origin validation, one final DOM extraction, policy-based cleaning without post-clean semantic verification, and existing cancellation-shielded cleanup in the specified order.

## 5. Operational and Reasoning Progress

- [x] 5.1 Generalize progress handling so operational milestones and streamed model reasoning share one invocation-wide item count, configured maximum, minimum interval, ordered coalescing, and best-effort delivery behavior; add mixed-item limit and ordering tests.
- [x] 5.2 Emit distinctly labelled milestones for initial navigation, access, discovery, reset, reconstruction, collection, and final extraction/cleaning without synthesizing reasoning or directly serializing checkpoint/report fields; test that reconstruction reasoning may still refer to checkpoint context.

## 6. Behavioral and Failure Coverage

- [x] 6.1 Add deterministic coordinator tests covering the full successful stage sequence, an empty access instruction list, semantic reconstruction with changed browser targets, stage-input isolation, final extraction only after complete collection, policy-based cleaning without fact verification, and unchanged HTML-only public output.
- [x] 6.2 Add failure-matrix tests proving that invalid checkpoints, ordinary no-tool completion, `unknown` discovery, failed reconstruction, visibly pending completion, collection contradiction, unbounded collection limits, context exhaustion, origin changes, and cleanup failures never return or extract partial HTML.
- [x] 6.3 Add a deterministic expandable/lazy fixture and real-browser integration coverage for orchestration-owned fresh snapshots, model-directed semantic waits, and final visibility retention without relying on nondeterministic model-directed tool calls.
- [x] 6.4 Replace the Compose public-tool cleaning test that depends on no-tool model completion with deterministic transport coverage, and document the tool-capable-model requirement for a live staged end-to-end test.
- [x] 6.5 Add deterministic staged end-to-end coverage proving finite incremental scrolling is classified as `retained-final-document` and numbered replacement pagination is classified as `unknown` without extracting partial HTML.

## 7. Configuration and Documentation

- [x] 7.1 Update settings tests, the full example configuration, and README limit documentation to state that existing model-turn and browser-action values apply independently to all four stages, operation timeouts are independent, settle grace defaults to zero, and the total timeout remains invocation-wide.
- [x] 7.2 Document greedy-by-default page/view retrieval, semantic reconstruction and waits, discovery evidence, supported retained-final-document interactions, `unknown` failure, unbounded-feed failure, cleaner-policy boundaries, same-origin/original-tab constraints, and the absence of fine-grained extraction, partial results, or a public opt-out.
- [x] 7.3 Document that existing reasoning-progress settings now govern the shared operational-and-reasoning progress stream and that operational milestones consume the configured item allowance.

## 8. Verification

- [x] 8.1 Run Ruff checks and formatting, the complete pytest suite with branch coverage, and the deterministic Compose integration suite; resolve all regressions.
- [x] 8.2 Validate the OpenSpec change strictly and confirm the implemented behavior and documentation satisfy every added and modified scenario.
