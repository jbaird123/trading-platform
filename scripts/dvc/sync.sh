#!/bin/bash
set -e

ACTION=$1

if [[ "$ACTION" != "push" && "$ACTION" != "pull" ]]; then
    echo "Error: Invalid action. Use 'push' or 'pull'."
    exit 1
fi

echo "Executing dvc $ACTION..."
dvc "$ACTION"
echo "DVC sync ($ACTION) complete."
