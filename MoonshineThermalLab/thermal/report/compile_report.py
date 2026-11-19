"""Compile saved TeX with XeLaTeX; this runs no models or scientific experiments."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    source = (ROOT / "main.tex").read_text(encoding="utf-8")
    if not args.draft and "工作稿" in source:
        raise RuntimeError("The current source is a draft; use --draft or finish the report first.")
    executable = shutil.which("xelatex")
    if not executable:
        raise RuntimeError("XeLaTeX is required to export the PDF. The saved TeX remains available.")
    build = ROOT / ("build_draft" if args.draft else "build")
    build.mkdir(exist_ok=True)
    for pass_number in (1, 2):
        response = subprocess.run(
            [executable, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
             "-output-directory=" + str(build), "main.tex"], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        (build / f"pass{pass_number}.txt").write_text(response.stdout + response.stderr, encoding="utf-8")
        if response.returncode:
            raise RuntimeError(f"XeLaTeX pass {pass_number} failed; inspect {build}.")
    log = (build / "main.log").read_text(encoding="utf-8", errors="replace")
    warnings = [line for line in log.splitlines() if any(token in line for token in (
        "Overfull", "Missing character", "undefined references", "undefined citations"))]
    if warnings:
        raise RuntimeError("Layout/reference warnings remain: " + "\n".join(warnings))
    output = build / "main.pdf" if args.draft else ROOT / "Moonshine_Thermal_Report.pdf"
    if not args.draft:
        shutil.copy2(build / "main.pdf", output)
    print(json.dumps({"pdf": str(output), "draft": args.draft, "compiled": True,
                      "visual_review_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
