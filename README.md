# Render and Strip MCP

`render-and-strip-mcp` is a Streamable HTTP MCP server with one tool:

```text
render_and_strip_page(url, task) -> clean semantic HTML
```

For each request it opens a fresh isolated session with an official Playwright MCP server, lets a
tool-calling model carry out the task, validates the final top-level origin, and returns only a
cleaned HTML document. Failures are MCP tool errors; partial HTML is never returned.

## Requirements

- Python 3.11–3.14 and [uv](https://docs.astral.sh/uv/).
- A reachable **official Playwright MCP** Streamable HTTP endpoint. It must run with `--isolated`
  and **without** `--shared-browser-context`. The Compose deployment below is the tested setup.
- An OpenAI-compatible chat endpoint accepted by LiteLLM. Its model must support streamed chat
  function tools, `tool_choice="auto"`, sequential tool calls, `temperature=0`, and `max_tokens`.
  Provider reasoning output is optional and is never sent as a model request parameter.

Install the application and development tools:

```bash
uv sync --group dev
```

## Configuration

Copy and adapt [`examples/render-and-strip.toml`](examples/render-and-strip.toml), then run:

```bash
uv run render-and-strip-mcp path/to/render-and-strip.toml
```

The server listens on `127.0.0.1:8000` by default and uses FastMCP's Streamable HTTP endpoint at
`/mcp`. The configuration file is optional. Without one, required Playwright and LLM values must
come from nested environment variables, for example:

```bash
export RENDER_AND_STRIP_MCP_PLAYWRIGHT_MCP__ENDPOINT=https://playwright-mcp.example/mcp
export RENDER_AND_STRIP_MCP_LLM__MODEL=openai-compatible/model-name
export RENDER_AND_STRIP_MCP_LLM__API_BASE=https://model.example/v1
export RENDER_AND_STRIP_MCP_LLM__API_KEY=replace-with-a-secret
uv run render-and-strip-mcp
```

TOML values are constructor inputs and take precedence over environment values. If a deployment
uses TOML, maintain overrides in that TOML file rather than expecting environment values to replace
it.

### Request and output policy

- `allow_plain_http` defaults to `false`; only HTTPS initial URLs are accepted by default. Enable
  it only for trusted local HTTP fixtures.
- `max_concurrent_invocations = 0` is unlimited. A positive value bounds active isolated browser
  sessions.
- Default execution limits are 12 model turns, 30 browser actions, 600 total seconds, 20
  navigation seconds, 15 action seconds, 90 model-request seconds, a 2-second settle delay, and
  10 cleanup seconds.
- `max_html_bytes = 0` permits unlimited clean HTML. A positive overage is an error, not a
  truncation.
- Optional reasoning progress uses `reasoning_progress_max_items = 0` and
  `reasoning_progress_min_interval_seconds = 0` for unlimited, immediate forwarding. Reasoning is
  reported only when the provider streams `reasoning_content` and the MCP caller accepts progress.

## Tested local dependency stack

[`docker-compose.yml`](docker-compose.yml) is the tested dependency configuration. It starts:

- the pinned official Playwright MCP image with bundled headless Chromium, `--isolated`, and no
  shared browser context;
- a pinned llama.cpp OpenAI-compatible server; and
- a deterministic static HTTP fixture served by `python -m http.server`.

Building the llama.cpp service downloads the default 398 MB Qwen2.5-0.5B-Instruct Q4_K_M GGUF
model. The Dockerfile verifies its SHA-256 before embedding it in the image. The default is small
enough for local CPU testing, though a larger tool-capable model is often better for real
browser tasks.

```bash
docker compose up -d --wait
uv run render-and-strip-mcp examples/compose.toml
```

The Dockerfile is the sole source of the default `MODEL_URL` and `MODEL_SHA256`. To change the
model, set **both** values before `docker compose build llama-cpp`; every model download is
checksum-verified.

```bash
export MODEL_URL=https://models.example/tool-capable-model.gguf
export MODEL_SHA256=the-model-file-sha256
docker compose build llama-cpp
```

`examples/compose.toml` explicitly enables plain HTTP for the fixture at
`http://localhost:8081/`. Do not use that setting for ordinary deployments. External Playwright
MCP deployments are responsible for the required isolated, non-shared browser-context flags.

After the Compose services are ready, run the browser and fixture integration suite:

```bash
uv run pytest tests/integration --run-compose-integration --no-cov
```

The focused command disables coverage because the 80% gate applies to the full suite. Endpoint
options default to Compose service DNS names and can be overridden with `--compose-app-endpoint`,
`--compose-fixture-url`, `--compose-model-api-base`, and `--compose-playwright-endpoint`.

It uses the explicit plain-HTTP integration configuration, validates the official Playwright MCP
wire contract and rendered-document cleanup against `http://test-site:8081/`, checks the actual
model and application transports, and avoids nondeterministic local-model tool calls. A complete
`render_and_strip_page` end-to-end call additionally requires a reliably tool-capable GGUF model,
which is not part of the deterministic test suite.

### Dev container

Open the repository in a Dev Containers-compatible editor and select **Reopen in Container**. The
configuration starts the Playwright MCP, model, fixture, and an application server. It exposes the
MCP endpoint at `http://localhost:8000/mcp` with the container-only settings in
[`examples/devcontainer.toml`](examples/devcontainer.toml). The devcontainer allows plain HTTP
solely so the included fixture can be exercised. It runs as an unprivileged UID/GID 1000 user and
uses the workspace-local `.venv`; choose either local or devcontainer development and recreate the
virtual environment when switching if necessary.

## Verification

Run the deterministic suite, which emits terminal and XML coverage reports and enforces 80% branch
coverage, plus formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The local Compose stack validates transport and browser compatibility. A live browser-agent
end-to-end integration test additionally requires the configured llama.cpp GGUF model to reliably
emit the required streamed tool-call protocol, so it is documented rather than run in the unit
suite.

## Tested compatibility pins

The locked Python runtime uses FastMCP 3.4.5, LiteLLM 1.95.0, OpenAI 2.20.0, Pydantic 2.12.5,
Pydantic Settings 2.14.2, Beautiful Soup 4.14.3, pytest 9.0.2, and Ruff 0.15.1. See
[`pyproject.toml`](pyproject.toml) and [`uv.lock`](uv.lock) for the complete resolved set.

The tested browser contract is `@playwright/mcp` 0.0.78 at Streamable HTTP path `/mcp`, deployed
as `mcr.microsoft.com/playwright/mcp:v0.0.78@sha256:3d871c22ea2d4cca0966e2cfb1860e1cb03eb7353725a3d6cffd133296fb04eb`.
The service requires `browser_navigate(url)`, `browser_tabs(action, index?, url?)`,
`browser_evaluate(function, element?, target?, filename?)`, and `browser_close()`. The pinned
llama.cpp model image uses release b10273 at
`ghcr.io/ggml-org/llama.cpp@sha256:14ab06c571008509adcedf635301edfa98071b1b8345269921d31ea4d519ae47`.
