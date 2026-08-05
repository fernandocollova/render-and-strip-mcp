## 1. Browser-Agent Prompt

- [x] 1.1 Update the fixed browser-agent system instruction to state that initial navigation is complete, direct current-page-only cleaning tasks to finish without a browser call, and retain tool use for tasks that require further action.
- [x] 1.2 Add or update focused model-context unit coverage to verify the internal guidance is present and the caller task remains verbatim in the user message.

## 2. Public-Request Regression Coverage

- [x] 2.1 Simplify the Compose end-to-end fixture request to use only a current-page cleaning task and retain its clean-HTML assertion.
- [x] 2.2 Run the relevant unit suite and Compose integration test to verify prompt construction and the no-caller-orchestration path.
