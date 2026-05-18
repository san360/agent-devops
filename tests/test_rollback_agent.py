import hashlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestRollbackFromArtifact:
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_rollback_creates_new_version(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env
    ):
        artifact_path, artifact_data = sample_artifact

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
        sample_artifact, mock_env
    ):
        artifact_path, artifact_data = sample_artifact

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
    def test_rollback_warns_on_hash_mismatch(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env, tmp_project, capsys
    ):
        artifact_path, artifact_data = sample_artifact

        prompt_file = tmp_project / "prompts" / "tech-trends-agent.md"
        prompt_file.write_text("# Changed prompt\nThis is different now.")

        artifact_data["definition"]["instructions_file"] = str(prompt_file)
        with open(artifact_path, "w") as f:
            json.dump(artifact_data, f)

        mock_agent = MagicMock()
        mock_agent.version = 12
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    @patch("scripts.rollback_agent.restore_prompt_from_git")
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_rollback_no_warning_when_hash_matches(
        self, MockWebSearch, MockClient, MockCred, mock_restore,
        sample_artifact, mock_env, capsys
    ):
        artifact_path, artifact_data = sample_artifact

        # Simulate successful git restore with matching content
        prompt_path = artifact_data["definition"]["instructions_file"]
        prompt_content = open(prompt_path).read()
        mock_restore.return_value = prompt_content

        mock_agent = MagicMock()
        mock_agent.version = 13
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        captured = capsys.readouterr()
        assert "WARNING" not in captured.out
        assert "Restored prompt file" in captured.out


class TestRollbackToolReconstruction:
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_reconstructs_web_search_tool(
        self, MockWebSearch, MockClient, MockCred,
        sample_artifact, mock_env
    ):
        artifact_path, _ = sample_artifact

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
        sample_artifact, mock_env
    ):
        artifact_path, artifact_data = sample_artifact

        artifact_data["definition"]["tools"].append({"type": "code_interpreter"})
        with open(artifact_path, "w") as f:
            json.dump(artifact_data, f)

        mock_agent = MagicMock()
        mock_agent.version = 15
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        MockCode.assert_called_once()


class TestRollbackPromptRestoration:
    @patch("scripts.rollback_agent.restore_prompt_from_git")
    @patch("scripts.rollback_agent.DefaultAzureCredential")
    @patch("scripts.rollback_agent.AIProjectClient")
    @patch("scripts.rollback_agent.WebSearchTool")
    def test_restores_prompt_file_from_git(
        self, MockWebSearch, MockClient, MockCred, mock_restore,
        sample_artifact, mock_env, tmp_project
    ):
        artifact_path, artifact_data = sample_artifact

        # Current file has Phase 2 content
        prompt_file = tmp_project / "prompts" / "tech-trends-agent.md"
        prompt_file.write_text("# Phase 2 prompt\nWith data analysis.")

        # Git restore returns the original Phase 1 content
        original_content = "# Phase 1 prompt\nWeb search only."
        mock_restore.return_value = original_content

        mock_agent = MagicMock()
        mock_agent.version = 20
        MockClient.return_value.agents.create_version.return_value = mock_agent

        from scripts.rollback_agent import rollback_from_artifact
        rollback_from_artifact(artifact_path, "prod")

        # Verify the prompt file was restored on disk
        assert prompt_file.read_text() == original_content

        # Verify the restored content was sent to Foundry
        call_kwargs = MockClient.return_value.agents.create_version.call_args
        definition = call_kwargs.kwargs["definition"]
        assert definition.instructions == original_content
