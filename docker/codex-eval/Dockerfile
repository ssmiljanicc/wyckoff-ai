FROM node:22-bookworm-slim@sha256:d9f850096136edbc402debdd8729579a288aac64574ada0ff4db26b6ae58b0b2

ARG CODEX_VERSION=0.141.0

RUN npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force \
    && groupadd --gid 10001 codex \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/sh codex \
    && install -d -o codex -g codex /workspace /run/secrets

USER codex
WORKDIR /workspace
ENV CODEX_HOME=/home/codex/.codex
