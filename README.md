# AI Foundry Prompt Agent — DevOps & Lifecycle Management

A complete CI/CD lifecycle for an Azure AI Foundry prompt agent, demonstrating
versioned prompts, tool changes, model upgrades, evaluation gates, and rollback.

## Agent: Technology Trend Research & Analysis

- **Phase 1:** Web search only (Bing Grounding)
- **Phase 2:** Web search + Code Interpreter for data analysis

## Repository Structure

```
agents/                  Agent config skeleton (JSON)
prompts/                 System prompt (Markdown)
evals/                   Golden dataset + evaluator config
scripts/                 Deploy, rollback, and model comparison scripts
infra/                   Bicep IaC for Foundry project
artifacts/               Generated deployment snapshots (post-deploy)
.github/workflows/       CI/CD pipelines
tests/                   Unit tests
```

## Prerequisites

- Python 3.12+
- Azure CLI (`az login`)
- An Azure AI Foundry project with a Bing Grounding connection
- An Azure OpenAI deployment (e.g. `gpt-4o-2024-11-20`)

## Quick Start

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
python scripts/deploy_agent.py --env test --semver 1.0.0 --tools bing_grounding
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
python scripts/compare_models.py --current gpt-4o-2024-11-20 --candidate gpt-4.1 --tools bing_grounding
```

Deploys both model versions to test for side-by-side evaluation.

## Authentication

Uses GitHub OIDC federation — no secrets stored. See the spec document for
detailed setup instructions.

## Running Tests

```bash
pytest tests/ -v
```
