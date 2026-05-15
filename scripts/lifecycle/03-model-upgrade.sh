#!/usr/bin/env bash
#
# 03-model-upgrade.sh — Model change: upgrade GPT deployment
#
# Creates a PR that updates the model from gpt-4o-2024-11-20 to gpt-4.1.
# The eval gate ensures the new model performs at least as well as the current one.
#
# Prerequisite: Phase 2 PR must be merged to main first.
#
# Run from repo root: ./scripts/lifecycle/03-model-upgrade.sh

set -euo pipefail

BRANCH="chore/model-upgrade-gpt41"
GITHUB_REPO="${GITHUB_REPO:-san360/agent-devops}"
NEW_MODEL="gpt-4.1"

echo "============================================"
echo " Model Upgrade: gpt-4o → $NEW_MODEL"
echo "============================================"
echo ""

# Ensure we're on main and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b "$BRANCH"

# --- Update GitHub variable to new model ---
echo "Updating GPT_DEPLOYMENT variable on $GITHUB_REPO..."
gh variable set GPT_DEPLOYMENT --body "$NEW_MODEL" --repo "$GITHUB_REPO"
echo "  GPT_DEPLOYMENT → $NEW_MODEL"

# --- Update agent config: add model history entry ---
python3 << 'PYEOF'
import json
from datetime import date

cfg = json.load(open("agents/tech-trends-agent.json"))

# Close the current model history entry
for entry in cfg.get("_model_history", []):
    if entry.get("to") is None:
        entry["to"] = date.today().isoformat()

# Add new model entry
cfg.setdefault("_model_history", []).append({
    "model": "gpt-4.1",
    "from": date.today().isoformat(),
    "to": None,
    "reason": "quality improvement, eval gated"
})

with open("agents/tech-trends-agent.json", "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PYEOF

# --- Commit, push, open PR ---
git add agents/
git commit -m "chore: upgrade model from gpt-4o-2024-11-20 to $NEW_MODEL"

git push origin "$BRANCH"

PR_URL=$(gh pr create \
  --repo "$GITHUB_REPO" \
  --title "Model Upgrade: gpt-4o-2024-11-20 → $NEW_MODEL" \
  --body "$(cat <<PR_EOF
## Summary
- Upgrades the agent model from \`gpt-4o-2024-11-20\` to \`$NEW_MODEL\`
- GitHub variable \`GPT_DEPLOYMENT\` updated to \`$NEW_MODEL\`
- Model history annotation updated in agent config

## Why this needs an eval gate
Swapping models is a behaviour change. The new model may:
- Format responses differently
- Handle tool calls differently
- Score higher or lower on evaluation dimensions

The eval workflow will deploy with the new model and verify all scores
meet thresholds before this can be merged.

## Changes
| File | Change |
|---|---|
| \`agents/tech-trends-agent.json\` | Updated \`_model_history\` annotation |
| GitHub variable \`GPT_DEPLOYMENT\` | \`gpt-4o-2024-11-20\` → \`$NEW_MODEL\` |

## What to check
- [ ] All 4 evaluator scores meet or exceed current thresholds
- [ ] No regression on Phase 1 or Phase 2 queries
- [ ] Response format still follows the structured template
- [ ] Tool calls (web search + code interpreter) still work correctly

## Phase
Phase 3 of 3 — model upgrade. Lifecycle demo complete after merge.
PR_EOF
)" \
  --head "$BRANCH" \
  --base main)

echo ""
echo "============================================"
echo " PR created: $PR_URL"
echo "============================================"
echo ""
echo " The evaluate.yml workflow will now:"
echo "   1. Deploy agent with $NEW_MODEL to TEST"
echo "   2. Run full evaluation suite (all 8 queries)"
echo "   3. Compare scores against thresholds"
echo ""
echo " If the new model scores equal or better on all dimensions,"
echo " merge the PR. deploy-prod.yml will deploy to production."
echo ""
echo " After this PR merges, the full lifecycle demo is complete:"
echo "   Phase 1: Web search agent           [done]"
echo "   Phase 2: + Code interpreter          [done]"
echo "   Phase 3: Model upgrade               [this PR]"
