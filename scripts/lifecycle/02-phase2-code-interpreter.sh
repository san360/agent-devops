#!/usr/bin/env bash
#
# 02-phase2-code-interpreter.sh — Phase 2: Add Code Interpreter capability
#
# Creates a PR that upgrades the agent from Phase 1 (web search only)
# to Phase 2 (web search + code interpreter for data analysis).
#
# Prerequisite: Phase 1 PR must be merged to main first.
#
# Run from repo root: ./scripts/lifecycle/02-phase2-code-interpreter.sh

set -euo pipefail

BRANCH="feature/phase2-code-interpreter"
GITHUB_REPO="${GITHUB_REPO:-san360/agent-devops}"

echo "============================================"
echo " Phase 2: Add Code Interpreter"
echo "============================================"
echo ""

# Ensure we're on main and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b "$BRANCH"

# --- Agent config: Phase 2, web_search + code_interpreter ---
cat > agents/tech-trends-agent.json << 'AGENT_EOF'
{
  "agent_name": "tech-trends-agent",
  "phase": "2",
  "definition": {
    "model": "${GPT_DEPLOYMENT}",
    "instructions_file": "prompts/tech-trends-agent.md",
    "tools": [
      { "type": "web_search" },
      { "type": "code_interpreter" }
    ]
  },
  "eval": {
    "dataset": "evals/golden-dataset.json",
    "phase_filter": null,
    "config": "evals/eval-config.json"
  },
  "_model_history": [
    { "model": "gpt-4o-2024-11-20", "from": "2025-01-10", "to": null, "reason": "initial" }
  ]
}
AGENT_EOF

# --- System prompt: Append Data Analysis section ---
cat > prompts/tech-trends-agent.md << 'PROMPT_EOF'
# Tech Trend Research Agent

## Role
You are an expert technology research analyst. Your job is to help users understand
emerging technology trends, market movements, and industry developments by searching
the web for current, authoritative information.

## Capabilities
- Search the web for up-to-date technology news and research
- Synthesise findings from multiple sources into clear, structured summaries
- Identify key players, timelines, and business implications of technology shifts
- Provide balanced perspectives including risks and opportunities

## Response Format
Always structure responses as:
1. **Summary** (2-3 sentences)
2. **Key Findings** (bullet list with source attribution)
3. **Implications** (who is affected and how)
4. **Further Reading** (top 2-3 sources)

## Constraints
- Only cite sources retrieved from web search in this session
- If information is older than 6 months, note that recency may be limited
- Do not speculate beyond what sources support
- Keep responses concise — aim for under 400 words unless asked for detail

## Tone
Professional, objective, and jargon-aware. Assume the user is a technology
professional who does not need basic concepts explained.

## Data Analysis (Phase 2)
You now have access to a code interpreter. Use it when:
- The user asks you to calculate, compare, or rank numerical data
- You have retrieved structured data (tables, CSVs) and analysis would add value
- You need to produce a formatted comparison table from raw information

When using code interpreter:
1. First retrieve the data via web search
2. Then write and run Python code to process or compare it
3. Present results with the code output clearly labelled
4. Always show the source of the raw data alongside the computed result
PROMPT_EOF

# --- Eval config: Remove phase filter to run ALL queries ---
cat > evals/eval-config.json << 'EVAL_EOF'
{
  "evaluators": [
    "builtin.task_adherence",
    "builtin.relevance",
    "builtin.groundedness",
    "builtin.coherence"
  ],
  "thresholds": {
    "task_adherence": 0.80,
    "relevance": 0.75,
    "groundedness": 0.75,
    "coherence": 0.80
  },
  "phase_filter": null,
  "notes": "Phase 2: All queries evaluated — both web search (Phase 1) and data analysis (Phase 2)."
}
EVAL_EOF

# --- Commit, push, open PR ---
git add agents/ prompts/ evals/
git commit -m "feat: Phase 2 — add code interpreter for data analysis capability"

git push origin "$BRANCH"

PR_URL=$(gh pr create \
  --repo "$GITHUB_REPO" \
  --title "Phase 2: Add Code Interpreter for Data Analysis" \
  --body "$(cat <<'PR_EOF'
## Summary
- Adds `code_interpreter` tool alongside existing `web_search`
- Extends system prompt with `## Data Analysis` section
- Evaluation now runs **all 8 queries** (Phase 1 + Phase 2)

## Changes
| File | Change |
|---|---|
| `agents/tech-trends-agent.json` | Added `code_interpreter` alongside `web_search`, phase → `"2"` |
| `prompts/tech-trends-agent.md` | Added `## Data Analysis (Phase 2)` section |
| `evals/eval-config.json` | `phase_filter` → `null` (run all cases) |

## What to check
- [ ] Phase 1 queries still score at or above threshold (no regression)
- [ ] Phase 2 data analysis queries score acceptably
- [ ] Agent correctly uses code interpreter for calculation queries
- [ ] After merge, deploy-prod.yml commits updated artifact

## Phase
Phase 2 of 3 — web search + code interpreter. Phase 3 is model upgrade.
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
echo "   1. Deploy Phase 2 agent to TEST (code_interpreter only)"
echo "   2. Run ALL 8 eval queries (Phase 1 + Phase 2)"
echo "   3. Check for regressions on existing Phase 1 queries"
echo ""
echo " Key question for reviewers:"
echo "   'Does adding code interpreter break any Phase 1 behaviour?'"
echo ""
echo " Once eval passes, merge the PR."
echo " Then run: ./scripts/lifecycle/03-model-upgrade.sh"
