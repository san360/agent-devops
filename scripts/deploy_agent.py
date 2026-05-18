"""Deploy the tech-trends-agent to an Azure AI Foundry project.

Usage:
    python scripts/deploy_agent.py --env test --semver 1.0.0 --tools web_search
    python scripts/deploy_agent.py --env prod --semver 1.2.0 --tools web_search,code_interpreter
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeInterpreterTool,
    PromptAgentDefinition,
    WebSearchTool,
)
from azure.identity import DefaultAzureCredential


def get_short_sha():
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"]
    ).decode().strip()


def get_full_sha():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"]
    ).decode().strip()


def hash_file(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def build_sdk_tools(tools):
    sdk_tools = []
    for t in tools:
        if t["type"] == "web_search":
            sdk_tools.append(WebSearchTool())
        elif t["type"] == "code_interpreter":
            sdk_tools.append(CodeInterpreterTool())
    return sdk_tools


def deploy_agent(env: str, tools: list, semver: str):
    env_var = f"FOUNDRY_{env.upper()}_ENDPOINT"
    endpoint = os.environ.get(env_var)
    if not endpoint:
        print(f"ERROR: Environment variable '{env_var}' is not set.")
        print("Please add it to your .env file (see .env.example) and run: source .env")
        sys.exit(1)
    model = os.environ.get("GPT_DEPLOYMENT")
    if not model:
        print("ERROR: Environment variable 'GPT_DEPLOYMENT' is not set.")
        print("Please add it to your .env file (see .env.example) and run: source .env")
        sys.exit(1)

    prompt_path = "prompts/tech-trends-agent.md"
    instructions = open(prompt_path).read()

    short_sha = get_short_sha()
    full_sha = get_full_sha()
    tool_names = ",".join(t["type"] for t in tools)
    description = (
        f"Tech Trend Research Agent | tools: {tool_names} | "
        f"model: {model} | commit: {short_sha} | v{semver}"
    )

    client = AIProjectClient(
        endpoint=endpoint, credential=DefaultAzureCredential()
    )

    sdk_tools = build_sdk_tools(tools)

    agent = client.agents.create_version(
        agent_name="tech-trends-agent",
        description=description,
        definition=PromptAgentDefinition(
            model=model,
            instructions=instructions,
            tools=sdk_tools,
        ),
    )

    artifact = {
        "artifact_schema": "1.0",
        "agent_name": "tech-trends-agent",
        "foundry_version_id": f"tech-trends-agent:{agent.version}",
        "semver": semver,
        "git": {
            "commit_sha": full_sha,
            "short_sha": short_sha,
            "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
            "tag": os.environ.get("GITHUB_REF", "").replace("refs/tags/", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "definition": {
            "model": model,
            "instructions_file": prompt_path,
            "instructions_hash": hash_file(prompt_path),
            "tools": tools,
        },
        "description": description,
        "deployment": {
            "environment": env,
            "foundry_endpoint": endpoint,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "deployed_by": "github-actions",
        },
    }

    artifact_path = f"artifacts/tech-trends-agent-v{semver}.json"
    os.makedirs("artifacts", exist_ok=True)
    with open(artifact_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"Deployed {agent.version} | artifact -> {artifact_path}")

    # Output for GitHub Actions
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"agent_version={agent.version}\n")

    return artifact, artifact_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Deploy tech-trends-agent to Foundry")
    p.add_argument("--env", default="test", choices=["test", "prod"])
    p.add_argument("--semver", default="0.0.1")
    p.add_argument(
        "--tools",
        default="web_search",
        help="comma-separated: web_search,code_interpreter",
    )
    args = p.parse_args()

    tools = [{"type": t.strip()} for t in args.tools.split(",") if t.strip()]
    deploy_agent(args.env, tools, args.semver)
