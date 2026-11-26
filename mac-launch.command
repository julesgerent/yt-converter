#!/bin/bash
cd "$(dirname "$0")"

if ! command -v uv &> /dev/null; then
    echo "Installation de uv en cours..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

uv run main.py
