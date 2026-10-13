from pathlib import Path
from runpy import run_path

helper = run_path(str(Path(__file__).resolve().parents[2] / "scripts/find_deployment.py"))[
    "find_deployment"
]


def test_selects_only_retained_main_bundle():
    runs = [
        {
            "id": 1,
            "head_branch": "main",
            "event": "pull_request",
            "status": "completed",
            "conclusion": "success",
        },
        {
            "id": 2,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        },
        {
            "id": 3,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        },
    ]

    def lookup(path):
        if "workflows/" in path:
            return {"workflow_runs": runs}
        expired = "/runs/2/" in path
        return {"artifacts": [{"name": "monitoring-models-CISO", "expired": expired}]}

    assert helper("owner/repo", "CISO", lookup) == 3  # noqa: PLR2004


def test_missing_region_has_no_implicit_other_region_fallback():
    def lookup(path):
        if "workflows/" in path:
            return {
                "workflow_runs": [
                    {
                        "id": 1,
                        "head_branch": "main",
                        "event": "push",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            }
        return {"artifacts": [{"name": "monitoring-models-CISO", "expired": False}]}

    assert helper("owner/repo", "ERCO", lookup) is None
