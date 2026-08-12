## Purpose

Optionally forward model reasoning as bounded, best-effort MCP progress notifications.
## Requirements
### Requirement: Optional reasoning progress forwarding
The server SHALL forward model-generated LiteLLM `reasoning_content` and SHALL additionally emit operational progress milestones for initial navigation, access, discovery, reset, reconstruction, collection, final extraction/cleaning, and browser closing. It SHALL identify operational messages as status rather than model reasoning and SHALL NOT synthesize reasoning text for orchestration work. Each non-empty normalized reasoning delta and each operational milestone SHALL be one progress fragment. Reasoning fragments and operational milestones SHALL enter one ordered progress buffer and be subject to the same delivery batch and interval policies. Progress availability, delivery failures, and fragment boundaries SHALL NOT determine stage completion, tool calls, or browser behavior. A model turn SHALL supply its active timeout only when accepting its own reasoning fragments; a non-empty accepted reasoning fragment SHALL renew that timeout before progress buffering or delivery, while operational milestones SHALL not renew a model-request timeout.

#### Scenario: Provider emits reasoning text
- **WHEN** a streamed LiteLLM response contains reasoning-text fragments
- **THEN** the server adds those fragments to the shared progress buffer, renews that turn's active model timeout, and continues to process the model response

#### Scenario: Orchestration enters a pipeline operation
- **WHEN** the invocation begins initial navigation, access, discovery, reset, reconstruction, collection, final extraction/cleaning, or browser closing
- **THEN** the server adds a labelled operational status fragment to the shared progress buffer without presenting it as model reasoning or renewing a model-request timeout

#### Scenario: Provider does not emit reasoning text
- **WHEN** the configured model emits no reasoning text during one or more stages
- **THEN** browser execution continues normally, operational milestones remain eligible for progress delivery, and the model timeout is not renewed by progress handling

#### Scenario: Provider emits blank reasoning text
- **WHEN** a streamed LiteLLM response contains an empty or whitespace-only reasoning fragment
- **THEN** the server does not renew the model timeout, add a progress fragment, or emit a progress delivery for it

### Requirement: Minimum reasoning progress interval
The server SHALL apply `reasoning_progress_min_interval_seconds` as the minimum time between successful progress deliveries across operational milestones and model reasoning. A value of `0` SHALL make each accepted non-empty fragment immediately eligible for delivery. A positive value SHALL buffer accepted fragment text in arrival order and permit delivery only when the minimum interval has elapsed since the prior successful delivery. Progress checks after an inner model turn or during outer invocation cleanup SHALL obey the same interval and SHALL NOT force a delivery.

#### Scenario: Reasoning items arrive within the interval
- **WHEN** operational status and model reasoning are accepted before a positive minimum interval elapses
- **THEN** the server retains and combines their clearly identified text in acceptance order until a later delivery is eligible

#### Scenario: Model turn ends before the interval elapses
- **WHEN** an inner model turn ends with buffered progress text before the positive minimum interval has elapsed
- **THEN** the server retains the buffered text and does not deliver it solely because the model turn ended

#### Scenario: Cleanup checks an eligible buffered batch
- **WHEN** cleanup checks buffered progress text after a positive minimum interval has elapsed
- **THEN** the server delivers the next ordered batch without bypassing the configured batch maximum

### Requirement: Progress notification semantics and failures
Each emitted progress notification SHALL report the number of fragments in that delivery batch as `progress` and the ordered, coalesced progress text as `message`. The server SHALL use the FastMCP progress-reporting context for delivery and SHALL NOT provide a cumulative total. Application orchestration SHALL NOT directly serialize checkpoint or stage-report fields into operational progress or determine whether a delivery was sent. If progress reporting is unavailable or delivery raises an error, the reporter SHALL handle the condition internally, log a warning, retain later progress deliveries as eligible, and continue browser-agent execution normally.

#### Scenario: An ordered progress batch is delivered
- **WHEN** a batch containing reasoning and operational fragments is eligible for delivery
- **THEN** the server reports the batch fragment count as `progress` and the newline-joined fragment text in buffer order as `message`

#### Scenario: Progress delivery fails
- **WHEN** reporting an operational or reasoning progress notification raises an error
- **THEN** the server logs the failure, continues the browser-agent invocation, and keeps later progress deliveries eligible

#### Scenario: Reconstruction reasoning refers to checkpoint information
- **WHEN** the reconstruction model includes checkpoint information in its generated reasoning
- **THEN** the server forwards that reasoning under the same progress batch and interval policies without separately serializing the checkpoint report

### Requirement: Per-delivery reasoning progress batch limit
The server SHALL support `reasoning_progress_max_items` as the maximum number of buffered reasoning fragments and operational milestones in one progress delivery. A positive maximum SHALL retain fragments beyond the delivery batch in their original buffer order for a later eligible delivery. A value of `0` SHALL mean that a delivery batch has no item limit. The configured maximum SHALL NOT impose an invocation-wide acceptance or delivery cap.

#### Scenario: A positive batch maximum is reached
- **WHEN** the shared buffer contains more fragments than a positive `reasoning_progress_max_items` value when delivery is eligible
- **THEN** the server delivers only the first configured number of fragments and retains the later fragments in order for a subsequent eligible delivery

#### Scenario: Multiple batches are delivered in one invocation
- **WHEN** an invocation accumulates and delivers more progress fragments over time than a positive `reasoning_progress_max_items` value
- **THEN** the server continues accepting and delivering later fragments in ordered batches while browser-agent execution continues normally

#### Scenario: Unlimited delivery batch
- **WHEN** `reasoning_progress_max_items` is `0`
- **THEN** the server delivers all buffered fragments when delivery is eligible
