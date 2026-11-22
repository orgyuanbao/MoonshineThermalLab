"""Re-run the course project's deterministic research agent and compare its complete trace."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import run_moonshine as runner
from integration.bound_agent import LOCAL_GOAL, default_policy, get_local_checker, run_agent
from integration.residual_tool import TOOL_NAME, register_residual_tool

FROZEN = HERE / "trace.json"


def run_trial(home):
    runner.bootstrap_runtime()
    from moonshine.model_tools import collect_tool_schemas
    from moonshine.moonshine_constants import MoonshinePaths
    from moonshine.tools.manager import ToolManager

    registry = ToolManager(MoonshinePaths(home))
    if registry.get_tool(TOOL_NAME) is not None:
        raise ValueError("Pristine Moonshine unexpectedly exposes the extension")
    register_residual_tool(registry)
    schema, = collect_tool_schemas(registry, mode="research", include=[TOOL_NAME])
    run = run_agent(default_policy, get_local_checker(home), goal=LOCAL_GOAL, max_rounds=4)
    if run["status"] != "finite_search_completed":
        raise ValueError("Study ended without the expected finite-domain evidence: " + run["reason"])
    return {"schema_version": 1, "mode": "deterministic_controller", "model": None,
            "model_calls": 0, "controller": "integration.bound_agent.run_agent",
            "upstream_commit": runner.source_identity()["commit"], "tool_name": TOOL_NAME,
            "pristine_registry_has_tool": False, "research_tool_schema": schema,
            "goal": run["goal"], "max_rounds": 4, "steps": run["history"],
            "decisions": run["decisions"], "controller_status": run["status"],
            "conclusion": run["reason"], "scale_bracket": run["scale_bracket"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-fixture", action="store_true",
                        help="Check the separate local scripted HTTP peer; makes no external model requests")
    parser.add_argument("--record", type=Path, metavar="NEW_JSON",
                        help="Write a fresh trace rather than compare with the published run")
    args = parser.parse_args()
    if args.http_fixture:
        from integration.test_bound_agent_http import fixture_receipt
        actual = fixture_receipt()
        frozen = HERE / "http_fixture.json"
    else:
        with tempfile.TemporaryDirectory() as tmp:
            actual = run_trial(Path(tmp))
        frozen = FROZEN
    if args.record:
        with args.record.open("x", encoding="utf-8", newline="\n") as fp:
            json.dump(actual, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
    elif json.loads(frozen.read_bytes()) != actual:
        raise ValueError("The observed decisions, witnesses or counts differ from the frozen run")
    if args.http_fixture:
        print("Loopback HTTP requests:", len(actual["http_requests"]), "| External model calls:",
              actual["external_model_calls"])
        return
    for step in actual["steps"]:
        result = step["result"]
        print(step["round"], result["candidate"], result["scale"], result["status"],
              result["checked_cases"], "/", result["total_cases"])
    print("Finite-domain scale interval:", actual["scale_bracket"], "| Model calls: 0")


if __name__ == "__main__":
    main()
