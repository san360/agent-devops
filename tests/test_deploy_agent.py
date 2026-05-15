import hashlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestGetShortSha:
    @patch("scripts.deploy_agent.subprocess.check_output")
    def test_returns_short_sha(self, mock_subprocess):
        mock_subprocess.return_value = b"a3f9c12\n"
        from scripts.deploy_agent import get_short_sha
        assert get_short_sha() == "a3f9c12"


class TestGetFullSha:
    @patch("scripts.deploy_agent.subprocess.check_output")
    def test_returns_full_sha(self, mock_subprocess):
        mock_subprocess.return_value = b"a3f9c12b8e4d1f6a9c2e5b7d0f3a8c1e4b7d9f2a\n"
        from scripts.deploy_agent import get_full_sha
        assert get_full_sha() == "a3f9c12b8e4d1f6a9c2e5b7d0f3a8c1e4b7d9f2a"


class TestHashFile:
    def test_produces_sha256_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
        from scripts.deploy_agent import hash_file
        assert hash_file(str(f)) == expected


class TestBuildSdkTools:
    @patch("scripts.deploy_agent.BingGroundingTool")
    def test_builds_bing_tool(self, MockBing):
        from scripts.deploy_agent import build_sdk_tools
        tools = [{"type": "bing_grounding"}]
        result = build_sdk_tools(tools, "my-conn")
        MockBing.assert_called_once_with(connection_id="my-conn")
        assert len(result) == 1

    @patch("scripts.deploy_agent.CodeInterpreterTool")
    @patch("scripts.deploy_agent.BingGroundingTool")
    def test_builds_multiple_tools(self, MockBing, MockCode):
        from scripts.deploy_agent import build_sdk_tools
        tools = [{"type": "bing_grounding"}, {"type": "code_interpreter"}]
        result = build_sdk_tools(tools, "conn")
        assert len(result) == 2

    @patch("scripts.deploy_agent.BingGroundingTool")
    def test_ignores_unknown_tool_type(self, MockBing):
        from scripts.deploy_agent import build_sdk_tools
        tools = [{"type": "unknown_tool"}]
        result = build_sdk_tools(tools, "conn")
        assert len(result) == 0


class TestDeployAgent:
    @patch("scripts.deploy_agent.DefaultAzureCredential")
    @patch("scripts.deploy_agent.AIProjectClient")
    @patch("scripts.deploy_agent.build_sdk_tools")
    @patch("scripts.deploy_agent.get_full_sha", return_value="a" * 40)
    @patch("scripts.deploy_agent.get_short_sha", return_value="a" * 7)
    def test_creates_artifact_with_correct_schema(
        self, mock_short, mock_full, mock_build_tools,
        MockClient, MockCred, tmp_project, mock_env
    ):
        mock_agent = MagicMock()
        mock_agent.version = 42
        MockClient.return_value.agents.create_version.return_value = mock_agent
        mock_build_tools.return_value = []

        old_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            from scripts.deploy_agent import deploy_agent
            artifact, path = deploy_agent(
                env="test",
                tools=[{"type": "bing_grounding"}],
                semver="1.0.0",
            )
        finally:
            os.chdir(old_cwd)

        assert artifact["artifact_schema"] == "1.0"
        assert artifact["agent_name"] == "tech-trends-agent"
        assert artifact["foundry_version_id"] == "tech-trends-agent:42"
        assert artifact["semver"] == "1.0.0"
        assert artifact["git"]["commit_sha"] == "a" * 40
        assert artifact["git"]["short_sha"] == "a" * 7
        assert artifact["definition"]["model"] == "gpt-4o-2024-11-20"
        assert artifact["definition"]["tools"] == [{"type": "bing_grounding"}]
        assert artifact["definition"]["instructions_hash"].startswith("sha256:")
        assert artifact["deployment"]["environment"] == "test"

    @patch("scripts.deploy_agent.DefaultAzureCredential")
    @patch("scripts.deploy_agent.AIProjectClient")
    @patch("scripts.deploy_agent.build_sdk_tools")
    @patch("scripts.deploy_agent.get_full_sha", return_value="b" * 40)
    @patch("scripts.deploy_agent.get_short_sha", return_value="b" * 7)
    def test_writes_artifact_file_to_disk(
        self, mock_short, mock_full, mock_build_tools,
        MockClient, MockCred, tmp_project, mock_env
    ):
        mock_agent = MagicMock()
        mock_agent.version = 1
        MockClient.return_value.agents.create_version.return_value = mock_agent
        mock_build_tools.return_value = []

        old_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            from scripts.deploy_agent import deploy_agent
            artifact, path = deploy_agent(
                env="test",
                tools=[{"type": "bing_grounding"}],
                semver="2.0.0",
            )
        finally:
            os.chdir(old_cwd)

        assert os.path.exists(os.path.join(str(tmp_project), path))
        written = json.load(open(os.path.join(str(tmp_project), path)))
        assert written["semver"] == "2.0.0"

    @patch("scripts.deploy_agent.DefaultAzureCredential")
    @patch("scripts.deploy_agent.AIProjectClient")
    @patch("scripts.deploy_agent.build_sdk_tools")
    @patch("scripts.deploy_agent.get_full_sha", return_value="c" * 40)
    @patch("scripts.deploy_agent.get_short_sha", return_value="c" * 7)
    def test_description_contains_metadata(
        self, mock_short, mock_full, mock_build_tools,
        MockClient, MockCred, tmp_project, mock_env
    ):
        mock_agent = MagicMock()
        mock_agent.version = 3
        MockClient.return_value.agents.create_version.return_value = mock_agent
        mock_build_tools.return_value = []

        old_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            from scripts.deploy_agent import deploy_agent
            artifact, _ = deploy_agent(
                env="test",
                tools=[{"type": "bing_grounding"}, {"type": "code_interpreter"}],
                semver="1.1.0",
            )
        finally:
            os.chdir(old_cwd)

        desc = artifact["description"]
        assert "bing_grounding,code_interpreter" in desc
        assert "gpt-4o-2024-11-20" in desc
        assert "v1.1.0" in desc
        assert "c" * 7 in desc
