## 1. Stage Runner Refactor

- [x] 1.1 Add a `StageRunState` dataclass for fresh per-stage action history, page state, and action-count state.
- [x] 1.2 Replace the `run_stage` free function with a dependency-bound `StageRunner.run` method while preserving stage execution behavior.

## 2. Integration And Verification

- [x] 2.1 Update browser-agent, collection-strategy, and unit-test callers to construct and use `StageRunner`.
- [x] 2.2 Run focused unit tests and OpenSpec validation, then record completed tasks.

## 3. Required Progress Dependencies

- [x] 3.1 Require the stage-runner reporter and model-stream reasoning sink, updating application and test callers.
- [x] 3.2 Audit remaining optional values and retain only those representing genuine lifecycle, protocol, or stage-specific absence.
- [x] 3.3 Run full verification after the required-dependency update.

## 4. Stage-Specific Context Classes

- [x] 4.1 Add a shared stage base class and concrete access, discovery, reconstruction, and collection classes.
- [x] 4.2 Update the runner and orchestration to pass stage objects instead of completion tools and optional stage context.
- [x] 4.3 Update tests and run full verification for the stage-class refactor.

## 5. Stage Identity Ownership

- [x] 5.1 Remove duplicated stage identity from completion tools and make concrete stages own it.
- [x] 5.2 Run full verification after updating stage identity ownership.
