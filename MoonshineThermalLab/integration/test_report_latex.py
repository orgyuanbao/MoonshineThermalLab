"""Offline tests for report formatting and untrusted research text."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integration import report_latex


class ReportLatexTests(unittest.TestCase):
    def test_math_notation_and_literal_research_text(self):
        rhs = report_latex.math_tex("‖e‖∞≤Σ_i γ_i")
        self.assertIn(r"\Vert_{\infty}", rhs)
        self.assertIn(r"\sum_", rhs)
        self.assertIn(r"\gamma", rhs)
        self.assertIsNone(report_latex.math_tex(r"\input{notes}"))
        data = {"title": "退化情况", "sections": ["proofs", "research_question"],
                "proofs": [{"text": r"只有 $\frac{2}{3}$。笔记 $\input{notes}$。"}],
                "research_question": "检查 2% & 3%"}
        tex = report_latex.build_tex(data)
        self.assertIn(r"\frac{2}{3}", tex)
        self.assertNotIn(r"\input{notes}", tex)
        self.assertIn(r"2\% \& 3\%", tex)
        self.assertLess(tex.index(r"\section{推导与数学结论}"), tex.index(r"\section{研究问题}"))
        self.assertNotIn(r"\section{实验与计算结果}", tex)

    def test_json_comparison_and_separate_error_text(self):
        summary = ('标准输出\n{"cases":[{"name":"left","norm":"5/7"},{"name":"right","norm":"2/9"}]}'
                   '\n\n标准错误或工具错误\nAdditional check pending.')
        table = report_latex.experiment_body(summary, typeset=True)
        self.assertIn("字段 & left & right", table)
        self.assertIn("norm & 5/7 & 2/9", table.replace(r"\allowbreak{}", ""))
        self.assertIn("Additional check pending.", table)
        self.assertNotIn('"cases":', table)

    def test_no_compiler_preserves_editable_chinese_source(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(report_latex.shutil, "which", return_value=None):
            folder = Path(tmp)
            receipt = report_latex.render_report({"title": "误差界"}, folder)
            self.assertEqual(receipt["compile_status"], "unavailable")
            self.assertIsNone(receipt["pdf"])
            self.assertIn("误差界", (folder / receipt["tex"]).read_text(encoding="utf-8"))
            self.assertFalse((folder / "report.pdf").exists())


if __name__ == "__main__":
    unittest.main()
