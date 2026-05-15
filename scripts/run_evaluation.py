"""Run agent evaluation with create-once, run-many pattern.

On first run: creates an evaluation named after the agent.
On subsequent runs: reuses the existing evaluation and adds a new run.
Run name encodes the commit SHA and branch for traceability.

Usage:
    python scripts/run_evaluation.py \
        --agent-name tech-trends-agent \
        --agent-version 16 \
        --data-path evals/golden-dataset.json \
        --commit-sha abc1234 \
        --branch feature/my-branch
"""

import argparse
import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai.types.eval_create_params import DataSourceConfigCustom


POLLING_INTERVAL = 5


def find_existing_eval(openai_client, eval_name: str):
    """Search for an existing evaluation by name."""
    page = openai_client.evals.list(order="desc", limit=100)
    for eval_obj in page.data:
        if eval_obj.name == eval_name:
            return eval_obj
    return None


def build_testing_criteria(evaluators: list, deployment_name: str) -> list:
    """Build testing criteria for Azure AI evaluators."""
    criteria = []
    for evaluator_name in evaluators:
        display_name = evaluator_name.split(".")[-1] if "." in evaluator_name else evaluator_name
        criteria.append({
            "type": "azure_ai_evaluator",
            "name": display_name,
            "evaluator_name": evaluator_name,
            "initialization_parameters": {
                "deployment_name": deployment_name,
            },
            "data_mapping": {
                "response": "{{sample.output_text}}",
                "query": "{{item.query}}",
                "ground_truth": "{{item.ground_truth}}",
                "tool_calls": "{{sample.tool_calls}}",
                "tool_definitions": "{{sample.tool_definitions}}",
            },
        })
    return criteria


def create_evaluation(openai_client, eval_name: str, evaluators: list, deployment_name: str):
    """Create a new evaluation."""
    data_source_config = DataSourceConfigCustom(
        type="custom",
        item_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        include_sample_schema=True,
    )

    testing_criteria = build_testing_criteria(evaluators, deployment_name)

    eval_obj = openai_client.evals.create(
        name=eval_name,
        data_source_config=data_source_config,
        testing_criteria=testing_criteria,
    )
    print(f"Created new evaluation: {eval_obj.name} (id: {eval_obj.id})")
    return eval_obj


def create_eval_run(openai_client, project_client, eval_id: str, run_name: str,
                    agent_name: str, agent_version: str, data_path: str):
    """Create a run against an existing evaluation."""
    # Upload dataset
    jsonl_path = convert_to_jsonl(data_path)
    dataset = project_client.datasets.upload_file(
        name=f"{agent_name}-eval-data",
        version=str(int(time.time())),
        file_path=jsonl_path,
    )
    print(f"Uploaded dataset: {dataset.name} (version: {dataset.version})")

    data_source = {
        "type": "azure_ai_target_completions",
        "source": {
            "type": "file_id",
            "id": dataset.id,
        },
        "input_messages": {
            "type": "template",
            "template": [
                {"type": "message", "role": "user", "content": "{{item.query}}"}
            ],
        },
        "target": {
            "type": "azure_ai_agent",
            "name": agent_name,
            "version": agent_version,
        },
    }

    eval_run = openai_client.evals.runs.create(
        eval_id=eval_id,
        name=run_name,
        data_source=data_source,
    )
    print(f"Created evaluation run: {eval_run.id} (name: {run_name})")
    return eval_run


def convert_to_jsonl(data_path: str) -> str:
    """Convert JSON dataset to JSONL format for upload."""
    with open(data_path) as f:
        data = json.load(f)

    jsonl_path = data_path.replace(".json", ".jsonl")
    with open(jsonl_path, "w") as f:
        for item in data["data"]:
            f.write(json.dumps(item) + "\n")

    return jsonl_path


def wait_for_run(openai_client, eval_id: str, run_id: str):
    """Poll until the evaluation run completes."""
    print("Waiting for evaluation run to complete...")
    while True:
        run = openai_client.evals.runs.retrieve(run_id=run_id, eval_id=eval_id)
        if run.status in ("completed", "failed"):
            print(f"Run finished with status: {run.status}")
            return run
        time.sleep(POLLING_INTERVAL)


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluation (create-once pattern)")
    parser.add_argument("--agent-name", required=True, help="Agent name")
    parser.add_argument("--agent-version", required=True, help="Agent version")
    parser.add_argument("--data-path", required=True, help="Path to golden dataset JSON")
    parser.add_argument("--commit-sha", required=True, help="Git commit SHA (short)")
    parser.add_argument("--branch", required=True, help="Git branch name")
    args = parser.parse_args()

    endpoint = os.environ["FOUNDRY_TEST_ENDPOINT"]
    deployment_name = os.environ["GPT_DEPLOYMENT"]

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    openai_client = project_client.get_openai_client()

    # Load evaluators from dataset file
    with open(args.data_path) as f:
        input_data = json.load(f)
    evaluators = input_data.get("evaluators", [])

    # Evaluation name is based on agent name (stable across runs)
    eval_name = f"{args.agent_name}-eval"

    # Find or create the evaluation
    eval_obj = find_existing_eval(openai_client, eval_name)
    if eval_obj:
        print(f"Found existing evaluation: {eval_obj.name} (id: {eval_obj.id})")
    else:
        print(f"No evaluation found with name '{eval_name}', creating new one...")
        eval_obj = create_evaluation(openai_client, eval_name, evaluators, deployment_name)

    # Run name encodes commit and branch for traceability
    run_name = f"{args.branch}/{args.commit_sha}"

    # Create and wait for the evaluation run
    eval_run = create_eval_run(
        openai_client, project_client, eval_obj.id, run_name,
        args.agent_name, args.agent_version, args.data_path,
    )
    completed_run = wait_for_run(openai_client, eval_obj.id, eval_run.id)

    # Output results for GitHub Actions
    gh_output = os.environ.get("GITHUB_OUTPUT", "")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"eval_id={eval_obj.id}\n")
            f.write(f"eval_run_id={completed_run.id}\n")
            f.write(f"eval_run_status={completed_run.status}\n")
            report_url = getattr(completed_run, "report_url", "")
            f.write(f"eval_report_url={report_url}\n")

    if completed_run.status == "failed":
        print("ERROR: Evaluation run failed")
        raise SystemExit(1)

    print(f"Evaluation complete. Run: {completed_run.id}")


if __name__ == "__main__":
    main()
