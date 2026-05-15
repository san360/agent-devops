#!/usr/bin/env bash
#
# teardown.sh — Remove all Azure resources and GitHub config created by bootstrap.sh
#
# Reads .bootstrap-state.json to know what to delete.
#
# Usage: ./scripts/teardown.sh [--yes]
#   --yes   Skip confirmation prompt

set -euo pipefail

STATE_FILE=".bootstrap-state.json"
SKIP_CONFIRM=false

if [[ "${1:-}" == "--yes" ]]; then
  SKIP_CONFIRM=true
fi

if [[ ! -f "$STATE_FILE" ]]; then
  echo "ERROR: $STATE_FILE not found. Run bootstrap.sh first or provide the file."
  exit 1
fi

# Read state
RESOURCE_GROUP=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['resource_group'])")
APP_ID=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['app_id'])")
GITHUB_REPO=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['github_repo'])")

echo "============================================"
echo " AI Foundry Agent DevOps — Teardown"
echo "============================================"
echo ""
echo " Will delete:"
echo "   Resource Group:    $RESOURCE_GROUP (and all resources within)"
echo "   App Registration:  $APP_ID (and federated credentials)"
echo "   GitHub Variables:  7 variables on $GITHUB_REPO"
echo ""

if [[ "$SKIP_CONFIRM" != true ]]; then
  read -rp "Are you sure? This cannot be undone. (yes/no): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ---------- Step 1: Delete Resource Group ----------
echo "[1/3] Deleting resource group $RESOURCE_GROUP..."
az group delete \
  --name "$RESOURCE_GROUP" \
  --yes \
  --no-wait
echo "  Resource group deletion initiated (async)"

# ---------- Step 2: Delete App Registration ----------
echo "[2/3] Deleting app registration $APP_ID..."

# Delete federated credentials first
for CRED_NAME in github-main github-pr github-release; do
  CRED_ID=$(az ad app federated-credential list --id "$APP_ID" \
    --query "[?name=='$CRED_NAME'].id" -o tsv 2>/dev/null || true)
  if [[ -n "$CRED_ID" ]]; then
    az ad app federated-credential delete --id "$APP_ID" --federated-credential-id "$CRED_ID" --output none
    echo "  - Deleted credential: $CRED_NAME"
  fi
done

# Delete the app (also deletes the service principal)
az ad app delete --id "$APP_ID" --output none
echo "  App registration deleted"

# ---------- Step 3: Remove GitHub Variables ----------
echo "[3/3] Removing GitHub repository variables..."
VARS=(
  AZURE_CLIENT_ID
  AZURE_TENANT_ID
  AZURE_SUBSCRIPTION_ID
  FOUNDRY_TEST_ENDPOINT
  FOUNDRY_PROD_ENDPOINT
  GPT_DEPLOYMENT
  BING_CONNECTION_NAME
)
for VAR in "${VARS[@]}"; do
  gh variable delete "$VAR" --repo "$GITHUB_REPO" 2>/dev/null || true
  echo "  - Removed $VAR"
done

# ---------- Cleanup ----------
rm -f "$STATE_FILE"

echo ""
echo "============================================"
echo " Teardown complete!"
echo "============================================"
echo ""
echo " - Resource group $RESOURCE_GROUP is being deleted (may take a few minutes)"
echo " - App registration $APP_ID deleted"
echo " - GitHub variables removed from $GITHUB_REPO"
echo " - $STATE_FILE removed"
