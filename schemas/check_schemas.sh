#!/bin/bash
#
# This script is called on CI to ensure the current schemas didn't change.
#
SELF_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

echo "Collecting the schemas for Microsoft Azure Marketplace"
git stash
tox -e azure_schemas "${SELF_DIR}/azure"
git stash pop

echo "Checking for changes on schemas..."
if [[ -z "$(git diff)" ]]; then
    echo "No changes detected."
else
    echo "Detected schema changes:"
    git diff
    exit 1
fi
