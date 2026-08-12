## Context

The existing reporter owns a shared buffer for model reasoning and operational statuses, but its item maximum is an invocation-wide counter and the application calls a flush operation that bypasses the delivery interval. The server now constructs the reporter from a FastMCP context, while tests still describe the older callback-based delivery contract. See `proposal.md` for motivation and the optional-agent-progress delta for the target behavior.

## Goals / Non-Goals

**Goals:**
- Make one reporter the sole authority for accepting, buffering, rate-limiting, batching, and best-effort delivery of progress.
- Preserve FIFO ordering across reasoning and status fragments while retaining undelivered fragments across batch boundaries.
- Expose an interval-respecting cleanup check that agent orchestration can safely invoke without knowing delivery state.
- Test the timing and batching behavior deterministically with a controllable monotonic clock and a fake FastMCP context.

**Non-Goals:**
- Introducing a background timer or waiting for the next permitted delivery time.
- Changing progress configuration names, model-streaming behavior, browser execution behavior, or Playwright tool validation.
- Delivering failures to application code, requeuing failed batches, or exposing delivery status to orchestration.

## Decisions

### Keep a single FIFO buffer and consume one eligible batch at a time

`accept()` will normalize non-blank fragments, append them to the shared buffer, then check whether delivery is currently permitted. The delivery operation will select the whole buffer for an unlimited maximum or its FIFO prefix for a positive maximum; retained items remain buffered for a later eligibility check. After a successful batch delivery, its timestamp becomes the rate-limit reference. This produces an effective upper bound of approximately `maximum_items / minimum_interval_seconds` for positive values without rejecting progress elsewhere in the invocation.

An invocation-wide accepted-item counter is removed because it conflicts with reusable batch capacity. Sending every retained batch in one call is rejected because deliveries after the first would violate the interval.

### Provide `flush_if_needed()` as the only application-facing flush operation

The reporter will expose `flush_if_needed()` and use the same eligibility logic for direct acceptance and cleanup checks. It returns without delivery when no fragments are buffered or a positive interval has not elapsed. `agent_loop.py` calls it after model turns and `browser_agent.py` calls it during cleanup; neither call site forces a flush or reads delivery state.

A force-flush API is rejected because it would let call sites violate the rate contract and recreate split delivery policy.

### Deliver directly through the FastMCP context and retain failures within the reporter

The reporter will call `Context.report_progress(progress=batch_size, message=batch_message)`. The selected batch is removed before the awaited call, and a reporting exception is caught and logged without blocking model or browser execution. Later accepted or buffered batches remain eligible for delivery, allowing recovery from transient reporting failures.

Requeuing failed batches for automatic retry is rejected because it can repeat stale reasoning and create an unbounded backlog. A later batch is attempted only when a future acceptance or interval-respecting flush checks delivery eligibility.

### Scope tests to progress behavior and its two orchestration call sites

Reasoning-progress tests will replace callback-based fakes with a context-shaped fake and assert batch size, messages, retained-order delivery, interval-respecting checks, zero-interval delivery, blank-fragment filtering, and non-fatal failure handling. Focused agent-loop and browser-agent tests will verify calls use `flush_if_needed()` without expanding unrelated browser behavior coverage.

## Risks / Trade-offs

- [No background scheduler means buffered items can remain pending until a later accept or cleanup check.] → The reporter checks on every accepted fragment and the existing model-turn and browser-agent cleanup boundaries invoke `flush_if_needed()`.
- [A failed delivery drops its selected batch while later deliveries remain eligible.] → This avoids replaying stale progress while allowing recovery from transient failures; repeated failures can produce repeated warnings.
- [One delivery may contain fewer than the configured maximum when it becomes eligible.] → The maximum is an upper batch bound, not a target size, which allows zero-interval immediate delivery.

## Migration Plan

1. Replace the existing invocation-wide counter and private/force flush behavior with the reporter-owned batch and eligibility logic.
2. Update the reporter construction and call sites to use FastMCP context delivery and `flush_if_needed()`.
3. Update the scoped unit tests and run the focused reasoning-progress, agent-loop, and browser-agent test modules.
4. Roll back by reverting the change if consumers require the prior cumulative-progress contract; no persisted data or configuration migration is needed.
