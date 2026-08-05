## Context

The server currently constructs one shared `InvocationGate` from the agent concurrency setting and passes it to every browser-agent invocation. Acquiring that gate occurs within the total-invocation timeout before a remote Playwright session is opened. The setting, implementation module, server wiring, configuration tests, example TOML, README, and current OpenSpec requirements all describe this behavior.

See `proposal.md` for the motivation and the accompanying specification deltas for the updated behavior contract.

## Goals / Non-Goals

**Goals:**
- Remove all application-level session queueing and the configuration that controls it.
- Simplify `BrowserAgent` construction so it owns only settings and optional progress reporting.
- Preserve existing invocation validation, time limits, browser isolation assumptions, cancellation behavior, and cleanup guarantees.
- Make the removed configuration fail strict configuration validation rather than silently changing behavior.

**Non-Goals:**
- Changing limits enforced by the remote Playwright MCP service, its browser process, or deployment infrastructure.
- Changing the number of browser contexts the remote service can host.
- Reworking any other request, model, browser-action, or output-size limits.

## Decisions

### Delete the gate rather than make it permanently unlimited

Remove the `InvocationGate` module, its shared server instance, and the browser-agent acquire/release lifecycle. No concurrency abstraction remains because the only supported configuration value is effectively unlimited.

Keeping the abstraction configured with an unlimited value would preserve unused dependency injection, lifecycle code, and tests without providing behavior.

### Retire the setting as a strict breaking configuration change

Remove `max_concurrent_invocations` from the validated agent settings and all documented examples. The existing `extra="forbid"` policy then rejects TOML and nested environment configuration that still supplies the removed key.

Retaining the setting as an ignored value was considered but rejected because it hides stale deployment policy and expands the long-term configuration surface.

### Keep the existing timeout and cleanup boundaries

Continue starting the total invocation timeout before request validation and keep browser cleanup outside that deadline in the cancellation-shielded `finally` path. Removing the queue means no time is spent waiting for an application-owned semaphore, but it does not change the lifetime of any remaining operation.

Moving the timeout or cleanup logic was considered but rejected because it is unrelated to concurrency removal and would increase behavioral risk.

## Risks / Trade-offs

- [A deployment relied on the local cap to protect remote browser capacity] -> The application will no longer throttle requests; operators must use deployment-level controls if capacity protection is required.
- [Stale TOML or nested environment configuration prevents startup] -> Strict validation exposes the removed setting with a clear validation error; remove the obsolete key during deployment updates.
- [Gate removal accidentally alters cleanup on failures or cancellation] -> Keep the existing session-manager and cleanup ordering intact and retain focused cancellation/cleanup tests.

## Migration Plan

1. Remove `max_concurrent_invocations` from TOML files and `RENDER_AND_STRIP_MCP_AGENT__MAX_CONCURRENT_INVOCATIONS` from deployment environments.
2. Deploy the simplified server; browser-agent invocations will no longer wait for an application-level slot.
3. If remote browser capacity becomes constrained, apply rate or concurrency controls at the deployment boundary rather than restoring an application setting.

Rollback consists of restoring the prior application release and, if needed, restoring the removed configuration key.
