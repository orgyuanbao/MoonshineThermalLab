"""Verify the controller's feedback loop, stopping rules and durable CLI traces."""
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import Mock, patch

from integration import bound_agent_cli as cli
from integration.bound_agent import LOCAL_GOAL, default_policy, get_local_checker, local_policy, run_agent


class BoundAgentTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.check = get_local_checker(self.root / "home")

    def run_local(self, policy=default_policy, **kwargs):
        return run_agent(policy, self.check, goal=LOCAL_GOAL, **kwargs)

    def test_default_policy_revises_then_pins_down_finite_domain_scale(self):
        result = self.run_local()
        self.assertEqual(result["status"], "finite_search_completed")
        observations = [step["result"] for step in result["history"]]
        self.assertEqual([(r["candidate"], r["scale"], r["checked_cases"]) for r in observations], [
            ("weak_signed", "1", 90), ("block_two_endpoint", "1", 1296), ("block_two_endpoint", "1/2", 1)])
        self.assertEqual(observations[0]["witness"]["true_error_inf"], "399/538")
        self.assertEqual(observations[-1]["witness"]["true_error_inf"], "21/4")
        self.assertEqual(result["scale_bracket"], {"lower":"1", "upper":"1", "no_finite_scale":False})
        self.assertEqual(result["decisions"][-1]["action"], "finish")

    def test_custom_domain_changes_the_choice_after_observation(self):
        domain = {"boundary_levels":["1/5"], "residual_values":[1], "partition":"whole"}
        result = self.run_local(local_policy("weak_signed", domain))
        checked = [step["result"] for step in result["history"]]
        self.assertEqual([(r["candidate"], r["status"], r["total_cases"]) for r in checked], [
            ("weak_signed", "no_counterexample_in_domain", 1), ("weak_signed", "counterexample", 1)])
        self.assertEqual(checked[1]["witness"]["candidate_bound"], "21/8")
        self.assertEqual(result["scale_bracket"]["lower"], result["scale_bracket"]["upper"])

    def test_budget_and_repeat_stop_before_another_tool_execution(self):
        counted = Mock(wraps=self.check)
        limited = run_agent(default_policy, counted, goal=LOCAL_GOAL, max_rounds=1)
        self.assertEqual((limited["status"], counted.call_count, len(limited["history"])), ("budget_exhausted", 1, 1))
        counted.reset_mock()

        def repeats(goal, history):
            arguments = dict(scale="1", candidate="weak_signed")
            if history:
                arguments = dict(reversed(list(arguments.items())))
            return {"action":"check", "arguments":arguments}

        repeated = run_agent(repeats, counted, goal=LOCAL_GOAL)
        self.assertEqual((repeated["status"], counted.call_count, len(repeated["history"])), ("repeated_candidate", 1, 1))

    def test_invalid_tool_receipt_keeps_previous_verified_work(self):
        verified = self.check({"candidate":"weak_signed", "scale":"1"})
        partial = {"status":"no_counterexample_in_domain", "checked_cases":1, "total_cases":1296, "witness":None}
        source = Mock(side_effect=[verified, partial])
        result = run_agent(default_policy, source, goal=LOCAL_GOAL)
        self.assertEqual(result["status"], "error")
        self.assertEqual([s["result"] for s in result["history"]], [verified])
        self.assertEqual(len(result["decisions"]), 2)

    def test_blank_model_configuration_and_existing_trace_are_preserved(self):
        example = "LLM_BASE_URL=\nLLM_MODEL=\nLLM_API_KEY=\n"
        (self.root / ".env.example").write_text(example, encoding="utf-8")
        out = self.root / "research"
        with patch.object(cli, "get_local_checker") as checker, self.assertRaises(ValueError):
            cli.investigate(self.root, model=True, output=out)
        checker.assert_not_called()
        self.assertEqual((self.root / ".env").read_text(encoding="utf-8"), example)
        self.assertFalse((out / "trace.json").exists())
        out.mkdir(exist_ok=True)
        existing = out / "trace.json"
        existing.write_bytes(b"user-owned trace")
        with patch.object(cli, "get_local_checker") as checker, self.assertRaises(FileExistsError):
            cli.investigate(self.root, output=out)
        checker.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"user-owned trace")

    def test_checkpoints_are_readable_during_run_and_survive_interruption(self):
        out = self.root / "research"
        trace = out / "trace.json"
        snapshots = []

        def interrupt_on_second(args):
            current = json.loads(trace.read_text(encoding="utf-8"))
            snapshots.append(current)
            if len(snapshots) == 2:
                raise KeyboardInterrupt
            return self.check(args)

        with redirect_stdout(StringIO()), patch.object(cli, "get_local_checker", return_value=interrupt_on_second):
            with self.assertRaises(KeyboardInterrupt):
                cli.investigate(self.root, output=out)
        self.assertEqual([len(s["history"]) for s in snapshots], [0, 1])
        self.assertTrue(all(s["status"] == "running" for s in snapshots))
        after = json.loads(trace.read_text(encoding="utf-8"))
        self.assertEqual(after["status"], "interrupted")
        self.assertEqual(after["history"], snapshots[1]["history"])
        self.assertEqual(after["history"][0]["result"]["witness"]["true_error_inf"], "399/538")
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["trace.json"])

    def test_failed_snapshot_replace_leaves_previous_json_intact(self):
        trace = self.root / "trace.json"
        cli.reserve_trace(trace, {"step":0})
        with patch.object(cli.os, "replace", side_effect=OSError("write error")), self.assertRaises(OSError):
            cli.save_trace(trace, {"step":1})
        self.assertEqual(json.loads(trace.read_text(encoding="utf-8")), {"step":0})
        self.assertEqual(list(self.root.glob(".trace-*.tmp")), [])

    def test_concurrent_starts_reserve_a_single_trace(self):
        trace = self.root / "trace.json"
        gate = Barrier(2)

        def reserve(identity):
            gate.wait(timeout=3)
            try:
                cli.reserve_trace(trace, {"owner":identity})
            except FileExistsError:
                return None
            return identity

        with ThreadPoolExecutor(max_workers=2) as workers:
            winners = [value for value in workers.map(reserve, (1, 2)) if value is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(json.loads(trace.read_text(encoding="utf-8")), {"owner":winners[0]})


if __name__ == "__main__":
    unittest.main()
