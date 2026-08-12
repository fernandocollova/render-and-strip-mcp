# Render and Strip MCP

`render-and-strip-mcp` is a Streamable HTTP MCP server with one tool:

```text
render_and_strip_page(url, task) -> clean semantic HTML
```

For each request it opens a fresh isolated session with an official Playwright MCP server, uses a
tool-calling model to reach the requested page or view and greedily collect its revealable retained
or same-origin paginated content, validates every top-level origin, and returns one normalized
semantic HTML document containing only selected visible task-content regions. Surrounding page
chrome is excluded by the selected boundary. Failures are MCP tool errors; partial HTML is never
returned.

## Requirements

- Python 3.11–3.14 and [uv](https://docs.astral.sh/uv/).
- A reachable **official Playwright MCP** Streamable HTTP endpoint. It must run with `--isolated`
  and **without** `--shared-browser-context`. The Compose deployment below is the tested setup.
- An OpenAI-compatible chat endpoint accepted by LiteLLM. Its model must support streamed chat
  function tools, `tool_choice="auto"`, sequential tool calls, `temperature=0`, and `max_tokens`.
  It must reliably call each stage's required completion tool; provider reasoning output is optional
  and is never sent as a model request parameter.

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
export RENDER_AND_STRIP_MCP_LLM__MODEL=openai/model-name
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
- Default execution limits are 12 model turns, 30 browser actions, a 3600-second run limit, 20
  navigation seconds, 15 action seconds, 90 model-request seconds, a 0-second optional settle
  grace, and 10 cleanup seconds. The model-turn and browser-action limits apply independently to
  access, discovery, reconstruction, each retained-document collection, and each pagination-advance
  iteration. The run deadline is renewed immediately before browser closing. The model-request
  deadline resets when the model reports non-blank reasoning. `max_paginated_documents` defaults
  to 25 captured pages across the invocation.
  Reaching that limit succeeds only if the final page's semantic or natural completion assessment
  succeeds; otherwise the request fails without partial HTML.
  Navigation calls use the navigation timeout, while each other browser operation (tab handling,
  URL checks, snapshots, actions, and selected-region capture) uses its own action timeout.
- `max_html_bytes = 0` permits unlimited clean HTML. A positive limit applies to the complete
  assembled UTF-8 result; an overage is an error, not a truncation.
- Optional reasoning progress uses `reasoning_progress_max_items = 0` and
  `reasoning_progress_min_interval_seconds = 0` for unlimited, immediate forwarding. These existing
  settings govern one shared stream of provider `reasoning_content` and labelled operational
  milestones; milestones consume the same configured item allowance. Progress is sent only when
  the MCP caller accepts it.
- Application logging writes to standard error. Set the `level` key in `[logging]` to `CRITICAL`,
  `ERROR`, `WARNING`, `INFO` (the default), or `DEBUG`; the equivalent environment variable is
  `RENDER_AND_STRIP_MCP_LOGGING__LEVEL`. Debug logging records model-stage activity and every
  reasoning-progress batch submitted to the MCP caller, including its message. Do not enable it
  where model reasoning may contain sensitive information.

### Greedy page/view retrieval

`render_and_strip_page(url, task)` keeps its two-input public signature and has no greedy-collection
opt-out. The access stage establishes a semantic page/view checkpoint rather than extracting
individual facts. Discovery inspects and, when safe, probes both retained reveal and immediate
page-advance mechanisms. It can select `retained-final-document` when relevant content can coexist
in one final visible document, or `paginated-documents` when a proven immediate Next/numbered action
replaces the current same-origin result document and retained collection can run on each page.
Unsafe, ambiguous, virtualized, mixed, unsupported, or unproven behavior is `unknown` and fails
without a reset, collection, partial result, or HTML output.

After discovery, the service navigates the original tab in the same browser context to the exact
caller URL and reconstructs the checkpoint semantically from fresh controls. It does not replay
element references or discovery history. Collection exhausts retainable scrolling/lazy additions,
additive controls, and expansions that can remain open together. When observations show pending
effects, the model must use a semantic wait or investigation action before completion. A feed that
continues to reveal relevant content until a configured stage or total limit is reached fails rather
than returning an incomplete document.

For `paginated-documents`, the same retained-document collection runs independently on each result
page. From each final fresh snapshot, collection identifies exactly one contiguous task-relevant
region and its current Playwright target. The service immediately captures that region's
visibility-filtered subtree before an immediate next-page action can replace it. The boundary
excludes surrounding page-level header, navigation, sidebar, search, and footer chrome; there is no
full-body fallback. A dedicated model stage uses the original task and compact cumulative progress to
decide whether later pages can still be relevant. Natural terminal pagination is the default when
the task has no explicit cutoff; uncertainty causes continuation rather than early completion. A
semantic boundary preserves its complete captured selected region. Traversal never treats
record-detail, `Read more`, or expanded-reading links as pagination, and unchanged or repeated page
states fail instead of duplicating content. Put semantic cutoffs directly in `task`, for example “retrieve
releases through version 2.0”; there is no site-, date-, or version-specific parser.

Every model-directed action is followed by an orchestration-owned fresh `browser_snapshot` after
the optional settle grace. The service restores the original tab and enforces the origin established
by initial navigation before each snapshot and selected-region capture. Each region is cleaned
independently, with relative links resolved against that region's source URL. One and many captures
then use the same fixed shape, in capture order and without page wrappers:

```html
<!doctype html>
<html><head><meta charset="utf-8"></head><body><main>…</main></body></html>
```

An outer selected `main` is unwrapped so the result always has exactly one `main`. Cleaning may
intentionally omit DOM content under its visibility, element, attribute, and aggregate size
policies; the service does not perform fine-grained fact extraction, verify facts after cleaning,
or return partial captures.

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

It uses the explicit plain-HTTP integration configuration, exercises the official Playwright MCP
wire behavior and rendered-document cleanup against `http://test-site:8081/`, checks the actual
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

The local Compose stack validates transport, browser compatibility, fresh snapshots, semantic waits,
and final-DOM visibility retention. A live browser-agent end-to-end integration test additionally
requires the configured llama.cpp GGUF model to reliably emit all staged completion-tool calls, so
it is documented rather than run in the deterministic suite.

## Tested compatibility pins

The locked Python runtime uses FastMCP 3.4.5, LiteLLM 1.95.0, OpenAI 2.20.0, Pydantic 2.12.5,
Pydantic Settings 2.14.2, Beautiful Soup 4.14.3, pytest 9.0.2, and Ruff 0.15.1. See
[`pyproject.toml`](pyproject.toml) and [`uv.lock`](uv.lock) for the complete resolved set.

The tested browser contract is `@playwright/mcp` 0.0.78 at Streamable HTTP path `/mcp`, deployed
as `mcr.microsoft.com/playwright/mcp:v0.0.78@sha256:3d871c22ea2d4cca0966e2cfb1860e1cb03eb7353725a3d6cffd133296fb04eb`.
The service requires `browser_navigate(url)`, `browser_tabs(action, index?, url?)`,
`browser_snapshot(target?, depth?, boxes?, filename?)`, `browser_evaluate(function, element?,
target?, filename?)`, and `browser_close()`. Selected capture uses the targeted evaluate form with
all of `function`, the human-readable `element`, and the fresh snapshot `target`; the function
receives that resolved element directly. The pinned llama.cpp model image uses release b10273 at
`ghcr.io/ggml-org/llama.cpp@sha256:14ab06c571008509adcedf635301edfa98071b1b8345269921d31ea4d519ae47`.
