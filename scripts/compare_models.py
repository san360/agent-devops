"""Side-by-side model comparison: deploy two agent versions with different models
and evaluate both to determine which performs better.

Usage:
    python scripts/compare_models.py --current gpt-4o-2024-11-20 --candidate gpt-4.1 --tools bing_grounding
"""

import argparse
import os

from scripts.deploy_agent import deploy_agent


LABEL_CURRENT = "model-current"
LABEL_CANDIDATE = "model-candidate"


def compare_models(current_model: str, candidate_model: str, tools: list):
    original_model = os.environ.get("GPT_DEPLOYMENT")

    results = {}
    for label, model in [
        (LABEL_CURRENT, current_model),
        (LABEL_CANDIDATE, candidate_model),
    ]:
        os.environ["GPT_DEPLOYMENT"] = model
        artifact, path = deploy_agent(
            env="test", tools=tools, semver=f"0.0.0-{label}"
        )
        results[label] = {"artifact": artifact, "path": path}
        print(f"Deployed {label} ({model}) -> {path}")

    if original_model is not None:
        os.environ["GPT_DEPLOYMENT"] = original_model

    print("\nBoth versions deployed to test. Run evaluation with:")
    print('  agent-ids: "tech-trends-agent:latest,tech-trends-agent:prev"')
    print('  baseline-agent-id: "tech-trends-agent:prev"')
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Compare two models side-by-side")
    p.add_argument("--current", required=True, help="Current model deployment name")
    p.add_argument("--candidate", required=True, help="Candidate model deployment name")
    p.add_argument(
        "--tools",
        default="bing_grounding",
        help="comma-separated tool list",
    )
    args = p.parse_args()

    tools = [{"type": t.strip()} for t in args.tools.split(",")]
    compare_models(args.current, args.candidate, tools)
