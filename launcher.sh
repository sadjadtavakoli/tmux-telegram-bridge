#!/bin/bash
set -e

SESSION="${TMUX_SESSION:-claude}"
BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check for .env
if [ ! -f "$BRIDGE_DIR/.env" ]; then
    echo "Error: .env not found. Copy .env.example to .env and fill in your credentials."
    echo "  cp $BRIDGE_DIR/.env.example $BRIDGE_DIR/.env"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists. Starting bridge only..."
else
    echo "Creating tmux session '$SESSION' with Claude Code..."
    tmux new-session -d -s "$SESSION" -n code
    tmux send-keys -t "$SESSION:code" "claude" Enter
fi

# Kill existing bridge window if present
if tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -q '^bridge$'; then
    tmux kill-window -t "$SESSION:bridge"
fi

# Start bridge in a new window
tmux new-window -t "$SESSION" -n bridge \
    "cd '$BRIDGE_DIR' && source .venv/bin/activate && python3 bridge.py; read -p 'Bridge exited. Press enter to close.'"

# Switch to the code window
tmux select-window -t "$SESSION:code"

# Attach or switch
if [ -n "$TMUX" ]; then
    tmux switch-client -t "$SESSION"
else
    tmux attach -t "$SESSION"
fi
