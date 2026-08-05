## Context

The service navigates to the caller-supplied URL before it constructs the first model turn. Its current fixed system message tells the model to complete the caller's task using Playwright tools, while the caller task is passed verbatim as user-message content. The Compose integration test compensates by embedding page-loaded and no-tool instructions in that public task. See proposal.md for motivation and the `browser-guided-page-rendering` delta for the required behavior.

## Goals / Non-Goals

**Goals:**
- Move initial-page-ready and current-page-cleaning guidance into the system-controlled model instruction.
- Preserve verbatim caller task content and existing model-directed actions for tasks that need them.
- Demonstrate the public request no longer includes MCP execution details.

**Non-Goals:**
- Add a task classifier, new public tool parameter, or configuration setting.
- Block all model browser tools after initial navigation.
- Change navigation, extraction, HTML-cleaning, or result behavior.

## Decisions

### Extend the fixed browser-agent system message

Add concise instructions that the service has already loaded the requested page, that a task solely asking to clean the current page must complete without a browser call, and that tools remain available when required by a different caller task. The system message is the appropriate trust boundary because the MCP implementation owns the navigation state and is supplied independently of caller-controlled text.

Keeping the guidance in the caller task was rejected because it exposes orchestration details and relies on every client to know the server's execution sequence. Adding a task parser or separate execution-mode argument was rejected because prompt guidance is sufficient for the narrowly defined model behavior and avoids expanding the public API.

### Retain the existing fresh two-message context shape

Continue placing the original task, current URL, action log, and browser observation in the user message. This preserves the compact-context requirement and lets the model use current state for interaction tasks without copying browser state into the caller's request.

### Test instruction placement at both levels

Add a focused unit assertion that generated model messages contain the loaded-page/current-page-cleaning guidance while retaining the task verbatim. Update the Compose end-to-end test to submit only a plain current-page cleaning task and verify its existing clean-HTML result, proving the caller no longer provides internal instructions.

## Risks / Trade-offs

- [A model may still call a tool despite prompt guidance] → Keep the instruction explicit and use the configured deterministic model settings; the focused prompt test and end-to-end fixture catch regressions for the supported path.
- [Guidance could suppress a needed action] → Scope the no-tool direction to tasks that only request cleaning the already loaded current page and explicitly retain tool use for interaction or navigation tasks.

## Migration Plan

Deploy the prompt and test update together. Existing callers remain compatible because the public tool signature and caller task text are unchanged; callers may remove redundant loaded-page/no-tool wording at their discretion. Roll back by restoring the prior system instruction if the configured model does not follow the scoped guidance reliably.
