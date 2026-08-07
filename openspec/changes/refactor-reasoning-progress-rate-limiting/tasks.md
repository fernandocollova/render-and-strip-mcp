## 1. Refactor reporter delivery policy

- [x] 1.1 Update `ReasoningProgressReporter` to buffer all non-blank reasoning and status fragments, remove the invocation-wide accepted-item counter, and use `maximum_items` only to select the next FIFO delivery batch.
- [x] 1.2 Implement reporter-owned interval eligibility and public `flush_if_needed()` so both accepted fragments and cleanup checks respect the minimum time between successful deliveries.
- [x] 1.3 Deliver batch-size progress and ordered batch text through the FastMCP context, keeping unavailable/failed delivery handling best-effort, non-fatal, internal to the reporter, and eligible for later delivery attempts.

## 2. Update progress integration call sites

- [x] 2.1 Confirm server construction supplies the FastMCP context to the reporter without exposing progress-delivery state to application code.
- [x] 2.2 Replace agent-loop post-turn and browser-agent cleanup calls with `flush_if_needed()` and remove use of private or force-flush APIs.

## 3. Cover and verify scoped behavior

- [x] 3.1 Update reasoning-progress tests with a fake FastMCP context to cover per-batch limits, retained FIFO batches, interval-respecting cleanup checks, zero-interval delivery, mixed status/reasoning order, blank fragments, batch-size payloads, and non-fatal delivery failures.
- [x] 3.2 Add or update focused agent-loop and browser-agent tests that verify the public interval-respecting flush call is used at their existing lifecycle boundaries.
- [x] 3.3 Run the focused reasoning-progress, agent-loop, and browser-agent test modules; report any remaining failures without changing Playwright validation tests.
