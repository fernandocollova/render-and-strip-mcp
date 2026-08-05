## MODIFIED Requirements

### Requirement: External dependency configuration
The application SHALL configure the FastMCP HTTP bind settings, official Playwright MCP HTTP endpoint, LiteLLM model identifier, OpenAI-compatible API base URL, model credentials, maximum output tokens, execution and cleanup limits, optional HTML byte limit, reasoning-progress maximum items, reasoning-progress minimum interval, and plain-HTTP permission through settings. The maximum output-token setting SHALL default to 1024, cleanup timeout SHALL default to 10 seconds, and both reasoning-progress settings SHALL default to `0`. Application code SHALL NOT hardcode Docker Compose hostnames, ports, or model paths. The application SHALL NOT expose a maximum concurrent invocation setting.

#### Scenario: Non-Compose endpoint configuration
- **WHEN** a deployment supplies reachable compatible official Playwright MCP and model HTTP endpoints through settings
- **THEN** the application connects to those endpoints without application-code changes

### Requirement: Configurable request policy
The application SHALL reject plain-HTTP page URLs by default and allow them only when the plain-HTTP setting is enabled. It SHALL NOT impose an application-level limit on simultaneous browser-agent sessions.

#### Scenario: Default request policy
- **WHEN** plain-HTTP permission is not configured
- **THEN** plain-HTTP page URLs are rejected and the application does not queue browser-agent sessions behind an application-level concurrency cap
