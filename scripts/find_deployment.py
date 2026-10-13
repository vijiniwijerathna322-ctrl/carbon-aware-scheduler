"""Discover retained bundles only from the dedicated reviewed main publisher."""

import argparse
import json
import subprocess
from collections.abc import Callable
from typing import Any


def find_deployment(repository: str, region: str, lookup: Callable[[str], Any]) -> int | None:
    runs = lookup(
        f"repos/{repository}/actions/workflows/deployment-bundle.yml/runs"
        "?branch=main&status=success&per_page=30"
    )
    for run in runs.get("workflow_runs", []):
        if run["head_branch"] != "main" or run["event"] == "pull_request":
            continue
        if run["status"] != "completed" or run["conclusion"] != "success":
            continue
        artifacts = lookup(f"repos/{repository}/actions/runs/{run['id']}/artifacts")
        if any(
            a["name"] == f"monitoring-models-{region}" and not a["expired"]
            for a in artifacts.get("artifacts", [])
        ):
            return int(run["id"])
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--region", required=True)
    args = parser.parse_args()

    def lookup(path):
        return json.loads(subprocess.check_output(["gh", "api", path], text=True))

    selected = find_deployment(args.repository, args.region, lookup)
    print(selected or "")
