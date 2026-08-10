FROM ghcr.io/astral-sh/uv:0.9.20-python3.13-trixie-slim
ENV UV_NO_CACHE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app
COPY . /context

RUN groupadd --gid 1000 render_and_strip_mcp && \
    useradd --gid render_and_strip_mcp --uid 1000 render_and_strip_mcp && \
    uv sync --locked --no-editable --no-group dev --directory /context && \
    rm -rf /context

USER devcontainer
ENTRYPOINT /app/bin/python3 -m render_and_strip_mcp
