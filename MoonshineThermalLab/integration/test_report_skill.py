"""Offline regression checks using constructed event fixtures and real Moonshine skills."""
import contextlib
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import run_moonshine
import thermal_agent
from integration import report_latex, report_skill


def result(name, args, output):
    return {"type": "tool_result", "text": name,
            "payload": {"name": name, "arguments": args, "output": output, "error": None}}


def review(passed, proof="逐项展开，可得四格温差的上界。"):
    args = {"scope": "intermediate", "proof": proof, "blueprint_path": "workspace/proof.md"}
    return result("verify_overall", args, {"scope": "intermediate", "passed": passed, "project_slug": "fixture",
                                          "summary": "已复核。" if passed else "需要补证。"})


@dataclass
class FixtureEvent:
    type: str
    text: str
    payload: dict


class ReportSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_moonshine.bootstrap_runtime()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.turn = self.root / "evidence" / "20261120-010101-abcdef12"
        self.turn.mkdir(parents=True)
        self.out = self.turn / "report"
        (self.turn / "input.txt").write_text("四格残差的误差上界\n检查正负交替的情况。", encoding="utf-8")
        report_skill.write_json(self.turn / "integration.json",
                                {"project": "fixture", "model": "fixture-model", "mode": "research"})
        self.final = {"type": "final", "text": "局部实验结束。", "payload": {
            "reason": "assistant_text", "research_workflow": {"research_log_archive": {"archived": 2}}}}
        self.py = result("run_python_script", {"path": "workspace/demo.py"}, {
            "status": "ok", "returncode": 0, "relative_path": "workspace/demo.py",
            "stdout": '{"bound":"5/7"}', "stderr": ""})

    def save(self, *tools):
        events = [*tools, self.final]
        (self.turn / "moonshine_events.jsonl").write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
        report_skill.write_json(self.turn / "turn_summary.json", {
            "session_id": "session-skill-test", "model": "fixture-model", "source_preserved": True,
            "final_events": [self.final], "error": None, "outcome": run_moonshine.research_outcome([self.final], tools)})

    def generate(self):
        return report_skill.run_report_skill(self.turn, self.home, "fixture")

    def test_native_skills_evidence_and_real_renderer(self):
        write = result("mcp_filesystem_write_file", {"path": "workspace/proof.md", "content": "证明蓝图：四格逐项求和。"},
                       {"status": "ok"})
        self.save(review(False), write, self.py, review(True))
        receipt = self.generate()
        self.assertIn(receipt["status"], ("tex_only", "compiled"), receipt)
        self.assertEqual(receipt["invocation"], "manual_retry")
        loaded = report_skill.read_json(self.out / "load_skill_definition.json")
        self.assertEqual(loaded["native_skill_audit"]["session_id"], "session-skill-test")
        self.assertEqual(loaded["native_skill_audit"]["event"], "skill_load")
        self.assertEqual(loaded["output"]["slug"], report_skill.SLUG)
        self.assertEqual(loaded["output"]["category"], "installed")
        self.assertEqual(report_skill.sha(self.home / loaded["output"]["path"]), loaded["installed_file_sha256"])
        data = report_skill.read_json(self.out / "report_input.json")
        self.assertEqual(data["title"], "四格残差的误差上界")
        self.assertIn("证明蓝图", data["proofs"][0]["text"])
        self.assertIn("#L2", data["proofs"][0]["source"])
        self.assertIn("5/7", data["experiments"][0]["summary"])
        self.assertEqual([r["status"] for r in data["reviews"]], ["未通过", "通过", "已记录"])
        self.assertEqual(set(data["sections"]), set(report_skill.SELECTIONS))
        for name, sha in receipt["outputs"].items():
            self.assertEqual(report_skill.sha(self.out / name), sha)
        if receipt["status"] == "compiled":
            self.assertEqual((self.out / "report.pdf").read_bytes()[:5], b"%PDF-")
            self.assertEqual(self.generate(), receipt)

    def test_definition_controls_rendered_sequence_and_material(self):
        self.save(self.py, review(True))
        definition = self.root / "SKILL.md"
        original = report_skill.DEFINITION.read_text(encoding="utf-8")
        baseline = json.dumps(report_skill.SELECTIONS, ensure_ascii=False, indent=2)
        changed = {"experiments": "python_tool_results", "proofs": "reviewed_blueprint_or_submitted_proof"}
        self.assertIn(baseline, original)
        definition.write_text(original.replace(baseline, json.dumps(changed, indent=2)), encoding="utf-8")
        with patch.object(report_skill, "DEFINITION", definition), patch.object(report_latex.shutil, "which", return_value=None):
            receipt = self.generate()
        self.assertEqual(receipt["status"], "tex_only", receipt)
        data = report_skill.read_json(self.out / "report_input.json")
        self.assertEqual(data["sections"], list(changed))
        self.assertNotIn("research_question", data)
        tex = (self.out / "report.tex").read_text(encoding="utf-8")
        self.assertLess(tex.index("实验与计算结果"), tex.index("推导与数学结论"))
        self.assertNotIn(r"\section{研究问题}", tex)

    def test_research_selector_includes_bound_witness_without_changing_legacy_output(self):
        event = result("check_residual_bound", {"candidate": "weak_signed"}, {
            "status": "counterexample", "checked_cases": 2, "total_cases": 16,
            "witness": {"violation_margin": "1/4"},
        })
        self.assertEqual(report_skill.experiments([event]), [])
        self.save(self.py, event, review(True))
        with patch.object(report_latex.shutil, "which", return_value=None):
            self.assertEqual(self.generate()["status"], "tex_only")
        row = report_skill.read_json(self.out / "report_input.json")["experiments"][1]
        self.assertEqual(row["status"], "找到反例")
        self.assertIn("1/4", row["summary"])

    def test_empty_evidence_and_later_failed_review(self):
        for tools in ([review(True)], [self.py], [self.py, review(True), review(False)]):
            with self.subTest(tools=tools):
                self.save(*tools)
                self.assertEqual(self.generate()["status"], "skipped")
                self.assertFalse((self.out / "report.tex").exists())
        self.save(self.py, review(True, proof=""))
        self.assertEqual(self.generate()["status"], "failed")
        self.assertFalse((self.out / "report.tex").exists())

    def test_retry_after_renderer_failure_preserves_user_edits_and_older_pdf(self):
        self.save(self.py, review(True))
        with patch.object(report_latex, "render_report", side_effect=RuntimeError("compiler interrupted")):
            self.assertEqual(self.generate()["status"], "failed")
        with patch.object(report_latex.shutil, "which", return_value=None):
            corrected = self.generate()
        self.assertEqual(corrected["status"], "tex_only", corrected)
        (self.out / "report.tex").write_text("课堂批注", encoding="utf-8")
        # An old artifact at a managed name must leave the current directory, even on a host without TeX.
        (self.out / "report.pdf").write_bytes(b"prior local file")
        (self.out / "teacher.txt").write_text("retain", encoding="utf-8")
        self.save(self.py, review(True), review(False))
        skipped = self.generate()
        self.assertEqual(skipped["status"], "skipped")
        self.assertFalse((self.out / "report.pdf").exists())
        self.assertFalse((self.out / "report.tex").exists())
        archive = self.out / skipped["previous_attempt"]
        self.assertEqual((archive / "report.tex").read_text(encoding="utf-8"), "课堂批注")
        self.assertEqual((archive / "report.pdf").read_bytes(), b"prior local file")
        self.assertEqual((self.out / "teacher.txt").read_text(encoding="utf-8"), "retain")

    def test_desktop_menu_latest_report(self):
        example = self.root / "report_example" / "report.pdf"
        with patch.object(run_moonshine, "DATA_ROOT", self.root), patch.object(thermal_agent.os, "startfile",
                create=True) as opened, patch.object(thermal_agent, "EXAMPLE_REPORT", example), \
                contextlib.redirect_stdout(io.StringIO()) as console:
            thermal_agent.open_latest_report()
            opened.assert_not_called()
            example.parent.mkdir()
            example.write_bytes(b"%PDF-menu-fixture")
            thermal_agent.open_latest_report()
            opened.assert_called_once_with(str(example))
            self.assertIn("这是已保存的报告", console.getvalue())
            opened.reset_mock()
            self.save(self.py, review(True))
            report_skill.write_json(self.root / "active_session.json", {
                "latest_evidence": self.turn.relative_to(self.root).as_posix()})
            with patch.object(run_moonshine, "HOME", self.home), patch.object(run_moonshine, "PROJECT", "fixture"), \
                 patch.object(report_latex.shutil, "which", return_value=None):
                thermal_agent.open_latest_report()
            opened.assert_called_once_with(str(self.out))
            opened.reset_mock()
            self.save(self.py, review(True), review(False))
            with patch.object(run_moonshine, "HOME", self.home), patch.object(run_moonshine, "PROJECT", "fixture"):
                thermal_agent.open_latest_report()
            opened.assert_not_called()
            self.assertIn("最后一次审核没有确认", console.getvalue())

    def test_normal_runner_dispatches_after_archiving(self):
        from moonshine.moonshine_cli.config import load_config
        from moonshine.moonshine_constants import MoonshinePaths
        from moonshine.skills.manager import SkillManager
        from moonshine.tools.manager import ToolManager

        app = Mock()
        app.start_shell_state.return_value = SimpleNamespace(session_id="fixture-automatic")
        app.stage_input_file.return_value = {"relative_path": "workspace/problem.md"}
        app.run_research_autopilot_events.return_value = map(lambda e: FixtureEvent(**e),
                                                             [self.py, review(True), self.final])
        (self.root / "problem.md").write_text("四格测试问题", encoding="utf-8")

        def offline_app(*args, **kwargs):
            app.paths = MoonshinePaths(self.home)
            app.config = load_config(app.paths)
            app.skill_manager = SkillManager(app.paths)
            app.tool_manager = ToolManager(app.paths)
            return app

        with patch.multiple(run_moonshine, DATA_ROOT=self.root, HOME=self.home, PROJECT="fixture", ENTRYPOINT=None), \
             patch.object(run_moonshine, "build_app", side_effect=offline_app), \
             patch.object(report_latex.shutil, "which", return_value=None), \
             patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_moonshine.run_research(model="fixture-model"), 0)
        app.close_session.assert_called_once()
        selection = report_skill.read_json(self.root / "active_session.json")
        report = self.root / selection["latest_evidence"] / "report"
        receipt = report_skill.read_json(report / "receipt.json")
        self.assertEqual(receipt["invocation"], "automatic_after_research")
        self.assertEqual(receipt["session_id"], "fixture-automatic")
        self.assertEqual(receipt["status"], "tex_only", receipt)


if __name__ == "__main__":
    unittest.main()

