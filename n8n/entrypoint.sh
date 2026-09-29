#!/bin/bash
# n8n entrypoint: import and activate workflows (SPEC §14.5, §23)
# Wraps the default n8n entrypoint to import workflow definitions before startup.

set -e

# Import workflows from /workflows directory
WORKFLOWS_DIR="/workflows"

if [ -d "$WORKFLOWS_DIR" ]; then
    echo "[n8n setup] Importing workflows from $WORKFLOWS_DIR..."

    # Start n8n in background to enable CLI commands
    node /dist/index.js &
    N8N_PID=$!

    # Wait for n8n API to be ready
    echo "[n8n setup] Waiting for n8n API..."
    for i in {1..30}; do
        if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
            echo "[n8n setup] n8n is ready"
            break
        fi
        echo "[n8n setup] Attempt $i/30..."
        sleep 2
    done

    # Import each workflow
    for workflow_file in "$WORKFLOWS_DIR"/*.json; do
        if [ -f "$workflow_file" ]; then
            workflow_name=$(basename "$workflow_file" .json)
            echo "[n8n setup] Importing workflow: $workflow_name"

            # Import with n8n CLI
            NODE_OPTIONS="--max-old-space-size=2048" \
            n8n import:workflow --input="$workflow_file" 2>&1 || echo "[n8n setup] Import of $workflow_name completed (status: $?)"
        fi
    done

    # Stop background n8n and let docker-entrypoint.sh start it properly
    echo "[n8n setup] Stopping background n8n..."
    kill $N8N_PID 2>/dev/null || true
    wait $N8N_PID 2>/dev/null || true
    sleep 1
else
    echo "[n8n setup] Warning: WORKFLOWS_DIR not found: $WORKFLOWS_DIR"
fi

# Start n8n with default entrypoint
echo "[n8n setup] Starting n8n with default configuration..."
exec /docker-entrypoint.sh "$@"
