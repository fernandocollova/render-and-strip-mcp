# greedy-page-content-collection Specification

## Purpose
Ensure requests broadly reveal content belonging to a target page or view that can coexist in one final rendered document, while failing when supported reveal mechanisms cannot be operationally exhausted or retained. Fine-grained extraction and assessment of individual facts remain downstream caller responsibilities.
## Requirements
### Requirement: Semantic access checkpoint
After initial navigation and a fresh orchestration-owned observation, the service SHALL run a model-guided access stage that reaches the caller's target page, report, view, or filter state. The stage SHALL complete only by submitting a validated semantic checkpoint containing a non-empty target-state description, reconstruction instructions, and one or more semantic verification conditions for that page/view state. It SHALL NOT treat the caller task as a request to extract or verify individual facts. Reconstruction instructions MAY be empty when the initial rendered page is already the target state. The checkpoint SHALL remain request-local. Application orchestration SHALL NOT directly add checkpoint fields to returned HTML, deterministic logs, or operational progress; model-generated reasoning MAY refer to checkpoint information available in its model context under the shared progress policy.

#### Scenario: Access interactions reach the target page or view
- **WHEN** the target page/view requires navigation, filters, or other preliminary browser interactions
- **THEN** the access stage reaches that page/view state and records semantic reconstruction instructions and verification conditions without storing browser element references as the reconstruction contract

#### Scenario: Initial page is already data-ready
- **WHEN** the initially rendered page already presents the target page/view state at its initial position
- **THEN** the access stage records a checkpoint with no reconstruction instructions and with conditions that identify that state

#### Scenario: Access stage does not produce a valid checkpoint
- **WHEN** the access model stops without the required completion report or supplies a malformed checkpoint
- **THEN** the invocation fails without strategy discovery or HTML output

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

#### Scenario: Numbered pagination replaces the current document view
- **WHEN** discovery establishes that an immediate next-page action replaces the current same-origin target-result document and that each page supports retained-document collection
- **THEN** discovery selects `paginated-documents`

#### Scenario: Discovery cannot establish retained-document behavior
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

### Requirement: Semantic checkpoint reconstruction
After successful strategy discovery, the service SHALL navigate the tracked original tab to the caller's original URL in the same isolated browser context, apply any configured settle grace, restore and validate that tab, and capture a fresh orchestration-owned observation. It SHALL then run a fresh model-guided reconstruction stage using the original task and validated checkpoint, rediscovering current controls rather than replaying captured browser references. Reconstruction SHALL complete only with an explicit validated report that the checkpoint verification conditions hold and no semantic pending state remains. Discovery actions and observations SHALL NOT be represented as actions already applied to the reset page.

#### Scenario: Data state is reconstructed through semantic steps
- **WHEN** the data-ready state is not fully represented by its URL
- **THEN** the reconstruction model follows the semantic instructions, adapts to the newly rendered controls, and verifies the target state before collection

#### Scenario: No access interactions need replay
- **WHEN** the checkpoint has no reconstruction instructions
- **THEN** reconstruction verifies the target state after navigation without inventing access steps

#### Scenario: Reconstruction cannot verify the target state
- **WHEN** the reconstruction model reports failure, stops without a valid completion report, or cannot satisfy every checkpoint verification condition within its limits
- **THEN** the invocation fails without collection or HTML output

### Requirement: Greedy retained-final-document collection
The `retained-final-document` strategy SHALL run a model-guided collection stage that exhausts non-destructive in-place reveal mechanisms belonging to the target page/view, including incremental scrolling or lazy loading, additive load-more controls, content-expansion controls, and disclosures that can remain open simultaneously. Collection SHALL request eligible semantic waits when a fresh observation shows a loading indicator, a missing expected action effect, or another pending state. It SHALL preserve previously revealed target-view content and SHALL complete only after a final verification sweep finds no new target-view content, no unused relevant retained-document reveal control, no visible pending state, and no loss of previously revealed target-view content. On successful completion, the service SHALL extract the visibility-filtered final top-level document once and apply the existing semantic HTML policy without post-clean semantic validation. The cleaner MAY intentionally omit retained DOM content according to its existing policy; assessment of individual returned facts belongs to the downstream caller.

#### Scenario: Additive content is exhausted
- **WHEN** scrolling or an additive control repeatedly reveals relevant content and eventually reaches a stable end
- **THEN** collection continues through the end, verifies that earlier content remains visible in the final DOM, and returns that DOM cleaned according to the existing semantic HTML policy

#### Scenario: Retainable expansions are opened
- **WHEN** relevant collapsed sections or expandable records can remain open simultaneously
- **THEN** collection opens the relevant expansions and leaves them open for final extraction

#### Scenario: Collection reveals unsupported behavior
- **WHEN** collection cannot preserve earlier relevant content or otherwise contradicts the selected retained-document strategy
- **THEN** the invocation fails without returning partial HTML

#### Scenario: Append-only source has no finite observed end
- **WHEN** collection continues finding new relevant content until a model-turn, browser-action, or total-time limit is reached
- **THEN** the invocation fails without extracting or returning partial HTML

### Requirement: Explicit model-stage completion
Each model-guided stage SHALL expose a stage-specific local completion tool with a validated argument schema alongside its eligible browser tools. The service SHALL route that tool locally, SHALL reject name collisions with remote tools, and SHALL NOT count it as a browser action. A stage SHALL fail when the model returns ordinary terminal text without calling its required completion tool, calls another stage's completion tool, or supplies invalid completion arguments.

#### Scenario: Stage submits a valid completion report
- **WHEN** the model calls the completion tool for its current stage with arguments satisfying that stage's schema
- **THEN** the service terminates the stage with the validated report without invoking a remote browser tool

#### Scenario: Model stops without explicit stage completion
- **WHEN** a stage model returns ordinary terminal content without its required completion-tool call
- **THEN** the invocation fails rather than treating the stage as successfully complete

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

#### Scenario: One stage consumes its action allowance
- **WHEN** a stage requests work beyond its inclusive model-turn or browser-action allowance
- **THEN** the invocation fails even if another stage used fewer turns or actions

#### Scenario: A new stage begins
- **WHEN** the preceding stage completed within its limits
- **THEN** the new stage receives fresh model-turn and browser-action counters without resetting the invocation-wide timeout or shared progress accounting

#### Scenario: Collection begins after reconstruction
- **WHEN** reconstruction verifies the access checkpoint and collection begins
- **THEN** collection receives the original task, selected strategy, current page state, and a fresh action history without checkpoint fields or prior-stage evidence

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
