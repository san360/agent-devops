# Artifacts Folder

## Purpose

The `artifacts/` folder is the **immutable deployment ledger** for the agent. Every time `deploy-prod.yml` deploys a new agent version to production, it commits a versioned JSON artifact here. This creates a git-native audit trail that answers:

- **What** was deployed (model, tools, prompt hash)
- **When** it was deployed (timestamp)
- **Where** it was deployed (which Foundry endpoint/environment)
- **Who** deployed it (CI pipeline or human)
- **Which code** produced it (git commit SHA, branch, tag)

## Why It Matters

| Concern | How Artifacts Help |
|---------|-------------------|
| **Rollback** | `rollback_agent.py` reads an artifact to reconstruct the exact agent definition (model + tools + prompt from that commit) and re-deploys it |
| **Auditability** | Each artifact is committed to `main` with `[skip ci]`, creating a permanent git history of every production deployment |
| **Drift Detection** | The `instructions_hash` field lets the rollback script verify whether the prompt file has changed since deployment |
| **Reproducibility** | The `git.commit_sha` field pins the exact source code state, enabling `git show <sha>:<file>` to retrieve any file as it was at deploy time |
| **Versioning** | `semver` + `foundry_version_id` map human-readable versions to Foundry's internal version numbers |

## Artifact Schema

```json
{
  "artifact_schema": "1.0",
  "agent_name": "tech-trends-agent",
  "foundry_version_id": "tech-trends-agent:6",
  "semver": "1.0.1",
  "git": {
    "commit_sha": "full 40-char SHA",
    "short_sha": "7-char SHA",
    "branch": "main",
    "tag": "refs/tags/v1.0.1 (if tagged)",
    "timestamp": "ISO-8601 UTC"
  },
  "definition": {
    "model": "gpt-4.1",
    "instructions_file": "prompts/tech-trends-agent.md",
    "instructions_hash": "sha256:<hex>",
    "tools": [{"type": "web_search"}, {"type": "code_interpreter"}]
  },
  "description": "human-readable summary",
  "deployment": {
    "environment": "prod",
    "foundry_endpoint": "https://...",
    "deployed_at": "ISO-8601 UTC",
    "deployed_by": "github-actions"
  }
}
```

## How to Rollback

To roll back production to a previous known-good version:

```bash
# Roll back to v1.0.0 (Phase 1: web_search only, gpt-4o model)
python scripts/rollback_agent.py artifacts/tech-trends-agent-v1.0.0.json prod
```

This will:
1. Retrieve the prompt file from git commit `b602722` (the exact state when v1.0.0 was deployed)
2. Restore `prompts/tech-trends-agent.md` on disk to that version
3. Re-deploy the agent to Foundry with the original model, tools, and instructions
4. Print the new Foundry version number

## Current Artifacts

| File | Version | Model | Tools | Environment | Deployed |
|------|---------|-------|-------|-------------|----------|
| `tech-trends-agent-v1.0.0.json` | v1.0.0 | gpt-4o | none | test | 2026-05-15 |
| `tech-trends-agent-v1.0.1.json` | v1.0.1 | gpt-4.1 | web_search, code_interpreter | prod | 2026-05-18 |

## Which Version to Use for Rollback

- **To undo Phase 3 (model upgrade)**: There is no intermediate artifact between Phase 2 merge and Phase 3 merge since both deployed as `v1.0.1`. To revert just the model, re-run deploy with `GPT_DEPLOYMENT=gpt-4o-2024-11-20`.
- **To undo everything back to initial state**: Use `tech-trends-agent-v1.0.0.json` — this has no tools and the initial prompt.
- **For production incidents**: Always roll back to the most recent artifact where production was stable. Check the `deployment.environment` field to ensure it's a `prod` artifact.

> **Note**: The deploy-prod workflow only fires on merges to `main` that touch `agents/` or `prompts/`. Each merge produces one artifact. If you need finer-grained rollback points, tag releases and use semver-based artifact naming.
