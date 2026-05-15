import os
from unittest.mock import MagicMock, patch

import pytest


class TestCompareModels:
    @patch("scripts.compare_models.deploy_agent")
    def test_deploys_both_models(self, mock_deploy, mock_env):
        mock_deploy.return_value = ({"semver": "test"}, "artifacts/test.json")

        from scripts.compare_models import compare_models
        results = compare_models(
            current_model="gpt-4o-2024-11-20",
            candidate_model="gpt-4.1",
            tools=[{"type": "bing_grounding"}],
        )

        assert mock_deploy.call_count == 2
        assert "model-current" in results
        assert "model-candidate" in results

    @patch("scripts.compare_models.deploy_agent")
    def test_sets_model_env_for_each_deploy(self, mock_deploy, mock_env):
        models_seen = []

        def capture_model(*args, **kwargs):
            models_seen.append(os.environ["GPT_DEPLOYMENT"])
            return ({"semver": "test"}, "artifacts/test.json")

        mock_deploy.side_effect = capture_model

        from scripts.compare_models import compare_models
        compare_models(
            current_model="model-a",
            candidate_model="model-b",
            tools=[{"type": "bing_grounding"}],
        )

        assert models_seen == ["model-a", "model-b"]

    @patch("scripts.compare_models.deploy_agent")
    def test_restores_original_env(self, mock_deploy, mock_env):
        mock_deploy.return_value = ({"semver": "test"}, "artifacts/test.json")
        original = os.environ["GPT_DEPLOYMENT"]

        from scripts.compare_models import compare_models
        compare_models(
            current_model="new-a",
            candidate_model="new-b",
            tools=[{"type": "bing_grounding"}],
        )

        assert os.environ["GPT_DEPLOYMENT"] == original

    @patch("scripts.compare_models.deploy_agent")
    def test_uses_correct_semver_labels(self, mock_deploy, mock_env):
        semvers_seen = []

        def capture_semver(*args, **kwargs):
            semvers_seen.append(kwargs.get("semver", args[2] if len(args) > 2 else None))
            return ({"semver": "test"}, "artifacts/test.json")

        mock_deploy.side_effect = capture_semver

        from scripts.compare_models import compare_models
        compare_models(
            current_model="a",
            candidate_model="b",
            tools=[{"type": "bing_grounding"}],
        )

        assert semvers_seen == ["0.0.0-model-current", "0.0.0-model-candidate"]
