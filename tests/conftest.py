import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project layout in a temp directory."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "tech-trends-agent.md"
    prompt_file.write_text("# Test prompt\nYou are a test agent.")

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_config = agents_dir / "tech-trends-agent.json"
    agent_config.write_text(json.dumps({
        "agent_name": "tech-trends-agent",
        "phase": "1",
        "definition": {
            "model": "${GPT_DEPLOYMENT}",
            "instructions_file": "prompts/tech-trends-agent.md",
            "tools": [{"type": "bing_grounding"}],
        },
        "eval": {
            "dataset": "evals/golden-dataset.jsonl",
            "phase_filter": "1",
            "config": "evals/eval-config.json",
        },
    }))

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    return tmp_path


@pytest.fixture
def mock_env(tmp_project):
    """Set required environment variables for deploy/rollback."""
    env = {
        "FOUNDRY_TEST_ENDPOINT": "https://test.endpoint.example.com",
        "FOUNDRY_PROD_ENDPOINT": "https://prod.endpoint.example.com",
        "GPT_DEPLOYMENT": "gpt-4o-2024-11-20",
        "BING_CONNECTION_NAME": "bing-grounding",
        "GITHUB_REF_NAME": "main",
        "GITHUB_REF": "refs/tags/v1.0.0",
    }
    with patch.dict(os.environ, env):
        yield env


@pytest.fixture
def mock_agent():
    """Mock Foundry agent response."""
    agent = MagicMock()
    agent.version = 7
    return agent


@pytest.fixture
def mock_ai_client(mock_agent):
    """Mock AIProjectClient with agents.create_version."""
    client = MagicMock()
    client.agents.create_version.return_value = mock_agent
    return client


@pytest.fixture
def sample_artifact(tmp_project):
    """Write and return a sample artifact file."""
    artifact = {
        "artifact_schema": "1.0",
        "agent_name": "tech-trends-agent",
        "foundry_version_id": "tech-trends-agent:5",
        "semver": "1.0.0",
        "git": {
            "commit_sha": "a" * 40,
            "short_sha": "a" * 7,
            "branch": "main",
            "tag": "v1.0.0",
            "timestamp": "2025-05-14T10:32:00Z",
        },
        "definition": {
            "model": "gpt-4o-2024-11-20",
            "instructions_file": str(tmp_project / "prompts" / "tech-trends-agent.md"),
            "instructions_hash": "",
            "tools": [{"type": "bing_grounding"}],
        },
        "description": "Tech Trend Research Agent | tools: bing_grounding | model: gpt-4o-2024-11-20 | commit: aaaaaaa | v1.0.0",
        "deployment": {
            "environment": "prod",
            "foundry_endpoint": "https://prod.endpoint.example.com",
            "deployed_at": "2025-05-14T10:50:00Z",
            "deployed_by": "github-actions",
        },
    }
    import hashlib
    prompt_content = (tmp_project / "prompts" / "tech-trends-agent.md").read_bytes()
    artifact["definition"]["instructions_hash"] = (
        "sha256:" + hashlib.sha256(prompt_content).hexdigest()
    )
    artifact_path = tmp_project / "artifacts" / "tech-trends-agent-v1.0.0.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))
    return str(artifact_path), artifact
