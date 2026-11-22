"""Regression tests for the paper's fixed sources and row-level aggregations."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integration.paper_evidence import (
    Archive, NATIVE, RESULTS, TRACKS, build_paper_evidence, read_groups, signed_research,
)

PROJECT = Path(__file__).resolve().parents[1]


class PaperEvidenceTests(unittest.TestCase):
    def test_full_evidence_distinguishes_comparison_protocols(self):
        evidence = build_paper_evidence(PROJECT)
        benchmark = evidence["benchmark"]
        self.assertEqual((benchmark["counts"]["paired_rows"], benchmark["counts"]["closed_rows"]), (1536, 3840))
        self.assertEqual(benchmark["totals"]["old_pre_alarms"]["block_sign"], 29)
        self.assertEqual(benchmark["totals"]["fallbacks"]["block_sign"], 40)
        self.assertEqual(benchmark["sign_endpoint_max_abs_gap"], 0)
        self.assertEqual(sum(t["local_step_evidence_complete"] for t in evidence["history"]["turns"]), 4)
        self.assertFalse(evidence["signed"]["turns"][0]["reviews"][0]["passed"])
        self.assertTrue(evidence["signed"]["turns"][0]["reviews"][-1]["passed"])
        self.assertEqual(evidence["four_cell"]["modes"][2]["error_inf"], "21/88")
        self.assertEqual(evidence["fresh"]["query_count"], 128)

    def test_changed_proof_is_rejected_before_use(self):
        original = Archive(PROJECT)
        path = NATIVE + "workspace/residual_proof.md"
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "integration").mkdir()
            (root / "integration/paper_sources.sha256").write_text(
                original.expected[path] + "  " + path + "\n", encoding="utf-8"
            )
            (root / path).parent.mkdir(parents=True)
            (root / path).write_bytes(original.bytes(path) + b"\nModified proof.\n")
            with self.assertRaisesRegex(ValueError, "Archive hash mismatch"):
                Archive(root).text(path)

    def test_duplicate_csv_row_does_not_replace_a_missing_observation(self):
        archive = Archive(PROJECT)
        lines = archive.text(RESULTS + "paired_cases.csv").splitlines()
        lines[-1] = lines[1]
        with patch.object(archive, "text", return_value="\n".join(lines)):
            with self.assertRaisesRegex(ValueError, "duplicate row"):
                read_groups(archive, "paired_cases.csv", "track", TRACKS, {"n", "index"}, 256)

    def test_last_review_must_agree_with_accepted_turn_summary(self):
        archive = Archive(PROJECT)
        receipt = json.loads(archive.text(NATIVE + "run_receipts.json"))
        last_review = next(r for r in reversed(receipt["turns"][0]["native_tool_results"])
                           if r["tool"] == "verify_overall")
        last_review["passed"] = False
        with patch.object(archive, "json", return_value=receipt):
            with self.assertRaisesRegex(ValueError, "review"):
                signed_research(archive)


if __name__ == "__main__":
    unittest.main()
