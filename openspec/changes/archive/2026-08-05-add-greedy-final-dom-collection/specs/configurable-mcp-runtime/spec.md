## MODIFIED Requirements

### Requirement: External dependency configuration
The application SHALL configure the FastMCP HTTP bind settings, official Playwright MCP HTTP endpoint, LiteLLM model identifier, OpenAI-compatible API base URL, model credentials, maximum output tokens, per-stage model-turn and browser-action limits, invocation-wide execution and cleanup limits, optional post-action settle grace, optional HTML byte limit, progress maximum items, progress minimum interval, and plain-HTTP permission through settings. The maximum output-token setting SHALL default to 1024, settle grace and cleanup timeout SHALL default to 0 and 10 seconds respectively, and both existing progress settings SHALL default to `0`. The configured model-turn and browser-action limits SHALL apply independently and with the same configured values to each model-guided stage. The existing `reasoning_progress_max_items` and `reasoning_progress_min_interval_seconds` settings SHALL govern the shared operational-and-reasoning progress stream without a configuration-key migration. Application code SHALL NOT hardcode Docker Compose hostnames, ports, or model paths. The application SHALL NOT expose a maximum concurrent invocation setting.

#### Scenario: Non-Compose endpoint configuration
- **WHEN** a deployment supplies reachable compatible official Playwright MCP and model HTTP endpoints through settings
- **THEN** the application connects to those endpoints without application-code changes

#### Scenario: Per-stage agent limits are configured
- **WHEN** a deployment configures model-turn or browser-action limits
- **THEN** the application applies each configured limit independently to access, discovery, reconstruction, and collection while retaining one invocation-wide total timeout

#### Scenario: Optional settle grace is not configured
- **WHEN** a deployment does not configure `page_settle_seconds`
- **THEN** the application captures fresh post-action observations without adding an application-level fixed delay

#### Scenario: Existing progress settings are configured
- **WHEN** a deployment configures reasoning-progress maximum items or minimum interval
- **THEN** the application applies those values to the shared stream of operational milestones and model reasoning
