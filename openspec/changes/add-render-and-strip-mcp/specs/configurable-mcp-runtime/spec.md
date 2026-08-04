## ADDED Requirements

### Requirement: Validated runtime settings
The application SHALL load a top-level Pydantic settings model from an optional TOML configuration file and nested environment-variable overrides using `__` as the delimiter. Unknown settings SHALL be rejected. Fields with in-code defaults SHALL use them when not supplied; fields without defaults SHALL remain required and SHALL cause ordinary Pydantic validation failure when absent. Docker Compose MAY supply test-infrastructure values without making those values application defaults.

#### Scenario: TOML configuration is loaded
- **WHEN** the CLI receives a path to an existing TOML configuration file
- **THEN** the application validates and uses the settings from that file

#### Scenario: Configuration file is absent
- **WHEN** the CLI receives no configuration file or a path that does not exist
- **THEN** the application applies in-code defaults and environment values and either starts with a valid settings model or fails through Pydantic validation for missing required fields

### Requirement: External dependency configuration
The application SHALL configure the FastMCP HTTP bind settings, official Playwright MCP HTTP endpoint, LiteLLM model identifier, OpenAI-compatible API base URL, model credentials, maximum output tokens, execution and cleanup limits, optional HTML byte limit, reasoning-progress maximum items, reasoning-progress minimum interval, plain-HTTP permission, and maximum concurrent invocation limit through settings. The maximum output-token setting SHALL default to 1024, cleanup timeout SHALL default to 10 seconds, and both reasoning-progress settings SHALL default to `0`. Application code SHALL NOT hardcode Docker Compose hostnames, ports, or model paths.

#### Scenario: Non-Compose endpoint configuration
- **WHEN** a deployment supplies reachable compatible official Playwright MCP and model HTTP endpoints through settings
- **THEN** the application connects to those endpoints without application-code changes

### Requirement: Local infrastructure harness
The repository SHALL provide Docker Compose configuration for a pinned tested release of the official Playwright MCP image with its bundled headless Chromium, a llama.cpp model server, and a deterministic static test-site service launched with Python's built-in HTTP server. It SHALL NOT add a separate browser service. The Playwright MCP service launch command SHALL include `--isolated` and SHALL NOT include `--shared-browser-context`. The Compose configuration SHALL supply test endpoint/model values and expose HTTP connectivity required for the application while remaining separate from runtime application defaults.

#### Scenario: Local dependency stack starts
- **WHEN** a developer starts the documented Docker Compose dependency stack with required model configuration
- **THEN** Playwright MCP, llama.cpp, and the deterministic HTTP test site expose endpoints usable by the application and each MCP client session receives an isolated browser context

#### Scenario: Integration configuration accesses the HTTP fixture
- **WHEN** the Compose integration smoke test invokes the application against the deterministic HTTP test site
- **THEN** its test configuration explicitly enables plain HTTP without changing the default runtime setting

### Requirement: Configurable request policy
The application SHALL reject plain-HTTP page URLs by default and allow them only when the plain-HTTP setting is enabled. It SHALL support a maximum concurrent invocation setting where `0` means no application-imposed concurrency limit and a positive value limits simultaneous browser-agent sessions.

#### Scenario: Default request policy
- **WHEN** plain-HTTP permission and maximum concurrent invocations are not configured
- **THEN** plain-HTTP page URLs are rejected and the application imposes no concurrency cap

#### Scenario: Positive concurrency limit
- **WHEN** the maximum concurrent invocation setting is a positive value and that many browser-agent sessions are active
- **THEN** the server does not start another browser-agent session until a slot is available

### Requirement: Browser isolation deployment prerequisite
The README SHALL state that the application assumes the configured remote official Playwright MCP server uses isolated browser contexts and does not enable shared browser contexts. It SHALL identify the Compose configuration with `--isolated` and without `--shared-browser-context` as the tested setup.

#### Scenario: Developer configures an external Playwright MCP server
- **WHEN** a developer configures the application to use an external official Playwright MCP endpoint
- **THEN** the README identifies isolated, non-shared browser-context configuration as the required deployment prerequisite

### Requirement: Streamable HTTP server startup
The CLI SHALL load settings, configure application logging, and start the FastMCP server using Streamable HTTP transport.

#### Scenario: Server starts from configured settings
- **WHEN** the CLI is started with valid settings
- **THEN** it exposes the render-and-strip MCP tool over the configured Streamable HTTP endpoint
