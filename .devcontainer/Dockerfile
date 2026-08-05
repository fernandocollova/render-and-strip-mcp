FROM ghcr.io/astral-sh/uv:0.9.20-python3.13-bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends --yes git curl \
    && rm --recursive --force /var/lib/apt/lists/*

RUN groupadd --gid 1000 devcontainer \
    && useradd --create-home --gid devcontainer --shell /bin/bash --uid 1000 devcontainer \
    && mkdir --parents /workspace \
    && chown devcontainer:devcontainer /workspace

WORKDIR /workspace
USER devcontainer
