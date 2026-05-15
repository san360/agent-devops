#!/usr/bin/env bash
#
# 01-phase1-web-search.sh — Phase 1: Initial agent with Bing Grounding only
#
# Creates a PR that sets the agent to Phase 1 configuration.
# The evaluate.yml workflow will trigger, deploy to TEST, and run evals.
#
# Run from repo root: ./scripts/lifecycle/01-phase1-web-search.sh

set -euo pipefail

BRANCH="feature/phase1-web-search"
GITHUB_REPO="${GITHUB_REPO:-san360/agent-devops}"

echo "============================================"
echo " Phase 1: Web Search Agent"
echo "============================================"
echo ""

# Ensure we're on main and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b "$BRANCH"

# --- Agent config: Phase 1, bing_grounding only ---
cat > agents/tech-trends-agent.json << 'AGENT_EOF'
{
  "agent_name": "tech-trends-agent",
  "phase": "1",
  "definition": {
    "model": "${GPT_DEPLOYMENT}",
    "instructions_file": "prompts/tech-trends-agent.md",
    "tools": [
      { "type": "bing_grounding" }
    ]
  },
  "eval": {
    "dataset": "evals/golden-dataset.jsonl",
    "phase_filter": "1",
    "config": "evals/eval-config.json"
  },
  "_model_history": [
    { "model": "gpt-4o-2024-11-20", "from": "2025-01-10", "to": null, "reason": "initial" }
  ]
}
AGENT_EOF

# --- System prompt: Phase 1 (web search only) ---
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
PROMPT_EOF

# --- Eval config: Phase 1 filter ---
cat > evals/eval-config.json << 'EVAL_EOF'
{
  "evaluators": [
    "TaskAdherenceEvaluator",
    "RelevanceEvaluator",
    "GroundednessEvaluator",
    "CoherenceEvaluator"
  ],
  "thresholds": {
    "task_adherence": 0.80,
    "relevance": 0.75,
    "groundedness": 0.75,
    "coherence": 0.80
  },
  "phase_filter": "1",
  "notes": "Phase 1: Only web search queries evaluated. Phase 2 data analysis queries excluded."
}
EVAL_EOF

# --- Commit, push, open PR ---
git add agents/ prompts/ evals/
git commit -m "feat: Phase 1 — tech trends agent with web search (Bing Grounding)"

git push origin "$BRANCH"

PR_URL=$(gh pr create \
  --repo "$GITHUB_REPO" \
  --title "Phase 1: Tech Trends Agent with Web Search" \
  --body "$(cat <<'PR_EOF'
## Summary
- Initial agent deployment with Bing Grounding (web search) capability
- System prompt defines structured research analyst behaviour
- Evaluation runs Phase 1 queries only (5 test cases)

## What to check
- [ ] evaluate.yml triggers and deploys to TEST
- [ ] All 4 evaluator scores meet thresholds
- [ ] PR comment shows eval results
- [ ] After merge, deploy-prod.yml fires and commits artifact

## Phase
Phase 1 of 3 — web search only. Phase 2 adds code interpreter.
PR_EOF
)" \
  --head "$BRANCH" \
  --base main)

echo ""
echo "============================================"
echo " PR created: $PR_URL"
echo "============================================"
echo ""
echo " The evaluate.yml workflow should now:"
echo "   1. Deploy agent to TEST project"
echo "   2. Run evaluation (Phase 1 queries only)"
echo "   3. Post results as a PR comment"
echo ""
echo " Once eval passes, merge the PR to trigger deploy-prod.yml."
echo " Then run: ./scripts/lifecycle/02-phase2-code-interpreter.sh"
