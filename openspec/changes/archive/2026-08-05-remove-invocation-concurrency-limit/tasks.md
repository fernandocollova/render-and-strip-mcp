## 1. Remove Runtime Concurrency Control

- [x] 1.1 Remove the maximum-concurrent-invocations setting from the agent configuration and the example TOML file.
- [x] 1.2 Delete the invocation-gate module and remove its imports, construction, injection, and acquisition lifecycle from the server and browser agent.

## 2. Update Documentation And Tests

- [x] 2.1 Remove concurrency-limit guidance from the README and update affected test descriptions.
- [x] 2.2 Update configuration tests to remove the supported setting and verify strict rejection of the retired configuration key.
- [x] 2.3 Update browser-agent and session-control tests for direct invocation startup, removing semaphore-specific coverage while retaining cleanup and cancellation coverage.

## 3. Verify

- [x] 3.1 Run the unit test suite with `uv run pytest`.
- [x] 3.2 Run `openspec validate remove-invocation-concurrency-limit --strict`.
