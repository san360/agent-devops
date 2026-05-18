"""Rollback a Foundry agent to a previous version using a saved artifact.

Usage:
    python scripts/rollback_agent.py artifacts/tech-trends-agent-v1.1.0.json prod
"""

import hashlib
import json
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeInterpreterTool,
    PromptAgentDefinition,
    WebSearchTool,
)
from azure.identity import DefaultAzureCredential


def rollback_from_artifact(artifact_path: str, env: str):
    artifact = json.load(open(artifact_path))
    env_var = f"FOUNDRY_{env.upper()}_ENDPOINT"
    endpoint = os.environ.get(env_var)
    if not endpoint:
        print(f"ERROR: Environment variable '{env_var}' is not set.")
        print("Please add it to your .env file (see .env.example) and run: source .env")
        sys.exit(1)
    client = AIProjectClient(
        endpoint=endpoint, credential=DefaultAzureCredential()
    )

    prompt_path = artifact["definition"]["instructions_file"]
    instructions = open(prompt_path).read()

    actual_hash = "sha256:" + hashlib.sha256(open(prompt_path, "rb").read()).hexdigest()
    if actual_hash != artifact["definition"]["instructions_hash"]:
        print(
            "WARNING: prompt file hash does not match artifact. "
            "The prompt may have changed since this artifact was created."
        )

    tools = []
    for t in artifact["definition"]["tools"]:
        if t["type"] == "web_search":
            tools.append(WebSearchTool())
        elif t["type"] == "code_interpreter":
            tools.append(CodeInterpreterTool())

    agent = client.agents.create_version(
        agent_name=artifact["agent_name"],
        description=(
            f"ROLLBACK from {artifact['foundry_version_id']} | "
            f"{artifact['description']}"
        ),
        definition=PromptAgentDefinition(
            model=artifact["definition"]["model"],
            instructions=instructions,
            tools=tools,
        ),
    )
    print(
        f"Rolled back. New version: {agent.version} "
        f"(re-deployed from {artifact['foundry_version_id']})"
    )
    return agent


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/rollback_agent.py <artifact.json> <env>")
        sys.exit(1)
    rollback_from_artifact(sys.argv[1], sys.argv[2])
