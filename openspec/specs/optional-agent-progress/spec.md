## Purpose

Optionally forward model reasoning as bounded, best-effort MCP progress notifications.

## Requirements

### Requirement: Optional reasoning progress forwarding
The server SHALL treat each non-empty normalized LiteLLM `reasoning_content` delta as one optional reasoning-progress item. It SHALL forward accepted items as MCP progress messages and SHALL NOT use reasoning availability or item boundaries to determine agent completion, tool calls, or browser behavior.

#### Scenario: Provider emits reasoning text
- **WHEN** a streamed LiteLLM response contains reasoning-text fragments
- **THEN** the server emits those fragments as MCP progress while continuing to process the model response

#### Scenario: Provider does not emit reasoning text
- **WHEN** a streamed LiteLLM response contains no reasoning-text fragments
- **THEN** the browser agent continues normally and emits no reasoning progress messages

### Requirement: Invocation-wide reasoning item limit
The server SHALL support `reasoning_progress_max_items` as the maximum number of non-empty reasoning deltas accepted for progress across the complete outer MCP tool invocation, including all inner model turns. A value of `0` SHALL mean unlimited. After reaching a positive maximum, the server SHALL continue consuming the model stream but SHALL not accept or emit later reasoning deltas.

#### Scenario: Unlimited reasoning progress default
- **WHEN** `reasoning_progress_max_items` is `0`
- **THEN** the server does not impose an invocation-wide reasoning-item cap

#### Scenario: Reasoning item maximum is reached across turns
- **WHEN** accepted reasoning deltas across one or more inner model turns reach a positive `reasoning_progress_max_items`
- **THEN** later reasoning deltas are consumed but not forwarded and the browser-agent loop continues normally

### Requirement: Minimum reasoning progress interval
The server SHALL support `reasoning_progress_min_interval_seconds` as a best-effort minimum interval between ordinary progress notifications. A value of `0` SHALL emit each accepted reasoning item immediately. A positive value SHALL buffer accepted item text in arrival order and coalesce it into the next notification after the interval. The server SHALL flush pending text at the end of an inner model turn or outer invocation even if that final flush occurs before the interval.

#### Scenario: Reasoning items arrive within the interval
- **WHEN** multiple accepted reasoning items arrive before a positive minimum interval elapses
- **THEN** the server combines their text in order into a later progress notification

#### Scenario: Model turn ends with buffered reasoning
- **WHEN** an inner model turn ends while accepted reasoning text remains buffered
- **THEN** the server flushes the pending text without delaying browser-agent execution

### Requirement: Progress notification semantics and failures
Each emitted progress notification SHALL report the cumulative number of accepted reasoning items as `progress`, the configured positive maximum as `total` or no total when unlimited, and the coalesced reasoning text as `message`. If the caller does not support progress or notification delivery fails, the server SHALL log a warning, disable further progress notifications for that invocation, and continue browser-agent execution normally.

#### Scenario: Progress delivery fails
- **WHEN** reporting a reasoning progress notification raises an error
- **THEN** the server suppresses further progress notifications without failing or changing the browser-agent invocation
