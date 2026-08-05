## MODIFIED Requirements

### Requirement: Optional reasoning progress forwarding
The server SHALL forward model-generated LiteLLM `reasoning_content` and SHALL additionally emit operational progress milestones for initial navigation, access, discovery, reset, reconstruction, collection, and final extraction/cleaning. It SHALL identify operational messages as status rather than model reasoning and SHALL NOT synthesize reasoning text for orchestration work. Each non-empty normalized reasoning delta and each operational milestone SHALL be one progress item. Progress availability or item boundaries SHALL NOT determine stage completion, tool calls, or browser behavior.

#### Scenario: Provider emits reasoning text
- **WHEN** a streamed LiteLLM response contains reasoning-text fragments
- **THEN** the server emits those fragments as progress while continuing to process the model response

#### Scenario: Orchestration enters a pipeline operation
- **WHEN** the invocation begins initial navigation, access, discovery, reset, reconstruction, collection, or final extraction/cleaning
- **THEN** the server emits an operational status item through the same progress stream without presenting it as model reasoning

#### Scenario: Provider does not emit reasoning text
- **WHEN** the configured model emits no reasoning text during one or more stages
- **THEN** browser execution continues normally and operational milestones remain eligible for progress delivery

### Requirement: Invocation-wide reasoning item limit
The server SHALL support `reasoning_progress_max_items` as the maximum number of non-empty reasoning deltas and operational milestones accepted for progress across the complete outer MCP tool invocation. A value of `0` SHALL mean unlimited. Operational milestones and reasoning deltas SHALL consume the same allowance in acceptance order. After reaching a positive maximum, the server SHALL continue browser and model processing but SHALL not accept or emit later progress items.

#### Scenario: Reasoning item maximum is reached across turns
- **WHEN** accepted operational milestones and reasoning deltas reach a positive `reasoning_progress_max_items`
- **THEN** later milestones and reasoning deltas are not emitted and browser-agent execution continues normally

#### Scenario: Unlimited reasoning progress default
- **WHEN** `reasoning_progress_max_items` is `0`
- **THEN** the server does not impose an invocation-wide progress-item cap

### Requirement: Minimum reasoning progress interval
The server SHALL apply `reasoning_progress_min_interval_seconds` as a best-effort minimum interval across operational milestones and model reasoning. A value of `0` SHALL emit each accepted item immediately. A positive value SHALL buffer accepted item text in arrival order and coalesce it into the next notification after the interval. The server SHALL flush pending text at the end of an inner model turn and outer invocation even if that final flush occurs before the interval.

#### Scenario: Reasoning items arrive within the interval
- **WHEN** operational status and model reasoning are accepted before a positive minimum interval elapses
- **THEN** the server combines their clearly identified text in acceptance order into a later progress notification

#### Scenario: Model turn ends with buffered reasoning
- **WHEN** an inner model turn ends while accepted progress text remains buffered
- **THEN** the server flushes the pending text without delaying browser-agent execution

### Requirement: Progress notification semantics and failures
Each emitted progress notification SHALL report the cumulative number of accepted operational and reasoning items as `progress`, the configured positive maximum as `total` or no total when unlimited, and the coalesced progress text as `message`. Application orchestration SHALL NOT directly serialize checkpoint or stage-report fields into operational progress. Model-generated reasoning MAY refer to information available in its model context. If the caller does not support progress or notification delivery fails, the server SHALL log a warning, disable further progress notifications for that invocation, and continue browser-agent execution normally.

#### Scenario: Progress delivery fails
- **WHEN** reporting an operational or reasoning progress notification raises an error
- **THEN** the server suppresses further progress notifications without failing or changing the browser-agent invocation

#### Scenario: Reconstruction reasoning refers to checkpoint information
- **WHEN** the reconstruction model includes checkpoint information in its generated reasoning
- **THEN** the server forwards that reasoning under the same progress limits without separately serializing the checkpoint report
