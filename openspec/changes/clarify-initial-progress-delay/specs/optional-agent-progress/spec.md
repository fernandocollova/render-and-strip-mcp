## MODIFIED Requirements

### Requirement: Minimum reasoning progress interval
The server SHALL apply `reasoning_progress_min_interval_seconds` as the minimum time between
successful progress deliveries across operational milestones and model reasoning. A value of `0`
SHALL make each accepted non-empty fragment immediately eligible for delivery. A positive value
SHALL buffer accepted fragment text in arrival order and permit the first delivery only after the
minimum interval has elapsed from invocation start; each later delivery SHALL require the minimum
interval to have elapsed since the prior successful delivery. Progress checks after an inner model
turn or during outer invocation cleanup SHALL obey the same interval and SHALL NOT force a
delivery.

#### Scenario: Initial reasoning items arrive within the interval
- **WHEN** operational status and model reasoning are accepted before a positive minimum interval
  has elapsed from invocation start
- **THEN** the server retains and combines their clearly identified text in acceptance order until
  the first delivery is eligible

#### Scenario: Reasoning items arrive within the interval after delivery
- **WHEN** operational status and model reasoning are accepted before a positive minimum interval
  has elapsed since a successful progress delivery
- **THEN** the server retains and combines their clearly identified text in acceptance order until
  a later delivery is eligible

#### Scenario: Model turn ends before the interval elapses
- **WHEN** an inner model turn ends with buffered progress text before the positive minimum
  interval has elapsed
- **THEN** the server retains the buffered text and does not deliver it solely because the model
  turn ended

#### Scenario: Cleanup checks an eligible buffered batch
- **WHEN** cleanup checks buffered progress text after a positive minimum interval has elapsed
- **THEN** the server delivers the next ordered batch without bypassing the configured batch
  maximum
