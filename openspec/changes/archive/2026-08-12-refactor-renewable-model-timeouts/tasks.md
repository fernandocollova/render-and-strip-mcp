## 1. Renewable timeout support

- [x] 1.1 Add `RenewableTimeout` with delegated asyncio context-manager behavior and renewal from
  its configured relative duration.
- [x] 1.2 Test deadline replacement, timeout conversion, and invalid pre-entry renewal behavior.

## 2. Timeout and progress integration

- [x] 2.1 Apply a renewable timeout to each streamed model turn and renew it through the reasoning
  callback only for non-blank fragments.
- [x] 2.2 Remove the idle-aware reporter wrapper, add an optional model timeout to progress
  acceptance, and retain existing progress buffering and delivery behavior.
- [x] 2.3 Rename the invocation setting to `run_timeout_seconds` and renew its deadline before
  browser closing.

## 3. Validate the migration

- [x] 3.1 Update configuration, progress, agent-loop, browser-agent, server, and documentation
  coverage for the renamed setting and timeout behavior.
- [x] 3.2 Run linting, formatting, and the complete test suite.
