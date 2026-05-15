#!/usr/bin/env bash
#
# bootstrap.sh — One-time setup for Azure AI Foundry + GitHub OIDC federation
#
# Provisions:
#   1. Resource group
#   2. TEST Foundry project (Bicep) — skipped with --skip-foundry
#   3. PROD Foundry project (Bicep) — skipped with --skip-foundry
#   4. App Registration + Service Principal
#   5. 3 Federated credentials (main, PR, tags)
#   6. RBAC role assignments
#   7. GitHub repository variables
#
# Prerequisites: az cli, gh cli, both logged in
#
# Usage:
#   ./scripts/bootstrap.sh \
#     --resource-group rg-agent-devops \
#     --location swedencentral \
#     --account-name agentdevops \
#     --github-repo san360/agent-devops
#
#   # Skip Foundry project creation (use existing projects):
#   ./scripts/bootstrap.sh \
#     --resource-group rg-agent-devops \
#     --account-name agentdevops \
#     --skip-foundry \
#     --test-endpoint "https://..." \
#     --prod-endpoint "https://..."

set -euo pipefail

# ---------- defaults ----------
RESOURCE_GROUP=""
LOCATION="swedencentral"
ACCOUNT_NAME=""
GITHUB_REPO="san360/agent-devops"
GPT_MODEL_NAME="gpt-4o"
GPT_MODEL_VERSION="2024-11-20"
GPT_DEPLOYMENT_NAME="gpt-4o-2024-11-20"
GPT_CAPACITY=30
BING_CONNECTION_NAME="bing-grounding"
SKIP_FOUNDRY=false
TEST_ENDPOINT=""
PROD_ENDPOINT=""

# ---------- parse args ----------
while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-group)  RESOURCE_GROUP="$2";      shift 2 ;;
    --location)        LOCATION="$2";            shift 2 ;;
    --account-name)    ACCOUNT_NAME="$2";        shift 2 ;;
    --github-repo)     GITHUB_REPO="$2";         shift 2 ;;
    --gpt-deployment)  GPT_DEPLOYMENT_NAME="$2"; shift 2 ;;
    --gpt-capacity)    GPT_CAPACITY="$2";        shift 2 ;;
    --skip-foundry)    SKIP_FOUNDRY=true;        shift   ;;
    --test-endpoint)   TEST_ENDPOINT="$2";       shift 2 ;;
    --prod-endpoint)   PROD_ENDPOINT="$2";       shift 2 ;;
    *)                 echo "Unknown flag: $1"; exit 1 ;;
  esac
done

if [[ -z "$RESOURCE_GROUP" || -z "$ACCOUNT_NAME" ]]; then
  echo "Usage: $0 --resource-group <rg> --account-name <name> [--location <loc>] [--github-repo <owner/repo>]"
  echo "       Add --skip-foundry --test-endpoint <url> --prod-endpoint <url> to use existing projects"
  exit 1
fi

if [[ "$SKIP_FOUNDRY" == true && ( -z "$TEST_ENDPOINT" || -z "$PROD_ENDPOINT" ) ]]; then
  echo "ERROR: --skip-foundry requires both --test-endpoint and --prod-endpoint"
  exit 1
fi

TEST_PROJECT="${ACCOUNT_NAME}-test"
PROD_PROJECT="${ACCOUNT_NAME}-prod"
APP_DISPLAY_NAME="github-${ACCOUNT_NAME}-cicd"

echo "============================================"
echo " AI Foundry Agent DevOps — Bootstrap"
echo "============================================"
echo " Resource Group:  $RESOURCE_GROUP"
echo " Location:        $LOCATION"
echo " Account Name:    $ACCOUNT_NAME"
echo " Skip Foundry:    $SKIP_FOUNDRY"
if [[ "$SKIP_FOUNDRY" == true ]]; then
  echo " TEST endpoint:   $TEST_ENDPOINT (provided)"
  echo " PROD endpoint:   $PROD_ENDPOINT (provided)"
else
  echo " Test Project:    $TEST_PROJECT"
  echo " Prod Project:    $PROD_PROJECT"
fi
echo " GitHub Repo:     $GITHUB_REPO"
echo " GPT Deployment:  $GPT_DEPLOYMENT_NAME"
echo "============================================"
echo ""

# ---------- Step 1: Resource Group ----------
echo "[1/7] Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ---------- Step 2 & 3: Deploy Foundry projects (or skip) ----------
if [[ "$SKIP_FOUNDRY" == true ]]; then
  echo "[2/7] Skipping TEST Foundry project (using provided endpoint)"
  echo "[3/7] Skipping PROD Foundry project (using provided endpoint)"
else
  echo "[2/7] Deploying TEST Foundry project..."
  TEST_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file infra/main.bicep \
    --parameters \
      accountName="${ACCOUNT_NAME}test" \
      projectName="$TEST_PROJECT" \
      gptDeploymentName="$GPT_DEPLOYMENT_NAME" \
      gptModelName="$GPT_MODEL_NAME" \
      gptModelVersion="$GPT_MODEL_VERSION" \
      gptCapacity="$GPT_CAPACITY" \
    --output json)

  TEST_ENDPOINT=$(echo "$TEST_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['projectEndpoint']['value'])")
  echo "  TEST endpoint: $TEST_ENDPOINT"

  echo "[3/7] Deploying PROD Foundry project..."
  PROD_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file infra/main.bicep \
    --parameters \
      accountName="${ACCOUNT_NAME}prod" \
      projectName="$PROD_PROJECT" \
      gptDeploymentName="$GPT_DEPLOYMENT_NAME" \
      gptModelName="$GPT_MODEL_NAME" \
      gptModelVersion="$GPT_MODEL_VERSION" \
      gptCapacity="$GPT_CAPACITY" \
    --output json)

  PROD_ENDPOINT=$(echo "$PROD_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['projectEndpoint']['value'])")
  echo "  PROD endpoint: $PROD_ENDPOINT"
fi

# ---------- Step 4: App Registration + Service Principal ----------
echo "[4/7] Creating App Registration and Service Principal..."
APP_ID=$(az ad app create \
  --display-name "$APP_DISPLAY_NAME" \
  --query appId -o tsv)

SP_OBJ_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo "  Client ID:     $APP_ID"
echo "  SP Object ID:  $SP_OBJ_ID"

# ---------- Step 5: Federated Credentials ----------
echo "[5/7] Adding federated credentials..."

az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters "{
    \"name\": \"github-main\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:ref:refs/heads/main\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" --output none
echo "  + main branch credential"

az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters "{
    \"name\": \"github-pr\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:pull_request\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" --output none
echo "  + pull request credential"

az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters "{
    \"name\": \"github-release\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:ref:refs/tags/*\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" --output none
echo "  + release tag credential"

# ---------- Step 6: RBAC Role Assignments ----------
echo "[6/7] Assigning RBAC roles..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

az role assignment create \
  --assignee "$SP_OBJ_ID" \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
  --scope "$SCOPE" \
  --output none
echo "  + Azure AI User (on resource group)"

az role assignment create \
  --assignee "$SP_OBJ_ID" \
  --role "Cognitive Services OpenAI User" \
  --scope "$SCOPE" \
  --output none
echo "  + Cognitive Services OpenAI User (on resource group)"

# Azure AI Developer on Foundry account scope (needed for agents/write data action)
if [[ -n "$TEST_ENDPOINT" ]]; then
  FOUNDRY_HOST=$(echo "$TEST_ENDPOINT" | sed -E 's|https://([^/]+)/.*|\1|')
  FOUNDRY_ACCOUNT_NAME=$(echo "$FOUNDRY_HOST" | sed -E 's|\.services\.ai\.azure\.com||')
  FOUNDRY_ACCOUNT_ID=$(az cognitiveservices account list \
    --query "[?name=='${FOUNDRY_ACCOUNT_NAME}'].id | [0]" -o tsv 2>/dev/null)
  if [[ -n "$FOUNDRY_ACCOUNT_ID" ]]; then
    az role assignment create \
      --assignee "$SP_OBJ_ID" \
      --role "Azure AI Developer" \
      --scope "$FOUNDRY_ACCOUNT_ID" \
      --output none
    echo "  + Azure AI Developer (on Foundry account: $FOUNDRY_ACCOUNT_NAME)"
  else
    echo "  ! Could not resolve Foundry account ID — assign Azure AI Developer manually"
  fi
fi

# ---------- Step 7: GitHub Variables ----------
echo "[7/7] Setting GitHub repository variables..."
TENANT_ID=$(az account show --query tenantId -o tsv)

gh variable set AZURE_CLIENT_ID       --body "$APP_ID"             --repo "$GITHUB_REPO"
gh variable set AZURE_TENANT_ID       --body "$TENANT_ID"          --repo "$GITHUB_REPO"
gh variable set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID"    --repo "$GITHUB_REPO"
gh variable set FOUNDRY_TEST_ENDPOINT --body "$TEST_ENDPOINT"      --repo "$GITHUB_REPO"
gh variable set FOUNDRY_PROD_ENDPOINT --body "$PROD_ENDPOINT"      --repo "$GITHUB_REPO"
gh variable set GPT_DEPLOYMENT        --body "$GPT_DEPLOYMENT_NAME" --repo "$GITHUB_REPO"
gh variable set BING_CONNECTION_NAME  --body "$BING_CONNECTION_NAME" --repo "$GITHUB_REPO"
echo "  Set 7 variables on $GITHUB_REPO"

# ---------- Summary ----------
echo ""
echo "============================================"
echo " Bootstrap complete!"
echo "============================================"
echo ""
echo " Azure Resources:"
echo "   Resource Group:     $RESOURCE_GROUP"
echo "   TEST endpoint:      $TEST_ENDPOINT"
echo "   PROD endpoint:      $PROD_ENDPOINT"
echo "   GPT deployment:     $GPT_DEPLOYMENT_NAME"
echo ""
echo " Identity:"
echo "   App Registration:   $APP_DISPLAY_NAME"
echo "   Client ID:          $APP_ID"
echo "   SP Object ID:       $SP_OBJ_ID"
echo "   Tenant ID:          $TENANT_ID"
echo "   Subscription ID:    $SUBSCRIPTION_ID"
echo ""
echo " GitHub ($GITHUB_REPO):"
echo "   7 repository variables set"
echo "   3 federated credentials configured"
echo ""
echo " Next steps:"
echo "   1. Configure Bing Grounding connection in both Foundry projects"
echo "      (Portal: ai.azure.com -> project -> Connections -> + New)"
echo "   2. Run lifecycle scripts in order:"
echo "      ./scripts/lifecycle/01-phase1-web-search.sh"
echo "      ./scripts/lifecycle/02-phase2-code-interpreter.sh"
echo "      ./scripts/lifecycle/03-model-upgrade.sh"
echo ""

# Save bootstrap state for teardown
STATE_FILE=".bootstrap-state.json"
python3 -c "
import json
json.dump({
    'resource_group': '$RESOURCE_GROUP',
    'location': '$LOCATION',
    'account_name': '$ACCOUNT_NAME',
    'app_id': '$APP_ID',
    'sp_obj_id': '$SP_OBJ_ID',
    'github_repo': '$GITHUB_REPO',
    'tenant_id': '$TENANT_ID',
    'subscription_id': '$SUBSCRIPTION_ID',
    'test_endpoint': '$TEST_ENDPOINT',
    'prod_endpoint': '$PROD_ENDPOINT',
    'gpt_deployment': '$GPT_DEPLOYMENT_NAME'
}, open('$STATE_FILE', 'w'), indent=2)
"
echo " State saved to $STATE_FILE (used by teardown.sh)"

# Save .env for local development
ENV_FILE=".env"
cat > "$ENV_FILE" <<EOF
# Generated by bootstrap.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Identity (Service Principal)
AZURE_CLIENT_ID=$APP_ID
AZURE_TENANT_ID=$TENANT_ID
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
SP_OBJECT_ID=$SP_OBJ_ID

# Azure AI Foundry endpoints
FOUNDRY_TEST_ENDPOINT=$TEST_ENDPOINT
FOUNDRY_PROD_ENDPOINT=$PROD_ENDPOINT

# Model deployment
GPT_DEPLOYMENT=$GPT_DEPLOYMENT_NAME

# Bing Grounding connection name
BING_CONNECTION_NAME=$BING_CONNECTION_NAME

# Resource metadata
RESOURCE_GROUP=$RESOURCE_GROUP
LOCATION=$LOCATION
ACCOUNT_NAME=$ACCOUNT_NAME
GITHUB_REPO=$GITHUB_REPO
EOF
echo " Local .env written (git-ignored)"
