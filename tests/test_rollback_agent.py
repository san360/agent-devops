import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRollbackFromArtifact:
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_rollback_creates_new_version(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env, tmp_project, monkeypatch
    ):
        artifact_path, artifact_data = sample_artifact
        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG",
                            str(tmp_project / "agents" / "tech-trends-agent.json"))

        mock_agent = MagicMock()
        mock_agent.version = 10
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        result = rollback_from_artifact(artifact_path, "prod")

        assert result.version == 10
        MockClient.return_value.agents.create_version.assert_called_once()
        call_kwargs = MockClient.return_value.agents.create_version.call_args
        assert "ROLLBACK" in call_kwargs.kwargs["description"]
        assert artifact_data["foundry_version_id"] in call_kwargs.kwargs["description"]

    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_rollback_uses_correct_model(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env, tmp_project, monkeypatch
    ):
        artifact_path, artifact_data = sample_artifact
        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG",
                            str(tmp_project / "agents" / "tech-trends-agent.json"))

        mock_agent = MagicMock()
        mock_agent.version = 11
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        call_kwargs = MockClient.return_value.agents.create_version.call_args
        definition = call_kwargs.kwargs["definition"]
        assert definition.model == artifact_data["definition"]["model"]

    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_rollback_restores_agent_config(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env, tmp_project, monkeypatch
    ):
        artifact_path, artifact_data = sample_artifact
        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG",
                            str(tmp_project / "agents" / "tech-trends-agent.json"))

        mock_agent = MagicMock()
        mock_agent.version = 12
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        restored = json.loads((tmp_project / "agents" / "tech-trends-agent.json").read_text())
        assert restored["agent_name"] == "tech-trends-agent"
        assert restored["definition"]["model"] == artifact_data["definition"]["model"]
        assert restored["definition"]["tools"] == artifact_data["definition"]["tools"]


class TestRollbackToolReconstruction:
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_reconstructs_web_search_tool(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env, tmp_project, monkeypatch
    ):
        artifact_path, _ = sample_artifact
        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG",
                            str(tmp_project / "agents" / "tech-trends-agent.json"))

        mock_agent = MagicMock()
        mock_agent.version = 14
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        MockWebSearch.assert_called_once()

    @patch("scripts.rollback_agent.CodeInterpreterTool")
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_reconstructs_code_interpreter(
        self, MockWebSearch, MockClient, MockCred, MockCode,
        sample_artifact, mock_env, tmp_project, monkeypatch
    ):
        artifact_path, artifact_data = sample_artifact
        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG",
                            str(tmp_project / "agents" / "tech-trends-agent.json"))

        artifact_data["definition"]["tools"].append({"type": "code_interpreter"})
        with open(artifact_path, "w") as f:
            json.dump(artifact_data, f)

        mock_agent = MagicMock()
        mock_agent.version = 15
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        MockCode.assert_called_once()


class TestRestoreDefaults:
    def test_restore_defaults_copies_files(self, tmp_path, monkeypatch):
        # Set up default files
        (tmp_path / "agents").mkdir()
        (tmp_path / "prompts").mkdir()

        default_config = tmp_path / "agents" / "tech-trends-agent.default.json"
        default_config.write_text('{"agent_name": "tech-trends-agent", "definition": {"tools": []}}')

        default_prompt = tmp_path / "prompts" / "tech-trends-agent.default.md"
        default_prompt.write_text("# Default prompt")

        active_config = tmp_path / "agents" / "tech-trends-agent.json"
        active_config.write_text('{"agent_name": "tech-trends-agent", "definition": {"tools": [{"type": "web_search"}]}}')

        active_prompt = tmp_path / "prompts" / "tech-trends-agent.md"
        active_prompt.write_text("# Modified prompt")

        monkeypatch.setattr("scripts.rollback_agent.AGENT_CONFIG", str(active_config))
        monkeypatch.setattr("scripts.rollback_agent.AGENT_DEFAULT", str(default_config))
        monkeypatch.setattr("scripts.rollback_agent.PROMPT_FILE", str(active_prompt))
        monkeypatch.setattr("scripts.rollback_agent.PROMPT_DEFAULT", str(default_prompt))

        from scripts.rollback_agent import restore_defaults
        restore_defaults()

        assert json.loads(active_config.read_text())["definition"]["tools"] == []
        assert active_prompt.read_text() == "# Default prompt"
