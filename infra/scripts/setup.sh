#!/usr/bin/env bash
set -euo pipefail

echo "=== SchemaIntern Development Environment Setup ==="

# --------------- Python / uv ---------------
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "uv already installed: $(uv --version)"
fi

echo "Installing Python dependencies..."
uv sync --all-extras --directory backend

# --------------- Node.js ---------------
if ! command -v node &> /dev/null; then
    echo "Please install Node.js 20+: https://nodejs.org/"
    exit 1
fi
echo "Node.js: $(node --version)"

if [ -f frontend/package.json ]; then
    echo "Installing frontend dependencies..."
    npm --prefix frontend ci
fi

# --------------- Pre-commit ---------------
if command -v uv &> /dev/null; then
    echo "Installing pre-commit hooks..."
    uv run --directory backend pre-commit install 2>/dev/null || true
fi

# --------------- Docker ---------------
if command -v docker &> /dev/null; then
    echo "Docker available: $(docker --version)"
    echo "Run 'docker compose -f infra/docker/docker-compose.yml up -d' to start services."
else
    echo "Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/"
fi

echo ""
echo "=== Setup complete ==="
