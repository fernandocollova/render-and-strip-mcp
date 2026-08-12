## Context

One `asyncio.timeout()` currently bounds an entire model request, even if the model is actively
streaming reasoning. A second timeout is named as an idle timeout and is reset by an
`IdleAwareProgressReporter` wrapper, even though it is intended to bound the whole browser-agent
run. The reporter and timeout lifetimes differ: one reporter spans the invocation, while one model
timeout spans exactly one model turn.

## Goals / Non-Goals

**Goals:**
- Give each model turn a renewable inactivity deadline.
- Preserve a separately named run-wide deadline and renew it before browser closing.
- Keep progress batching and delivery independent from timeout renewal.
- Retain `asyncio.Timeout` lifecycle and exception behavior.

**Non-Goals:**
- Add a fixed maximum duration in addition to model inactivity timeout.
- Treat ordinary content or tool-call chunks as model activity.
- Change cleanup timeout/cancellation policy beyond granting the run deadline before close.
- Add background timers, retries, or a general timeout abstraction hierarchy.

## Decisions

### Wrap, do not subclass, `asyncio.Timeout`

`RenewableTimeout` owns one `asyncio.Timeout`, creates it during construction to preserve the
stdlib relative-deadline semantics, delegates asynchronous context entry and exit, and adds
`renew()`. Renewal calls `reschedule(loop.time() + configured_seconds)`, which resets rather than
extends the deadline. Subclassing is rejected because `asyncio.Timeout` is final and has a
stateful cancellation lifecycle.

### Bind a model timeout to reasoning acceptance for one turn

`StageRunner` creates `RenewableTimeout(model_request_timeout_seconds)` around each streamed model
turn. It supplies the active timeout only to the model reasoning callback. `ProgressReporter.accept`
normalizes the fragment first, then renews the supplied timeout for a non-blank fragment before
buffering or attempting delivery. This preserves existing meaningful-progress semantics while
ensuring interval coalescing and failed MCP progress delivery never control timeout renewal.

An invocation-wide idle-aware reporter is removed because its lifetime and responsibility do not
match a per-turn model deadline. Operational status accepts receive no timeout and therefore do
not extend a model request.

### Rename the outer deadline to a run timeout

`idle_timeout_seconds` becomes `run_timeout_seconds` with a 3600-second default. Browser-agent
execution uses it as the outer deadline and resets it immediately before browser closing, reserving
the configured run duration for close work after normal processing or a processing failure.

The retired key is not adapted: strict settings validation reports it clearly. Compatibility
fallbacks are rejected because application configuration is a controlled contract.

## Risks / Trade-offs

- [A provider can stream non-blank reasoning indefinitely.] → The model timeout intentionally
  measures inactivity; per-turn output-token settings remain in place. A hard duration cap is
  explicitly deferred.
- [A timeout that has already started expiring cannot be renewed.] → Cleanup-timeout/cancellation
  behavior is left to subsequent work rather than silently adapting timeout state.
- [Only reasoning fragments renew the model deadline.] → This matches current progress semantics;
  providers that stream only ordinary content or tool-call deltas retain the configured fixed
  model-request deadline.

## Migration Plan

1. Deploy configuration updates using `run_timeout_seconds` or
   `RENDER_AND_STRIP_MCP_AGENT__RUN_TIMEOUT_SECONDS`.
2. Remove uses of the retired idle-timeout key; invalid uses fail at startup.
3. Roll back by restoring the previous setting key and timeout wiring if deployments require the
   prior invocation-idle behavior. No persisted state requires migration.
