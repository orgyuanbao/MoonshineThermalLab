"""Verify the published course paper, and optionally compare an offline regeneration."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "course_paper"


def read(folder, name):
    return json.loads((folder / name).read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(ok, explanation):
    if not ok:
        raise ValueError(explanation)


def check_files(folder, hashes):
    for name, expected in hashes.items():
        path = (folder / name).resolve()
        require(path.is_relative_to(folder.resolve()) and not Path(name).is_absolute(),
                f"Expected a relative artifact path: {name}")
        require(path.is_file() and digest(path) == expected, f"Checksum mismatch: {name}")


def check_export(folder, *, published):
    receipt = read(folder, "receipt.json")
    loaded = read(folder, "load_skill_definition.json")
    evidence = read(folder, "paper_input.json")

    require(receipt["mode"] == "course_paper" and receipt["skill"] == "latex-research-report",
            "Expected the project reporting skill in course-paper mode.")
    require(receipt["model_calls"] == 0 and receipt["new_research_rounds"] == 0,
            "A course paper must identify archived research separately from report generation.")
    native = loaded["native_skill_audit"]
    require(native["event"] == "skill_load" and native["slug"] == receipt["skill"]
            and native["project_slug"] == receipt["project"] and native["session_id"] == receipt["session_id"],
            "The native skill-load record belongs to a different invocation.")
    require(loaded["tool"] == "load_skill_definition" and loaded["registry"] == "installed",
            "Missing native dispatch of the installed report skill.")
    require("Course Paper Layout" in loaded["output"]["sections"], "Installed skill lacks the paper layout.")
    require(loaded["skill_source_sha256"] == digest(ROOT/"project_skills"/receipt["skill"]/"SKILL.md"),
            "Loaded definition and published course-paper skill differ.")

    names = {"paper.tex", "paper_input.json", "load_skill_definition.json"}
    if published:
        names.add("paper.pdf")
        require(receipt["status"] == receipt["compile_status"] == "compiled", "Missing published compilation.")
        with (folder / "paper.pdf").open("rb") as pdf:
            require(pdf.read(5) == b"%PDF-", "Unreadable published PDF.")
    else:
        require(receipt["status"] == "tex_only" and receipt["compile_status"] == "disabled",
                "Expected source-only regeneration.")
    require(set(receipt["outputs"]) == names, "Receipt does not identify the expected outputs.")
    check_files(folder, receipt["outputs"])
    check_files(ROOT, receipt["inputs"])
    sources = {r["path"]: r["sha256"] for r in evidence["sources"]}
    require(len(sources) == len(evidence["sources"]) == receipt["source_count"], "Incomplete source inventory.")
    required = {"evidence/iterations.json", "residual_study/moonshine/run_receipts.json",
                "report_example/run_evidence.json", "residual_study/results/paired_cases.csv",
                "residual_study/results/closed_loop_cases.csv", "residual_study/results/fresh_stream.json",
                "integration/residual_tool.py", "integration/bound_agent.py", "residual_study/agent_extension/trace.json",
                "residual_study/agent_extension/replay.py", "residual_study/agent_extension/live_trace.json",
                "residual_study/agent_extension/verify_live_trace.py","integration/bound_agent_cli.py",
                "integration/test_residual_tool.py","integration/test_bound_agent.py"}
    require(required <= sources.keys(), "Missing research histories or benchmark data.")
    check_files(ROOT, sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", type=Path, help="Directory produced with thermal_agent.py paper --tex-only.")
    args = parser.parse_args()
    check_export(PUBLISHED, published=True)
    if args.rebuild:
        check_export(args.rebuild, published=False)
        for name in ("paper_input.json", "paper.tex"):
            require(digest(PUBLISHED / name) == digest(args.rebuild / name),
                    f"Archived and regenerated {name} differ.")
    print("Verified published skill invocation, source and product hashes, and paper PDF.")
    if args.rebuild:
        print("The regenerated evidence and LaTeX match the published files byte for byte.")


if __name__ == "__main__":
    main()
