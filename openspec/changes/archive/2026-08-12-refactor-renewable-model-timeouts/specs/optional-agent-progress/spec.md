## MODIFIED Requirements

### Requirement: Optional reasoning progress forwarding
The server SHALL forward model-generated LiteLLM `reasoning_content` and SHALL additionally emit operational progress milestones for initial navigation, access, discovery, reset, reconstruction, collection, final extraction/cleaning, and browser closing. It SHALL identify operational messages as status rather than model reasoning and SHALL NOT synthesize reasoning text for orchestration work. Each non-empty normalized reasoning delta and each operational milestone SHALL be one progress fragment. Reasoning fragments and operational milestones SHALL enter one ordered progress buffer and be subject to the same delivery batch and interval policies. Progress availability, delivery failures, and fragment boundaries SHALL NOT determine stage completion, tool calls, or browser behavior. A model turn SHALL supply its active timeout only when accepting its own reasoning fragments; a non-empty accepted reasoning fragment SHALL renew that timeout before progress buffering or delivery, while operational milestones SHALL not renew a model-request timeout.

#### Scenario: Provider emits reasoning text
- **WHEN** a streamed LiteLLM response contains reasoning-text fragments
- **THEN** the server adds those fragments to the shared progress buffer, renews that turn's active model timeout, and continues to process the model response

#### Scenario: Orchestration enters a pipeline operation
- **WHEN** the invocation begins initial navigation, access, discovery, reset, reconstruction, collection, final extraction/cleaning, or browser closing
- **THEN** the server adds a labelled operational status fragment to the shared progress buffer without presenting it as model reasoning or renewing a model-request timeout

#### Scenario: Provider does not emit reasoning text
- **WHEN** the configured model emits no reasoning text during one or more stages
- **THEN** browser execution continues normally, operational milestones remain eligible for progress delivery, and the model timeout is not renewed by progress handling

#### Scenario: Provider emits blank reasoning text
- **WHEN** a streamed LiteLLM response contains an empty or whitespace-only reasoning fragment
- **THEN** the server does not renew the model timeout, add a progress fragment, or emit a progress delivery for it
