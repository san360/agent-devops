# AI Foundry Prompt Agent — DevOps & Lifecycle Management

A complete CI/CD lifecycle for an Azure AI Foundry prompt agent, demonstrating
versioned prompts, tool changes, model upgrades, evaluation gates, and rollback.

## Agent: Technology Trend Research & Analysis

- **Phase 1:** Web search only (`web_search` tool)
- **Phase 2:** Web search + Code Interpreter for data analysis

## Repository Structure

```
agents/                          Agent config skeleton (JSON)
prompts/                         System prompt (Markdown)
evals/                           Golden dataset + evaluator config
scripts/
  deploy_agent.py                Deploy agent to TEST or PROD
  rollback_agent.py              Re-deploy from a saved artifact
  compare_models.py              Side-by-side model comparison
  bootstrap.sh                   One-time Azure + GitHub setup
  teardown.sh                    Reverse everything bootstrap created
  lifecycle/
    01-phase1-web-search.sh      PR: agent with web search only
    02-phase2-code-interpreter.sh PR: add code interpreter
    03-model-upgrade.sh          PR: upgrade model to gpt-4.1
infra/                           Bicep IaC for Foundry project
artifacts/                       Generated deployment snapshots (post-deploy)
.github/workflows/               CI/CD pipelines
tests/                           Unit tests
```

## Prerequisites

- Python 3.12+
- Azure CLI (`az login`)
- GitHub CLI (`gh auth login`)
- An Azure subscription with permissions to create resources and App Registrations
- An Azure OpenAI deployment (e.g. `gpt-4o-2024-11-20`)

## Quick Start — Automated Bootstrap

The bootstrap script provisions all Azure infrastructure and GitHub configuration in one shot.

```bash
# 1. Login to Azure and GitHub
az login
gh auth login

# 2. Run bootstrap
./scripts/bootstrap.sh \
  --resource-group rg-agent-devops \
  --account-name agentdevops \
  --location eastus \
  --github-repo san360/agent-devops
```

This creates:
- A resource group with TEST and PROD AI Foundry projects (via Bicep)
- An App Registration with a Service Principal
- 3 federated credentials for GitHub OIDC (main branch, pull requests, tags)
- RBAC role assignments (Azure AI User, Cognitive Services OpenAI User)
- 6 GitHub repository variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `FOUNDRY_TEST_ENDPOINT`, `FOUNDRY_PROD_ENDPOINT`, `GPT_DEPLOYMENT`)

State is saved to `.bootstrap-state.json` for use by the teardown script.

### Bootstrap Parameters

| Flag | Required | Default | Description |
|---|---|---|---|
| `--resource-group` | Yes | — | Azure resource group name |
| `--account-name` | Yes | — | Base name for Foundry accounts (suffixed with `test`/`prod`) |
| `--location` | No | `eastus` | Azure region |
| `--github-repo` | No | `san360/agent-devops` | GitHub `owner/repo` for variables and federation |
| `--gpt-deployment` | No | `gpt-4o-2024-11-20` | GPT model deployment name |
| `--gpt-capacity` | No | `30` | GPT deployment capacity (tokens per minute in thousands) |

## Lifecycle Demo — Phase 1 → Phase 2 → Model Upgrade

Three scripts simulate the full agent lifecycle by creating PRs that trigger the CI/CD pipeline. Run them sequentially — each builds on the previous phase.

### Phase 1: Web Search Agent

```bash
./scripts/lifecycle/01-phase1-web-search.sh
```

- Creates branch `feature/phase1-web-search`
- Configures the agent with the `web_search` tool
- Evaluation runs 5 Phase 1 test cases
- Opens a PR — `evaluate.yml` triggers, deploys to TEST, runs eval

**After the eval passes, merge the PR.** `deploy-prod.yml` deploys to PROD.

### Phase 2: Add Code Interpreter

```bash
./scripts/lifecycle/02-phase2-code-interpreter.sh
```

- Creates branch `feature/phase2-code-interpreter` from updated `main`
- Adds `code_interpreter` tool alongside `web_search`
- Extends the system prompt with a `## Data Analysis` section
- Evaluation now runs all 8 test cases (Phase 1 + Phase 2) — checks for regressions
- Opens a PR

**After the eval passes, merge the PR.**

### Phase 3: Model Upgrade

```bash
./scripts/lifecycle/03-model-upgrade.sh
```

- Creates branch `chore/model-upgrade-gpt41`
- Updates the `GPT_DEPLOYMENT` GitHub variable to `gpt-4.1`
- Adds a model history entry in the agent config
- Opens a PR — the eval gate verifies the new model scores at or above thresholds

**After the eval passes, merge the PR.** The full lifecycle demo is complete.

### Lifecycle Flow Diagram

```
Phase 1 PR → eval gate → merge → prod deploy
                                      ↓
Phase 2 PR → eval gate → merge → prod deploy
                                      ↓
Phase 3 PR → eval gate → merge → prod deploy
```

## Teardown

Remove all Azure resources and GitHub configuration created by bootstrap:

```bash
./scripts/teardown.sh          # interactive confirmation prompt
./scripts/teardown.sh --yes    # skip confirmation
```

This deletes:
- The resource group (and all resources within — TEST project, PROD project, model deployments)
- Federated credentials and the App Registration
- All 7 GitHub repository variables
- The `.bootstrap-state.json` state file

## Manual Quick Start

If you prefer to set up infrastructure manually instead of using bootstrap:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Foundry endpoints and deployment names

# 3. Login to Azure
az login

# 4. Deploy to test
source .env  # or export vars manually
python scripts/deploy_agent.py --env test --semver 1.0.0 --tools web_search
```

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `evaluate.yml` | PR touching `agents/`, `prompts/`, `evals/` | Deploy to test, run eval, post results to PR |
| `deploy-prod.yml` | Push to `main` touching `agents/`, `prompts/` | Deploy to prod, commit artifact |
| `monitor.yml` | Daily cron (06:00 UTC) | Eval prod agent, open issue on drift |

## Evaluation

The eval gate uses `microsoft/ai-agent-evals@v3-beta` with four evaluators:

- **Task Adherence** (threshold: 0.80)
- **Relevance** (threshold: 0.75)
- **Groundedness** (threshold: 0.75)
- **Coherence** (threshold: 0.80)

## Rollback

```bash
python scripts/rollback_agent.py artifacts/tech-trends-agent-v1.1.0.json prod
```

Re-deploys the exact prompt, tools, and model from a saved artifact.

## Model Comparison

```bash
python scripts/compare_models.py --current gpt-4o-2024-11-20 --candidate gpt-4.1 --tools web_search
```

Deploys both model versions to test for side-by-side evaluation.

## Authentication

Uses GitHub OIDC federation — no secrets stored in the repository. The `bootstrap.sh` script
configures this automatically by creating an App Registration with federated credentials for
three GitHub Actions contexts:

| Credential | Subject | Used by |
|---|---|---|
| `github-main` | `repo:owner/repo:ref:refs/heads/main` | `deploy-prod.yml` |
| `github-pr` | `repo:owner/repo:pull_request` | `evaluate.yml` |
| `github-release` | `repo:owner/repo:ref:refs/tags/*` | Future release workflows |

For manual setup, create these federated credentials on an App Registration and assign
the `Azure AI User` and `Cognitive Services OpenAI User` roles scoped to your resource group.

## Running Tests

```bash
pytest tests/ -v
```
