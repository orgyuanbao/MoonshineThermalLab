"""Regression checks for the project extension through Moonshine's real registry."""
from fractions import Fraction as F
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import run_moonshine as runner
from integration.residual_tool import TOOL_NAME, register_residual_tool


class ResidualToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner.bootstrap_runtime()
        from moonshine.moonshine_constants import MoonshinePaths
        from moonshine.tools.manager import ToolManager
        cls.temp = TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.tools = ToolManager(MoonshinePaths(Path(cls.temp.name)))
        register_residual_tool(cls.tools)
        cls.runtime = {"mode": "research", "tool_manager": cls.tools}

    def check(self, candidate, **kwargs):
        return self.tools.dispatch(TOOL_NAME, {"candidate": candidate, **kwargs}, self.runtime)

    def test_native_counterexample_satisfies_original_equation(self):
        found = self.check("weak_signed")
        self.assertEqual(found["status"], "counterexample")
        self.assertLess(found["checked_cases"], found["total_cases"])
        w = found["witness"]
        e = list(map(F, w["error"]))
        left, right, down, up = (2*h/(4+h) for h in map(F, w["boundaries"]))
        diagonals = [2+left+down, 2+right+down, 2+left+up, 2+right+up]
        # Four-cell stencil independently applies A, without the tool's inverse.
        self.assertEqual([c * e[i] - e[i ^ 1] - e[i ^ 2] for i, c in enumerate(diagonals)], w["residual"])
        self.assertEqual(max(map(abs, e)), F(w["true_error_inf"]))
        self.assertGreater(F(w["true_error_inf"]), F(w["candidate_bound"]))
        self.assertEqual(F(w["true_error_inf"])-F(w["candidate_bound"]), F(w["violation_margin"]))

    def test_true_estimates_exhaust_domain_and_false_tightening_is_refuted(self):
        full = self.check("block_two_endpoint")
        self.assertEqual(full["status"], "no_counterexample_in_domain")
        self.assertEqual((full["checked_cases"], full["total_cases"], full["witness"]), (1296, 1296, None))
        for candidate in ("block_position", "block_signed", "block_two_endpoint"):
            for partition in ("whole", "rows", "singletons"):
                sub = self.check(candidate, partition=partition, boundary_levels=["1/2", "2"], residual_values=[-2, 1])
                self.assertEqual((sub["checked_cases"], sub["total_cases"], sub["witness"]), (256, 256, None))
        tight = self.check("block_two_endpoint", scale="1/2", boundary_levels=["1/5"], residual_values=[1])
        self.assertEqual((tight["witness"]["true_error_inf"], tight["witness"]["candidate_bound"]), ("21/4", "21/8"))
        unit = self.check("weak_signed", boundary_levels=["1/5"])
        self.assertEqual(unit["status"], "no_counterexample_in_domain")

    def test_registry_rejects_invalid_arguments_and_respects_exposure(self):
        for bad in ({"candidate":"unknown"}, {"scale":"1/0"}, {"scale":"11"},
                    {"boundary_levels":["1/5","2/10"]}, {"boundary_levels":["1/6"]},
                    {"residual_values":[-1,-1]}, {"residual_values":[33]}, {"residual_values":[True]},
                    {"residual_values":[0,1,2,3]}, {"unlisted":1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.tools.dispatch(TOOL_NAME, {"candidate":"weak_signed", **bad}, self.runtime)
        with self.assertRaisesRegex(RuntimeError, "not exposed"):
            self.tools.dispatch(TOOL_NAME, {"candidate":"weak_signed"}, {
                **self.runtime, "exposure":{"tools_include":runner.TOOLS}})

    def test_thermal_runner_registers_definition_and_old_projects_keep_their_tools(self):
        from moonshine.providers import OfflineProvider
        with TemporaryDirectory() as root, patch.object(runner, "HOME", Path(root)/"home"), \
             patch("integration.codex_provider.CodexCLIProvider", return_value=OfflineProvider()):
            for project in ("thermal-rom", "harmony-active-ranging"):
                with patch.object(runner, "PROJECT", project):
                    cfg = runner.configure_home("offline-test")
                    app = runner.build_app("offline-test", Path(root)/"evidence")
                    names = {s["name"] for s in app.tool_manager.schemas(
                        mode="research", include=cfg["exposure"]["tools_include"])}
                    self.assertEqual(TOOL_NAME in names, project == "thermal-rom")
                    if project == "thermal-rom":
                        info = app.tool_manager.dispatch("load_tool_definition", {"name":TOOL_NAME}, {
                            "mode":"research", "tool_manager":app.tool_manager, "exposure":cfg["exposure"]})
                        self.assertEqual(info["source"], "project")

    def test_checker_results_do_not_bypass_review_and_archiving(self):
        final = [{"payload": {"reason": "done", "research_workflow": {"research_log_archive": {"archived": 1}}}}]
        run = {"text": TOOL_NAME, "payload": {"output": self.check("weak_signed")}}
        review = {"text": "verify_overall", "payload": {"output": {"passed": True}}}
        self.assertFalse(runner.research_outcome(final, [run])["accepted_local_research_step"])
        self.assertFalse(runner.research_outcome([], [run,review])["accepted_local_research_step"])
        out = runner.research_outcome(final, [run,review])
        self.assertTrue(out["accepted_local_research_step"])
        self.assertEqual((out["successful_python_executions"], out["successful_residual_checks"]), (0, 1))
        self.assertNotIn("successful_residual_checks", runner.research_outcome(final, [review]))
        incomplete = {"text": TOOL_NAME, "payload": {"output": {"checked_cases": 1, "total_cases": 1296,
                      "status": "no_counterexample_in_domain", "witness": None}}}
        self.assertFalse(runner.research_outcome(final, [incomplete, review])["accepted_local_research_step"])


if __name__ == "__main__":
    unittest.main()
