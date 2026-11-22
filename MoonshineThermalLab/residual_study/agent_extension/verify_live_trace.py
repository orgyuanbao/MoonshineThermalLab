"""Replay the two archived model-selected mathematical checks locally, without an API key."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
if __package__ in (None, ""):
    sys.path.insert(0, str(HERE.parents[1]))

from integration.bound_agent import get_local_checker, scale_bracket
from integration.residual_tool import TOOL_NAME, completed_search


def validate_trace(trace):
    """Check the decisions, observations and stopping condition of this recorded run."""
    if (trace.get("schema_version") != 1 or trace.get("mode") != "live_chat_completions"
            or trace.get("provider") != "阿里云百炼" or trace.get("model") != "DeepSeek 4.1"
            or trace.get("tool_name") != TOOL_NAME):
        raise ValueError("Live trace identity or reporting metadata mismatch")
    steps = trace["steps"]
    decisions = trace["decisions"]
    if len(steps) != 2 or [d["action"] for d in decisions] != ["check", "check", "finish"]:
        raise ValueError("Expected two observed tool checks followed by the model's finish")
    for i, (step, candidate) in enumerate(zip(steps, ("weak_signed", "block_two_endpoint"))):
        args = {"candidate": candidate}
        if (step["round"] != i + 1 or step["arguments"] != args or step["reason"] != ""
                or decisions[i] != {"action": "check", "arguments": args, "reason": ""}
                or step["result"]["candidate"] != candidate or not completed_search(step["result"])):
            raise ValueError(f"Live trace decision and observation disagree at round {i + 1}")
    first, second = (step["result"] for step in steps)
    domain = ("grid", "boundary_order", "cell_order", "boundary_levels", "residual_values",
              "partition", "scale", "total_cases", "arithmetic")
    if (any(first[field] != second[field] for field in domain)
            or first["status"] != "counterexample"
            or second["status"] != "no_counterexample_in_domain"
            or trace["controller_status"] != "finite_search_completed"
            or trace["scale_bracket"] != scale_bracket(steps)):
        raise ValueError("Counterexample, follow-up domain or stop condition is inconsistent")
    if not trace["conclusion"] or decisions[-1] != {"action": "finish", "reason": trace["conclusion"]}:
        raise ValueError("The model's final answer is inconsistent with its finish decision")


def replay_math(trace, home):
    """Recompute the published numbers with the same registered tool, keeping the decisions fixed."""
    validate_trace(trace)
    check = get_local_checker(home)
    for step in trace["steps"]:
        if check(step["arguments"]) != step["result"]:
            raise ValueError(f"Exact replay differs from the recorded result at round {step['round']}")


def check_source(trace, path):
    """When the original private run is available, compare its hash and all published run fields."""
    data = path.read_bytes()
    if sha256(data).hexdigest() != trace["source_trace_sha256"]:
        raise ValueError("Source trace SHA-256 differs")
    original = json.loads(data)
    fields = {"goal": "goal", "steps": "history", "decisions": "decisions", "conclusion": "reason",
              "controller_status": "status", "scale_bracket": "scale_bracket"}
    if (original["policy"] != "chat_completions"
            or any(trace[public] != original[private] for public, private in fields.items())):
        raise ValueError("Published run data differs from the original controller record")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="optionally verify against the original local trace.json")
    args = parser.parse_args()
    trace = json.loads((HERE / "live_trace.json").read_bytes())
    if args.source is not None:
        check_source(trace, args.source)
    with tempfile.TemporaryDirectory() as home:
        replay_math(trace, Path(home))
    for step in trace["steps"]:
        result = step["result"]
        print(step["round"], result["candidate"], result["status"], result["checked_cases"], "/", result["total_cases"])
    print("Both exact tool outputs match the archived model session. External calls during replay: 0.")


if __name__ == "__main__":
    main()
