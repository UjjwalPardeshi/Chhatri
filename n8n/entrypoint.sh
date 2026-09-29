#!/bin/bash
# n8n entrypoint: import and activate workflows (SPEC §14.5, §23)
# This script runs before the default n8n startup to import workflow definitions
# and activate them, ensuring workflows are available immediately.

set -e

# Wait for n8n to be ready (if running in docker compose context)
if [ ! -z "$DB_TYPE" ]; then
    echo "Waiting for n8n database to initialize..."
    sleep 5
fi

# Import workflows from /workflows directory
echo "Importing n8n workflows..."
WORKFLOWS_DIR="${WORKFLOWS_DIR:-/workflows}"

if [ -d "$WORKFLOWS_DIR" ]; then
    for workflow_file in "$WORKFLOWS_DIR"/*.json; do
        if [ -f "$workflow_file" ]; then
            workflow_name=$(basename "$workflow_file" .json)
            echo "  Importing $workflow_name..."

            # Use n8n CLI to import workflow
            # The import:workflow command expects: n8n import:workflow --input=<file>
            n8n import:workflow --input="$workflow_file" || true
        fi
    done
else
    echo "Warning: WORKFLOWS_DIR not found: $WORKFLOWS_DIR"
fi

# Activate workflows
echo "Activating workflows..."
n8n launch || true

# If launch fails or completes, fall back to default startup
echo "Starting n8n..."
exec /docker-entrypoint.sh "$@"
