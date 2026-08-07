## Context

See `proposal.md`. The reporter initializes its delivery reference time at invocation start and
checks the configured interval whenever a fragment is accepted or a caller invokes a non-forcing
flush check.

## Goals / Non-Goals

**Goals:**
- Preserve a positive configured interval before the first delivery.
- Describe initial-batch timing unambiguously in the progress specification and deterministic
  tests.

**Non-Goals:**
- Changing progress batch limits, failure handling, or application call sites.
- Adding a timer or delaying browser execution while progress is buffered.

## Decisions

### Retain invocation-start time as the initial delivery reference

The reporter will continue to initialize the delivery timestamp to zero relative to its monotonic
clock. This applies a positive interval before the first delivery and each later delivery. Using an
absent timestamp would make the first batch immediately eligible and contradict the configured
initial delay.

### Test the observable first-batch delay through the fake clock

Progress tests will accumulate fragments before advancing the fake clock to the interval threshold,
then assert that the first batch contains the buffered FIFO fragments. This verifies the same
eligibility policy used by regular acceptance and cleanup checks.

## Risks / Trade-offs

- [Short invocations can finish before the first positive-interval delivery is eligible.] → This is
  intentional best-effort progress behavior; browser execution is never delayed to emit progress.
