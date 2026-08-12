## Purpose

Configure and operate the render-and-strip MCP server and its local development infrastructure.
## Requirements
### Requirement: Validated runtime settings
The application SHALL load a top-level Pydantic settings model from an optional TOML configuration file and nested environment-variable overrides using `__` as the delimiter. Unknown settings SHALL be rejected. Fields with in-code defaults SHALL use them when not supplied; fields without defaults SHALL remain required and SHALL cause ordinary Pydantic validation failure when absent. Docker Compose MAY supply test-infrastructure values without making those values application defaults.

#### Scenario: TOML configuration is loaded
- **WHEN** the CLI receives a path to an existing TOML configuration file
- **THEN** the application validates and uses the settings from that file

#### Scenario: Configuration file is absent
- **WHEN** the CLI receives no configuration file or a path that does not exist
- **THEN** the application applies in-code defaults and environment values and either starts with a valid settings model or fails through Pydantic validation for missing required fields

### Requirement: External dependency configuration
The application SHALL configure the FastMCP HTTP bind settings, official Playwright MCP HTTP endpoint, LiteLLM model identifier, OpenAI-compatible API base URL, model credentials, maximum output tokens, per-stage model-turn and browser-action limits, invocation-wide run and cleanup limits, optional post-action settle grace, optional HTML byte limit, progress maximum items, progress minimum interval, and plain-HTTP permission through settings. The maximum output-token setting SHALL default to 1024, `run_timeout_seconds` to 3600 seconds, settle grace and cleanup timeout to 0 and 10 seconds respectively, and both existing progress settings SHALL default to `0`. The configured model-turn and browser-action limits SHALL apply independently and with the same configured values to each model-guided stage. The existing `reasoning_progress_max_items` and `reasoning_progress_min_interval_seconds` settings SHALL govern the shared operational-and-reasoning progress stream without a configuration-key migration. Application code SHALL NOT hardcode Docker Compose hostnames, ports, or model paths. The application SHALL NOT expose a maximum concurrent invocation setting. The application SHALL reject the retired `idle_timeout_seconds` key through strict settings validation.

#### Scenario: Non-Compose endpoint configuration
- **WHEN** a deployment supplies reachable compatible official Playwright MCP and model HTTP endpoints through settings
- **THEN** the application connects to those endpoints without application-code changes

#### Scenario: Per-stage agent limits are configured
- **WHEN** a deployment configures model-turn or browser-action limits
- **THEN** the application applies each configured limit independently to access, discovery, reconstruction, and collection while retaining one invocation-wide run timeout

#### Scenario: Run timeout is configured
- **WHEN** a deployment configures `run_timeout_seconds`
- **THEN** the application uses that value as the invocation-wide deadline and resets it immediately before browser closing

#### Scenario: Retired idle timeout is configured
- **WHEN** a deployment configures `idle_timeout_seconds`
- **THEN** settings validation rejects the unknown key instead of adapting it to the run timeout

#### Scenario: Optional settle grace is not configured
- **WHEN** a deployment does not configure `page_settle_seconds`
- **THEN** the application captures fresh post-action observations without adding an application-level fixed delay

#### Scenario: Existing progress settings are configured
- **WHEN** a deployment configures reasoning-progress maximum items or minimum interval
- **THEN** the application applies those values to the shared stream of operational milestones and model reasoning

### Requirement: Local infrastructure harness
The repository SHALL provide Docker Compose configuration for a pinned tested release of the official Playwright MCP image with its bundled headless Chromium, a llama.cpp model server, and a deterministic static test-site service launched with Python's built-in HTTP server. It SHALL NOT add a separate browser service. The Playwright MCP service launch command SHALL include `--isolated` and SHALL NOT include `--shared-browser-context`. The Compose configuration SHALL supply test endpoint/model values and expose HTTP connectivity required for the application while remaining separate from runtime application defaults. A dedicated llama.cpp model-image Dockerfile SHALL own the sole default model URL and SHA-256, verify every downloaded model, and require custom model URL and SHA-256 build-argument pairs.

#### Scenario: Local dependency stack starts
- **WHEN** a developer starts the documented Docker Compose dependency stack with required model configuration
- **THEN** Playwright MCP, llama.cpp, and the deterministic HTTP test site expose endpoints usable by the application and each MCP client session receives an isolated browser context

#### Scenario: Integration configuration accesses the HTTP fixture
- **WHEN** the Compose integration test invokes the application against the deterministic HTTP test site
- **THEN** its test configuration explicitly enables plain HTTP without changing the default runtime setting

#### Scenario: Default model image is built
- **WHEN** a developer builds the default llama.cpp Compose service
- **THEN** the dedicated model Dockerfile downloads its default model and verifies it against the Dockerfile's default SHA-256

#### Scenario: Custom model image is built
- **WHEN** a developer replaces the default model
- **THEN** they provide both `MODEL_URL` and `MODEL_SHA256` build arguments and the image verifies the downloaded model

### Requirement: Compose-backed development container
The repository SHALL provide a devcontainer configuration that uses the Compose application service, starts the Playwright MCP, llama.cpp, fixture, and application services, and forwards the application MCP port. The application service SHALL use internal dependency endpoints and keep its UV project environment outside the mounted workspace.

#### Scenario: Developer opens the devcontainer
- **WHEN** a developer opens the repository in a Dev Containers-compatible editor
- **THEN** the application and its supporting Compose services start and the application MCP endpoint is reachable through the forwarded port

### Requirement: Configurable request policy
The application SHALL reject plain-HTTP page URLs by default and allow them only when the plain-HTTP setting is enabled. It SHALL NOT impose an application-level limit on simultaneous browser-agent sessions.

#### Scenario: Default request policy
- **WHEN** plain-HTTP permission is not configured
- **THEN** plain-HTTP page URLs are rejected and the application does not queue browser-agent sessions behind an application-level concurrency cap

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
