## MODIFIED Requirements

### Requirement: Greedy retained-final-document collection
The `retained-final-document` strategy SHALL run a model-guided collection stage that exhausts non-destructive in-place reveal mechanisms belonging to the target page/view, including incremental scrolling or lazy loading, additive load-more controls, content-expansion controls, and disclosures that can remain open simultaneously. Collection SHALL request eligible semantic waits when a fresh observation shows a loading indicator, a missing expected action effect, or another pending state. It SHALL preserve previously revealed target-view content and SHALL complete only after a final verification sweep finds no new target-view content, no unused relevant retained-document reveal control, no visible pending state, and no loss of previously revealed target-view content. Successful completion SHALL identify exactly one current contiguous task-relevant content region by a non-empty element description and fresh snapshot target. The region SHALL contain all content relevant to the caller task and SHALL exclude surrounding page-level chrome. The service SHALL immediately capture that region's visibility-filtered subtree and SHALL apply the common normalized semantic HTML policy without post-clean semantic validation. It SHALL fail without HTML if the region report is malformed or the selected target cannot be resolved and captured.

#### Scenario: Additive content is exhausted
- **WHEN** scrolling or an additive control repeatedly reveals relevant content and eventually reaches a stable end
- **THEN** collection continues through the end, verifies that earlier content remains visible, selects the complete task-content region, and returns its content through the common normalization path

#### Scenario: Retainable expansions are opened
- **WHEN** relevant collapsed sections or expandable records can remain open simultaneously
- **THEN** collection opens the relevant expansions, leaves them open, and includes them in the selected content region

#### Scenario: Collection reveals unsupported behavior
- **WHEN** collection cannot preserve earlier relevant content or otherwise contradicts the selected retained-document strategy
- **THEN** the invocation fails without returning partial HTML

#### Scenario: Append-only source has no finite observed end
- **WHEN** collection continues finding new relevant content until a model-turn, browser-action, or total-time limit is reached
- **THEN** the invocation fails without extracting or returning partial HTML

#### Scenario: Selected content target is unavailable
- **WHEN** collection completes with a malformed, missing, stale, or unresolvable selected-region target
- **THEN** the invocation fails without falling back to the whole body or returning partial HTML

### Requirement: Composed paginated-document collection
The `paginated-documents` strategy SHALL run retained-document collection on the current result page, capture its one selected visibility-filtered task-content region before replacement, and then run model-guided page advancement. It SHALL repeat in source order until semantic or natural completion. It SHALL preserve each whole selected boundary-page region, SHALL NOT filter individual records from a selected region, and SHALL NOT follow record-detail or expanded-reading links as pagination controls. It SHALL reject unchanged transitions and repeated collected page states rather than silently duplicate content. After completion it SHALL normalize every selected region through the same path used for retained-document collection and assemble their content in source order under one `main` without surrounding page-level chrome or page-boundary wrappers.

#### Scenario: Multiple result pages are collected
- **WHEN** each result page has an enabled immediate next-page control and later pages may still satisfy the caller task
- **THEN** the service exhausts retained content, selects and captures one task-content region on each page before replacement, advances one result page at a time, and assembles normalized region content in source order

#### Scenario: Boundary falls within a page
- **WHEN** a selected boundary-page region contains both records that do and do not satisfy the semantic cutoff and later pages cannot contain relevant records
- **THEN** the service retains the whole selected boundary-page region and stops without advancing

#### Scenario: Record detail link is present
- **WHEN** a result record offers a detail, `Read more`, or equivalent non-pagination link
- **THEN** paginated collection does not follow that link as part of result-page traversal

#### Scenario: Pagination repeats or does not replace the page
- **WHEN** advancement reports continuation but produces an unchanged or previously collected page state
- **THEN** the invocation fails without assembled or partial HTML
