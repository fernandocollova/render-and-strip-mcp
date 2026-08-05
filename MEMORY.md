# Project notes

- `/home/fcollova/projects/nyc-stats` is a structure-only reference. Never copy, import, reuse, or otherwise use code from it in this project.
- Compose builds the llama.cpp model image from `docker/llama-cpp/Dockerfile`; its sole `MODEL_URL` and `MODEL_SHA256` defaults are checksum-verified, and custom models must supply both values.
- The devcontainer attaches to the Compose `app` service as UID/GID 1000 user `devcontainer`; it intentionally uses the workspace-local `.venv`.
- This workspace runs inside that `app` container. Its image does not install the Docker CLI, so do not invoke `docker compose` here. The devcontainer starts `playwright-mcp`, `llama-cpp`, `test-site`, and `app`; run Compose integration tests directly with `uv run pytest tests/integration --run-compose-integration --no-cov`, using the Compose service-DNS defaults.
