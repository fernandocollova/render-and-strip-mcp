## Context

`run_stage` currently receives session-stable dependencies on every call and declares the state of each stage run as separate local variables. See `proposal.md` for motivation. The browser agent invokes it for access, discovery, reconstruction, and collection, while collection strategy code invokes it for the selected collection mechanism.

## Goals / Non-Goals

**Goals:**

- Bind session-stable dependencies once in a `StageRunner` instance.
- Make per-stage state explicit and guarantee it is newly initialized for each run.
- Preserve current control flow, limits, model context, reports, and exception behavior.

**Non-Goals:**

- Change stage prompts, tool schemas, or model-streaming behavior.
- Persist or share run state across stages.
- Alter public MCP behavior or configuration.

## Decisions

### Use a `StageRunner` class for stable dependencies

The class constructor will receive LLM settings, agent settings, the tool catalog, browser-action executor, and required progress reporter. Its `run` method will receive only stage-varying inputs: completion tool, task, initial state, checkpoint, and strategy.

This represents the existing browser-session lifetime and eliminates repeated dependency wiring. Retaining a free function plus a partially-applied callable would be less explicit and would not make the lifecycle clear at call sites.

### Represent each invocation with a mutable `StageRunState` dataclass

`StageRunState` will be constructed at the beginning of `StageRunner.run` from the supplied initial state. It will hold the action log, current state, preceding state, and browser-action count.

Keeping this state as a local variable in `run`, rather than an attribute of `StageRunner`, preserves stage isolation and makes the runner safe to reuse sequentially or concurrently. Leaving four independent local variables would remain valid, but would not make the requested per-run state boundary explicit.

### Update direct callers and tests

Callers will construct one runner per browser session or collection invocation and call `run` for each stage. Tests will instantiate the runner and continue exercising the same success, context, limit, and progress-reporting paths.

### Require the model reasoning sink

The server always creates a progress reporter, `BrowserAgent` always passes it to `StageRunner`, and `StageRunner` is the only application caller of `stream_model_turn`. Both the runner reporter and stream reasoning callback will therefore be required, eliminating branches that cannot execute in the application. Tests that call lower-level streaming directly will supply an explicit sink.

### Represent stage-specific context with classes

A shared `Stage` base class will build the task, action history, URL, and current observation portions of every model request. `AccessStage`, `DiscoveryStage`, `ReconstructionStage`, and `CollectionStage` will each own their stage identity, system prompt, and completion tool. Reconstruction and collection will require their checkpoint and strategy in their constructors, while discovery and collection opt into preceding-state context. `CompletionTool` retains only the model-facing function name and report parser because stage identity no longer belongs to the tool-routing contract.

This removes stage-name branching and optional checkpoint/strategy arguments from message construction. The generic report typing refinement remains out of scope for this step; `StageRunResult.report` retains its current report union.

## Risks / Trade-offs

- A runner could accidentally retain mutable stage data between calls → `StageRunState` is created inside `run` and no such data is stored on `StageRunner`.
- A new construction step can marginally increase call-site setup → it removes repeated stable dependency arguments and matches the session lifecycle.
- Refactoring can subtly alter control flow → retain the existing loop and branch ordering, and run the focused unit tests.
- Requiring an internal callback could affect direct unit callers → update them to pass an explicit no-op or recording sink.
- Four stage classes add names and objects → keep common formatting in the base class and limit subclasses to stage-specific declarations and context.
