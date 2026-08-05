## Context

The current service has one model-directed browser loop. Any no-tool model response ends that loop, older observations are discarded, and Python then extracts one visibility-filtered top-level DOM. This keeps the context compact but provides no trusted stage boundary, semantic reconstruction contract, or evidence that relevant reveal mechanisms were exhausted.

The pinned Playwright MCP session already provides the isolated browser context, same-origin enforcement, original-tab restoration, and final-document extraction needed by this change. The cleaner and public HTML-only return contract do not need multi-state aggregation because the only implemented strategy requires all collected content to coexist in the final DOM.

## Goals / Non-Goals

**Goals:**

- Make the control flow explicit and testable across access, discovery, reconstruction, and collection.
- Use model semantic judgment for arbitrary page controls while validating every model-produced handoff at the serialized boundary.
- Reconstruct a data-ready state without literal replay of stale browser references.
- Keep future strategy addition localized to a small dispatch boundary.
- Preserve current browser isolation, location safety, cleanup, HTML cleaning, rate-limited progress, and all-or-nothing output behavior.
- Define navigation and collection at the target page/view level; downstream callers, not this service, perform fine-grained extraction from the cleaned HTML.

**Non-Goals:**

- Accumulate numbered pages, mutually exclusive views, replaced content, or virtualized windows.
- Name or distinguish unsupported page mechanisms beyond `unknown`.
- Prove completeness through a generic deterministic DOM classifier.
- Infer generic network-idle or DOM-stability readiness for arbitrary pages.
- Clone or restore JavaScript heap state, browser contexts, or exact DOM snapshots.
- Add a public strategy argument, greedy opt-out, multi-document result, or partial result.
- Replay literal captured Playwright calls or persist access plans beyond one request.
- Extract requested facts, verify that particular facts survive semantic cleaning, or inspect the cleaned HTML with another model stage.

## Decisions

### Use four explicit model-guided stages

The browser agent will orchestrate this sequence inside its existing invocation-wide timeout and isolated session:

```text
initial navigation
  -> access and checkpoint
  -> discovery
  -> reset to caller URL
  -> checkpoint reconstruction
  -> retained-final-document collection
  -> final extraction and cleaning
```

Access establishes the semantic boundary between reaching the requested page/view state and broadly gathering its content. Discovery may mutate that state while probing. Reset always navigates the tracked original tab to the exact caller-supplied URL in the same browser context, preserving cookies and browser storage, and reconstruction uses the checkpoint to reach the data-ready state again.

This intentionally spends additional model calls and browser actions to keep collection strategies free from rollback and adaptive strategy-switching logic. Continuing directly from discovery was rejected because it couples probes to collection and makes each future strategy responsible for interpreting partially consumed state.

### Require local completion tools for typed stage handoffs

Each stage receives exactly one local completion function schema in addition to eligible remote browser tools. A generalized stage runner will distinguish local completion calls from remote calls, validate local arguments with strict Pydantic models, and return a typed stage result. Ordinary no-tool completion is an error.

The request-local models will be conceptually equivalent to:

```text
AccessCheckpoint
  target_state: non-empty string
  reconstruction_instructions: list of non-empty strings, possibly empty
  verification: non-empty list of non-empty strings

DiscoveryReport
  strategy: "retained-final-document" | "unknown"
  evidence: non-empty list of non-empty strings

ReconstructionReport
  verified: boolean
  evidence: non-empty list of non-empty strings

CollectionReport
  complete: boolean
  evidence: non-empty list of non-empty strings
```

Only a verified reconstruction and complete collection proceed. `unknown`, false reports, malformed reports, wrong completion tools, name collisions, and ordinary terminal responses raise domain-specific errors.

Local tools are preferable to terminal JSON because the configured model endpoint already guarantees function calling while provider-specific response formatting is intentionally unsupported. Free-form JSON would require recovering from prose or Markdown wrappers. The local reports are control data only and never become browser actions or public output.

### Minimize model-visible stage handoffs

Every stage receives the original caller task, its stage-specific system instructions, its own model-directed action log, and the current URL and fresh browser observation. Access receives no prior-stage result. Discovery starts from the data-ready state but does not receive the access checkpoint. Reconstruction alone receives the full access checkpoint. Collection receives the selected strategy through its strategy-specific prompt but does not receive the checkpoint, discovery evidence, or reconstruction evidence.

Initial and reset navigation are orchestration operations and are not represented as model-directed actions. Discovery and reconstruction evidence remains typed request-local control data rather than advice to later stages. This isolation prevents stale discovery observations from appearing to describe the reconstructed page, keeps context small, and limits checkpoint exposure. Collection intentionally rediscovers current controls after reconstruction.

### Keep semantic reconstruction separate from private action records

The access checkpoint stores a target page/view state, semantic instructions, and verification conditions. It does not store Playwright element references or assert that individual requested facts are present. Reconstruction receives the original task and checkpoint in a fresh stage context and rediscovers current controls.

Raw remote arguments may remain available transiently while an action executes, but the existing redacted action summaries remain the only action history sent to later turns or progress. No replay log is needed. Literal tool replay was rejected because snapshot targets, focus, loading state, and conditional controls are unstable after navigation.

### Use fresh post-action observations and semantic waits

The current remote action result can describe page state before asynchronous effects become observable. The service will promote the official `browser_snapshot` operation to a pinned required orchestration capability and reserve it from direct model use. After every successful model-directed browser action, orchestration will let the remote operation complete, apply the optional configured settle grace, restore the original tab, enforce the origin policy, and capture a fresh snapshot. The settle grace defaults to zero and is not treated as proof of readiness.

Initial navigation and reset navigation use the same fresh-state boundary before access and reconstruction respectively. The pinned official MCP operation performs its own bounded action/navigation completion behavior; application orchestration will not infer network idle, parse historical network output as active-request state, or require generic DOM stability. When a fresh observation shows a loading label, progress indicator, missing expected effect, or another semantic sign that page state is pending, the current model stage uses eligible browser waiting tools and then receives another fresh snapshot. A bounded time wait remains available when no semantic marker exists.

The stage runner will carry a small page-state value containing the current URL and fresh observation. Discovery and collection contexts following an action SHALL include the immediately preceding state alongside the current state and action summary. Access and reconstruction need only the current state. Older observation pairs remain discarded.

The model, not application code, decides whether page/view content was retained and whether expected action effects are ready for evaluation. The application validates the report schema and dispatches its result; it does not implement generic item matching, DOM differencing, network-idle inference, or post-clean semantic verification. If the evidence is ambiguous or too large for the model context, the request fails rather than weakening the context or guessing.

### Keep collection scoped to page-state retrieval

The caller task guides the browser to a target page, report, view, or filter state. It is not a fine-grained extraction query. Relevance means that an interaction exposes more content belonging to that target state, not that the revealed text contains particular requested facts. Completeness means operational exhaustion and retention of supported reveal mechanisms in the final top-level DOM before cleaning.

The existing semantic cleaner then applies its independent top-level-document, visibility, element, attribute, and size policies. This change does not verify that particular DOM values survive cleaning and does not inspect the cleaned result semantically. Downstream callers remain responsible for extracting and assessing individual facts from the returned HTML.

### Define operational rather than mathematical completeness

The discovery prompt will require an explicit inspection for apparent page/view reveal mechanisms. A static page may select the retained strategy without a mutating probe after an inspection finds no relevant mechanism. Apparent mechanisms are safely probed when needed to establish their behavior; there is no fixed probe count. A mechanism that is unsafe to probe, unprobeable, replacing, virtualized, mixed, or otherwise ambiguous produces `unknown`. Discovery evidence identifies what was inspected or probed and why retained behavior was or was not established.

The retained strategy prompt will require the model to inspect and exhaust relevant in-place mechanisms, request semantic waits when expected effects remain pending, preserve earlier content, and conduct a final verification sweep. Completion means that this sweep found no new target-view content, no unused relevant retained-document controls, no visible pending state, and no observed loss of prior target-view content.

This is an operational model judgment, not a proof about arbitrary website code. A generic browser cannot prove that no hidden future event exists. A source that continues producing content until a configured limit is therefore an error, as is a later contradiction of discovery's strategy selection.

### Dispatch strategies through plain functions

The collection coordinator will map the validated strategy literal to a concrete async collection function. This change supplies only `retained-final-document`; `unknown` has no handler and raises before reset. Future changes can add report literals and functions without introducing protocols, abstract classes, plugins, or changing access and reconstruction.

### Keep counters stage-local and the deadline invocation-wide

The generalized stage runner will initialize model-turn and model-directed browser-action counters for each stage. All four stages receive the same configured maxima independently. The configured maxima are inclusive: a valid local completion call may consume the final permitted model turn, and exactly the configured number of model-directed browser actions may execute subject to the turn allowance. An additional browser action is rejected before execution. If the final permitted model turn requests a browser action, the stage rejects it before execution because no turn would remain for mandatory completion. A local completion call consumes its model turn but not a browser action. Initial/reset navigation, orchestration snapshots, tab selection, URL checks, and final extraction do not consume model-directed browser-action allowance.

The existing outer timeout continues to cover validation, all stages, resets, settling, extraction, and cleaning. Reasoning-progress accounting also remains invocation-wide. This preserves simple phase behavior while bounding the request as a whole.

Each remote operation retains an independent existing deadline. Initial, reset, and model-directed navigation calls use the navigation timeout. Other model-directed browser calls, orchestration tab operations, URL evaluation, fresh snapshots, and final extraction each use the browser-action timeout independently. Optional settle grace uses its configured duration. These operation deadlines do not form one composite action deadline; the invocation-wide timeout bounds the complete sequence.

### Extend progress with operational milestones

The service will emit operational progress for initial navigation, access, discovery, reset, reconstruction, collection, and final extraction/cleaning. These messages are identified as operational status rather than model reasoning. They and streamed model-reasoning fragments share one invocation-wide item count, configured maximum, minimum delivery interval, ordered coalescing, and best-effort failure behavior. Operational items therefore consume the same configured allowance as reasoning items.

Application orchestration does not directly serialize checkpoint or stage-report fields into action logs, operational progress, or returned HTML. Model-generated reasoning remains forwarded under the shared progress policy and may refer to any information available in its model context, including checkpoint information during reconstruction.

### Preserve final-document extraction and public output

After a complete collection report, orchestration reselects the original tab, validates its final URL against the origin established by initial navigation, fetches the visibility-filtered top-level document, and runs the existing cleaner once. No discovery snapshot or model report contributes directly to HTML, and no post-clean model stage verifies individual facts. Every failure remains atomic and browser cleanup retains the existing primary-error precedence.

## Risks / Trade-offs

- **[Model misclassifies a page as retained]** -> Require explicit before/after evidence and a collection verification sweep; fail if collection observes a contradiction. The design accepts that semantic model judgment cannot provide formal proof.
- **[Reset does not recreate identical live data]** -> Verify the semantic target rather than exact DOM equality and keep reset in the same browser context. Fail if reconstruction cannot verify the checkpoint.
- **[Discovery causes server-side or storage side effects that navigation cannot undo]** -> Restrict discovery prompts to plausibly non-destructive data-reveal probes. The service cannot mechanically prove click safety on arbitrary external pages.
- **[Four stages multiply model and browser work]** -> Keep limits per stage and one total timeout. Extra work is an accepted trade-off for simpler strategy implementations.
- **[Fresh before/after observations exceed model context]** -> Preserve existing fail-without-truncation behavior rather than hiding evidence or returning incomplete HTML.
- **[Asynchronous content changes after a fresh snapshot]** -> Use the pinned MCP operation's bounded completion behavior, model-directed semantic waits, optional deployment grace, and final verification sweep; do not claim generic readiness proof.
- **[An endless additive feed never reaches completion]** -> Let stage or total limits fail the invocation and preserve the no-partial-result contract.
- **[Required browser snapshot capability tightens Playwright compatibility]** -> Pin and validate the schema against the already pinned official MCP release and fail before model execution on incompatible servers.
- **[Access instructions contain sensitive values]** -> Keep checkpoint data request-local, do not serialize report fields directly into logs or operational progress, and include the checkpoint only in trusted reconstruction model context; model reasoning may still refer to its context under the configured progress policy.

## Migration Plan

1. Add and validate the required official browser-snapshot capability and stage-completion schemas before enabling staged orchestration.
2. Replace the single loop with stage orchestration and the retained strategy in one release so the public tool never runs with an incomplete phase pipeline.
3. Update progress handling and documentation so operational milestones and model reasoning share the existing invocation-wide rate limits.
4. Update configuration documentation to explain that existing turn/action values apply independently per stage, settle grace defaults to zero, and the total timeout remains invocation-wide.
5. Update deterministic tests and fixtures before enabling the new greedy default.

Rollback consists of reverting the release. No persisted data or configuration-key migration is required, but rollback restores the previous non-greedy semantics for the same public tool signature.
