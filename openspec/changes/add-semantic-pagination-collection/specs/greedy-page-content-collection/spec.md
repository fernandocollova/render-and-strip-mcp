## MODIFIED Requirements

### Requirement: Retained-document strategy discovery
The service SHALL run a model-guided discovery stage from the data-ready state and SHALL provide fresh page observations from before and after discovery probes. Discovery SHALL explicitly inspect for apparent reveal and page-advance mechanisms and SHALL return exactly one of `retained-final-document`, `paginated-documents`, or `unknown` through a validated completion report. It SHALL ignore controls that are not plausibly related to revealing or advancing the caller's target result set. When a behavioral probe is needed, discovery SHALL activate only a plausibly relevant control whose user-visible semantics indicate a non-mutating content reveal or immediate result-page advance, SHALL probe one transition at a time, and SHALL compare the fresh observations before and after it. It SHALL NOT submit forms, change target filters or selections, authenticate, create or modify data, delete data, start downloads, follow record-detail links, or activate a control with uncertain effects. A plausibly relevant control that remains unsafe or ambiguous SHALL require `unknown` only when leaving it unused prevents discovery from establishing a complete supported collection path; an unrelated or redundant ambiguous control alone SHALL NOT require `unknown`. Discovery MAY select `retained-final-document` for a static page without a mutating probe when inspection finds no relevant reveal mechanism. It SHALL select `retained-final-document` only when content belonging to the target page/view can be exposed and remain simultaneously present in one visibility-filtered top-level document. It SHALL select `paginated-documents` only when an immediate next-page action replaces the current target-result document with another same-origin document and can be composed with retained-document collection on each page. It SHALL classify every unprobeable, unproven, virtualized, mixed, ambiguous, or otherwise unsupported behavior that prevents complete supported collection as `unknown`. Its evidence SHALL identify what was inspected or probed and why the selected behavior was established.

#### Scenario: Static content is already retained
- **WHEN** the target page/view content is already present throughout the rendered document and explicit inspection finds no additional relevant reveal mechanism
- **THEN** discovery selects `retained-final-document`

#### Scenario: Probe appends and retains relevant content
- **WHEN** a discovery probe reveals additional relevant content while preserving previously revealed relevant content in the visible top-level document
- **THEN** discovery may select `retained-final-document` after it establishes that the applicable reveal mechanisms have retained-document behavior

#### Scenario: Finite incremental scrolling retains relevant content
- **WHEN** discovery and retained-document collection use incremental scrolling that reveals a finite amount of additional target-view content while preserving earlier visible content
- **THEN** discovery selects `retained-final-document`, collection reaches the observed end, and final extraction includes the retained revealed content

#### Scenario: Clearly non-mutating relevant control is probed
- **WHEN** a control is plausibly relevant to target-content revelation and its visible semantics clearly indicate scrolling, disclosure, additive loading, or immediate result-page advancement
- **THEN** discovery may activate one transition and compare the fresh observations before and after it

#### Scenario: Ambiguous control is unrelated or redundant
- **WHEN** a control has uncertain effects but is not plausibly related to the target result set or is unnecessary to establish a complete supported collection path
- **THEN** discovery leaves it unused without classifying the otherwise supported page behavior as `unknown`

#### Scenario: Ambiguous relevant control prevents completeness
- **WHEN** a plausibly relevant control has uncertain or potentially mutating effects and leaving it unused prevents discovery from establishing complete supported collection
- **THEN** discovery does not activate it and reports `unknown`

#### Scenario: Numbered or next-page navigation replaces the result document
- **WHEN** discovery establishes that an immediate next-page action replaces the current same-origin target-result document and that each page supports retained-document collection
- **THEN** discovery selects `paginated-documents`

#### Scenario: Discovery cannot establish supported behavior
- **WHEN** discovery observes or cannot rule out unsafe, virtualized, mixed, ambiguous, or otherwise unsupported behavior
- **THEN** discovery reports `unknown`

#### Scenario: Discovery report is malformed
- **WHEN** the discovery model stops without the required completion report or supplies an unsupported strategy value or malformed report
- **THEN** the invocation fails without reconstruction, collection, or HTML output

### Requirement: Unsupported discovery fails before collection
The service SHALL implement `retained-final-document` and `paginated-documents` collection strategies. An `unknown` discovery result SHALL fail the invocation before reset, reconstruction, collection, or final-document extraction, and the service SHALL NOT return the current page as a partial result.

#### Scenario: Unknown page behavior
- **WHEN** discovery reports `unknown`
- **THEN** the tool returns a clear unsupported-collection error without resetting the page or returning HTML

### Requirement: Stage-local context and limits
Access, discovery, reconstruction, retained-document collection, and each pagination-advance iteration SHALL use fresh stage-local model-action histories and separate configured model-turn and model-directed browser-action counters. Access and discovery SHALL receive no prior-stage report, reconstruction SHALL receive the full access checkpoint, retained-document collection SHALL receive its selected per-page strategy without checkpoint or discovery evidence, and pagination advancement SHALL receive the original task, the deterministic number of captured documents, and only the prior compact semantic pagination progress needed across pages. Pagination advancement SHALL additionally receive the current page state and the immediately preceding fresh observation after an action for transition comparison. The invocation-wide total timeout and shared operational-and-reasoning progress limits SHALL continue across all stages and pages. The configured maxima SHALL be inclusive under the existing stage completion and browser-action rules.

#### Scenario: A pagination iteration begins
- **WHEN** one page has completed retained-document collection and capture
- **THEN** page advancement starts with fresh action counters and history while receiving the compact cross-page pagination progress and captured-document count

#### Scenario: Pagination continues across stage-local limits
- **WHEN** multiple page-advance and per-page collection iterations complete within their individual limits
- **THEN** their stage-local counters reset between iterations while the invocation-wide timeout and progress accounting continue

#### Scenario: Page-advance work exceeds a stage limit
- **WHEN** one pagination-advance iteration requests work beyond an inclusive model-turn or browser-action maximum
- **THEN** the invocation fails without assembled or partial HTML

## ADDED Requirements

### Requirement: Composed paginated-document collection
The `paginated-documents` strategy SHALL run retained-document collection on the current result page, capture its complete visibility-filtered top-level document before replacement, and then run model-guided page advancement. It SHALL repeat in source order until semantic or natural completion. It SHALL preserve each whole captured boundary page, SHALL NOT filter individual records from a captured page, and SHALL NOT follow record-detail or expanded-reading links as pagination controls. It SHALL reject unchanged transitions and repeated collected page states rather than silently duplicate content.

#### Scenario: Multiple result pages are collected
- **WHEN** each result page has an enabled immediate next-page control and later pages may still satisfy the caller task
- **THEN** the service exhausts retained content on each page, captures it before replacement, advances exactly one result page, and repeats in order

#### Scenario: Boundary falls within a page
- **WHEN** a captured page contains both records that do and do not satisfy the semantic cutoff and later pages cannot contain relevant records
- **THEN** the service retains the whole captured boundary page and stops without advancing

#### Scenario: Record detail link is present
- **WHEN** a result record offers a detail, `Read more`, or equivalent non-pagination link
- **THEN** paginated collection does not follow that link as part of result-page traversal

#### Scenario: Pagination repeats or does not replace the page
- **WHEN** advancement reports continuation but produces an unchanged or previously collected page state
- **THEN** the invocation fails without assembled or partial HTML

### Requirement: Semantic pagination completion
The page-advance model SHALL interpret any semantic stopping condition from the original natural-language task without a site-specific cutoff parser. It SHALL maintain a compact cumulative progress summary for subsequent pages. It SHALL stop when evidence establishes that later pages cannot satisfy the caller task or when no enabled immediate next-page control remains. If the task supplies no explicit cutoff, the natural terminal page SHALL be the semantic default. When ordering, cutoff satisfaction, or next-page relevance is uncertain, it SHALL continue rather than claim completion.

#### Scenario: Caller supplies a semantic cutoff
- **WHEN** the current page and established result ordering show that later pages cannot satisfy the natural-language task
- **THEN** page advancement reports semantic completion without activating Next

#### Scenario: Caller supplies no explicit cutoff
- **WHEN** an enabled immediate next-page control remains and no task condition excludes later pages
- **THEN** pagination continues toward the natural terminal page

#### Scenario: Natural terminal page is reached
- **WHEN** no enabled immediate next-page control remains
- **THEN** page advancement reports completion and collection assembles the captured documents

#### Scenario: Relevance is uncertain
- **WHEN** the model cannot establish that later pages are outside the caller's requested scope
- **THEN** it advances to the immediate next result page instead of stopping

### Requirement: Hard paginated-document limit
The service SHALL enforce a configured positive maximum number of captured paginated documents independently of semantic completion. If page advancement establishes that another relevant or potentially relevant page remains after the maximum number has been captured, the invocation SHALL fail without assembled or partial HTML. Reaching semantic or natural completion on the maximum captured page SHALL succeed.

#### Scenario: Completion occurs at the hard limit
- **WHEN** the maximum permitted document has been captured and page advancement establishes semantic or natural completion
- **THEN** the service successfully assembles all captured documents

#### Scenario: Another page remains after the hard limit
- **WHEN** the maximum permitted document has been captured and page advancement continues to another potentially relevant page
- **THEN** the invocation fails with an execution-limit error and returns no HTML
