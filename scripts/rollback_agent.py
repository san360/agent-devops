"""Rollback a Foundry agent to its default definition or a previous artifact.

Restores the agent config and prompt from default baseline files in the repo,
then re-deploys to Foundry.

Usage:
    python scripts/rollback_agent.py <artifact.json> <env>
    python scripts/rollback_agent.py --default <env>
"""

import json
import os
import shutil
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeInterpreterTool,
    PromptAgentDefinition,
    WebSearchTool,
)
from azure.identity import DefaultAzureCredential

AGENT_CONFIG = "agents/tech-trends-agent.json"
AGENT_DEFAULT = "agents/tech-trends-agent.default.json"
PROMPT_FILE = "prompts/tech-trends-agent.md"
PROMPT_DEFAULT = "prompts/tech-trends-agent.default.md"


def restore_defaults():
    """Copy default agent config and prompt over the active files."""
    shutil.copy(AGENT_DEFAULT, AGENT_CONFIG)
    print(f"Restored agent config from {AGENT_DEFAULT}")
    shutil.copy(PROMPT_DEFAULT, PROMPT_FILE)
    print(f"Restored prompt from {PROMPT_DEFAULT}")


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

    # Restore agent config and prompt from artifact's definition
    agent_config = {
        "agent_name": artifact["agent_name"],
        "definition": artifact["definition"],
        "eval": artifact.get("eval", {
            "dataset": "evals/golden-dataset.json",
            "phase_filter": None,
            "config": "evals/eval-config.json",
        }),
    }
    with open(AGENT_CONFIG, "w") as f:
        json.dump(agent_config, f, indent=2)
        f.write("\n")
    print(f"Restored agent config from artifact: {AGENT_CONFIG}")

    # Read prompt content from disk (prompt file stays as-is from artifact era)
    prompt_path = artifact["definition"]["instructions_file"]
    instructions = open(prompt_path).read()

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
        print("Usage: python scripts/rollback_agent.py <artifact.json|--default> <env>")
        sys.exit(1)

    if sys.argv[1] == "--default":
        restore_defaults()
        # Load the default config to re-deploy
        rollback_config = json.load(open(AGENT_DEFAULT))
        # Create a minimal artifact-like structure for rollback
        artifact_path = AGENT_DEFAULT
        env = sys.argv[2]
        env_var = f"FOUNDRY_{env.upper()}_ENDPOINT"
        endpoint = os.environ.get(env_var)
        if not endpoint:
            print(f"ERROR: Environment variable '{env_var}' is not set.")
            sys.exit(1)
        client = AIProjectClient(
            endpoint=endpoint, credential=DefaultAzureCredential()
        )
        instructions = open(PROMPT_DEFAULT).read()
        agent = client.agents.create_version(
            agent_name=rollback_config["agent_name"],
            description="ROLLBACK to default baseline",
            definition=PromptAgentDefinition(
                model=rollback_config["definition"]["model"],
                instructions=instructions,
                tools=[],
            ),
        )
        print(f"Rolled back to default. New version: {agent.version}")
    else:
        rollback_from_artifact(sys.argv[1], sys.argv[2])
