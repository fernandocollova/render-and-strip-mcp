FROM ghcr.io/astral-sh/uv:0.9.20-python3.13-trixie-slim

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        ca-certificates \
        curl \
        git \
        nodejs \
        npm \
    && npm install --global --ignore-scripts --no-audit --no-fund npm@10.8.2 \
    && rm --recursive --force /var/lib/apt/lists/*

RUN groupadd --gid 1000 devcontainer \
    && useradd --create-home --gid devcontainer --shell /bin/bash --uid 1000 devcontainer \
    && mkdir --parents /workspace \
    && chown devcontainer:devcontainer /workspace

COPY --chown=devcontainer:devcontainer .npmrc package.json package-lock.json /opt/container-tools/

USER devcontainer

WORKDIR /opt/container-tools
RUN npm ci \
    && npm run setup:opencode \
    && npm run verify:tools \
    && npm run audit:dependencies \
    && npm run audit:signatures \
    && npm cache clean --force

ENV PATH=/opt/container-tools/node_modules/.bin:${PATH}

WORKDIR /workspace
