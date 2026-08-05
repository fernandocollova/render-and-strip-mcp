## Purpose

Ensure requests broadly reveal content belonging to a target page or view that can coexist in one final rendered document, while failing when supported reveal mechanisms cannot be operationally exhausted or retained. Fine-grained extraction and assessment of individual facts remain downstream caller responsibilities.

## ADDED Requirements

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
The service SHALL run a model-guided discovery stage from the data-ready state and SHALL provide fresh page observations from before and after discovery probes. Discovery SHALL explicitly inspect for apparent reveal mechanisms and SHALL return exactly one of `retained-final-document` or `unknown` through a validated completion report. It MAY select `retained-final-document` for a static page without a mutating probe when inspection finds no relevant reveal mechanism. Where behavior must be established, it SHALL safely probe apparent mechanisms without a fixed required probe count. It SHALL select `retained-final-document` only when it determines that content belonging to the target page/view can be exposed and remain simultaneously present in the visibility-filtered final top-level document. It SHALL classify every unsafe-to-probe, unprobeable, unproven, ambiguous, replacing, virtualized, mixed, or otherwise unsupported behavior as `unknown` without requiring a more specific unsupported category. Its evidence SHALL identify what was inspected or probed and why retained behavior was or was not established.

#### Scenario: Static content is already retained
- **WHEN** the target page/view content is already present throughout the rendered document and explicit inspection finds no additional relevant reveal mechanism
- **THEN** discovery selects `retained-final-document`

#### Scenario: Probe appends and retains relevant content
- **WHEN** a discovery probe reveals additional relevant content while preserving previously revealed relevant content in the visible top-level document
- **THEN** discovery may select `retained-final-document` after it establishes that the applicable reveal mechanisms have retained-document behavior

#### Scenario: Finite incremental scrolling retains relevant content
- **WHEN** discovery and retained-document collection use incremental scrolling that reveals a finite amount of additional target-view content while preserving earlier visible content
- **THEN** discovery selects `retained-final-document`, collection reaches the observed end, and final extraction includes the retained revealed content

#### Scenario: Discovery cannot establish retained-document behavior
- **WHEN** discovery observes or cannot rule out behavior that removes, replaces, virtualizes, or otherwise prevents relevant content from coexisting in the final document
- **THEN** discovery reports `unknown`

#### Scenario: Numbered pagination replaces the current document view
- **WHEN** discovery observes numbered-page navigation whose next-page action replaces the current target-view document rather than retaining prior-page content
- **THEN** discovery reports `unknown`

#### Scenario: Discovery report is malformed
- **WHEN** the discovery model stops without the required completion report or supplies an unsupported strategy value or malformed report
- **THEN** the invocation fails without reconstruction, collection, or HTML output

### Requirement: Unsupported discovery fails before collection
The service SHALL implement only the `retained-final-document` collection strategy in this change. An `unknown` discovery result SHALL fail the invocation before reset, reconstruction, collection, or final-document extraction, and the service SHALL NOT return the current page as a partial result.

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
Access, discovery, reconstruction, and collection SHALL each use a fresh stage-local model-action history and separate configured model-turn and model-directed browser-action counters. Access and discovery SHALL receive no prior-stage report, reconstruction SHALL receive the full access checkpoint, and collection SHALL receive the selected strategy without the checkpoint or prior report evidence. The invocation-wide total timeout and shared operational-and-reasoning progress limits SHALL continue across all stages. The configured maxima SHALL be inclusive: valid local completion MAY occur on the final permitted model turn, and an action beyond the browser-action maximum SHALL fail before execution. A browser action requested on the final permitted model turn SHALL also fail before execution because no turn remains for mandatory completion. Initial navigation, reset navigation, tab restoration, location validation, fresh observation capture, local completion calls, and final extraction SHALL remain outside the model-directed browser-action counters while remaining inside the total timeout.

#### Scenario: One stage consumes its action allowance
- **WHEN** a stage requests work beyond its inclusive model-turn or browser-action allowance
- **THEN** the invocation fails even if another stage used fewer turns or actions

#### Scenario: A new stage begins
- **WHEN** the preceding stage completed within its limits
- **THEN** the new stage receives fresh model-turn and browser-action counters without resetting the invocation-wide timeout or shared progress accounting

#### Scenario: Collection begins after reconstruction
- **WHEN** reconstruction verifies the access checkpoint and retained-document collection begins
- **THEN** collection receives the original task, selected strategy, current page state, and a fresh action history without checkpoint fields or prior-stage evidence
