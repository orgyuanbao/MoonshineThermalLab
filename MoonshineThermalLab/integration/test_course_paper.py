"""Exercise the second mode of the installed skill without a model or TeX."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_moonshine
import thermal_agent
from integration import course_paper, report_skill


class CoursePaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_moonshine.bootstrap_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.source = report_skill.ROOT / "report_example" / "source_skill.md"

    def dispatch(self, paper=True):
        return report_skill.load_definition(self.home, "thermal-rom", "test-export", None, course_paper=paper)

    def install_previous(self):
        with patch.object(report_skill, "DEFINITION", self.source):
            layout, receipt = self.dispatch(paper=False)
        self.assertEqual(layout, report_skill.SELECTIONS)
        return self.home / receipt["output"]["path"]

    def test_upgrade_v1_through_native_registry_preserves_single_turn_mode(self):
        installed = self.install_previous()
        sections, loaded = self.dispatch()
        self.assertEqual(sections, ["problem", "bounds", "four_cell", "research", "experiments",
                                    "discussion", "sources"])
        self.assertEqual(loaded["registry"], "installed")
        self.assertEqual(loaded["native_skill_audit"]["event"], "skill_load")
        self.assertEqual(loaded["skill_source_sha256"], report_skill.sha(report_skill.DEFINITION))
        self.assertEqual(loaded["installed_file_sha256"], report_skill.sha(installed))
        single, _ = self.dispatch(paper=False)
        self.assertEqual(single, report_skill.SELECTIONS)

    def test_upgrade_preserves_personal_edit_in_old_metadata(self):
        installed = self.install_previous()
        installed.write_text(installed.read_text(encoding="utf-8").replace(
            "title: 研究证据转 LaTeX 报告", "title: 个人批注"), encoding="utf-8")
        before = installed.read_bytes()
        with self.assertRaisesRegex(ValueError, "个人改动"):
            self.dispatch()
        self.assertEqual(installed.read_bytes(), before)

    def test_unchanged_output_and_source_checks(self):
        (self.root / "observed.txt").write_text("frozen", encoding="utf-8")
        row = {"path": "observed.txt", "sha256": report_skill.sha(self.root / "observed.txt")}
        self.assertEqual(course_paper.check_sources(self.root, {"sources": [row]}), 1)
        (self.root / "observed.txt").write_text("edited", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "校验值"):
            course_paper.check_sources(self.root, {"sources": [row]})
        with self.assertRaisesRegex(ValueError, "已有文件"):
            course_paper.fresh_destination(self.root)

    def test_menu_and_cli_forward_paper_action(self):
        console = io.StringIO()
        with patch.object(thermal_agent, "configure"), patch.object(thermal_agent, "build_course_paper",
                return_value=0) as build, patch.object(run_moonshine, "model_display", return_value="offline"), \
             contextlib.redirect_stdout(console), patch("builtins.input", side_effect=["7", "0"]), \
             patch("sys.argv", ["thermal_agent.py"]):
            self.assertEqual(thermal_agent.main(), 0)
            build.assert_called_once_with(open_result=True)
        with patch.object(thermal_agent, "configure"), patch.object(thermal_agent, "build_course_paper",
                return_value=0) as build, patch("sys.argv", ["thermal_agent.py", "paper", "--tex-only",
                                                              "--output", str(self.root)]):
            self.assertEqual(thermal_agent.main(), 0)
            build.assert_called_once_with(self.root, tex_only=True)


if __name__ == "__main__":
    unittest.main()
