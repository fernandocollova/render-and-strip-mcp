FROM alpine:3.22.1 AS model-download

ARG MODEL_URL=https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf
ARG MODEL_SHA256=6eb923e7d26e9cea28811e1a8e852009b21242fb157b26149d3b188f3a8c8653

RUN apk add --no-cache curl
RUN set -eux; \
    curl --fail --location --retry 3 --output /model.gguf "$MODEL_URL"; \
    echo "$MODEL_SHA256  /model.gguf" | sha256sum -c -

FROM ghcr.io/ggml-org/llama.cpp@sha256:14ab06c571008509adcedf635301edfa98071b1b8345269921d31ea4d519ae47

COPY --from=model-download /model.gguf /models/model.gguf
