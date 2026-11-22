"""Build a course paper from the registered report skill and archived evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from integration import report_skill


IMPLEMENTATION_FILES = (
    "project_skills/latex-research-report/SKILL.md",
    "integration/report_skill.py",
    "integration/course_paper.py",
    "integration/paper_evidence.py",
    "integration/paper_sources.sha256",
    "integration/paper_latex.py",
    "integration/paper_template.tex",
    "source_manifest.json",
)
ROOT = report_skill.ROOT


def compile_paper(work: Path, enabled: bool) -> tuple[str, str]:
    if not enabled:
        return "disabled", "已按要求保存可编辑源文件。"
    engine = shutil.which("xelatex")
    if not engine:
        return "unavailable", "未找到 XeLaTeX，已保存可编辑源文件。"
    command = [engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
               "-file-line-error", "paper.tex"]
    try:
        for _ in range(2):
            attempt = subprocess.run(command, cwd=work, capture_output=True,
                                     stdin=subprocess.DEVNULL, timeout=120, check=False)
            if attempt.returncode:
                return "failed", "XeLaTeX 编译出错。可用本目录的 paper.tex 复现编译。"
    except (OSError, subprocess.TimeoutExpired):
        return "failed", "XeLaTeX 未能完成编译，已保存可编辑源文件。"
    log = (work / "paper.log").read_text(encoding="utf-8", errors="replace")
    warnings = ("Missing character:", "There were undefined references", "There were undefined citations")
    if any(warning in log for warning in warnings):
        return "failed", "XeLaTeX 报告缺失字形或未解析的引用，已保存可编辑源文件。"
    pdf = work / "paper.pdf"
    if not pdf.is_file() or pdf.stat().st_size < 50 or not pdf.read_bytes().startswith(b"%PDF-"):
        return "failed", "编译器没有生成可读的 PDF，已保存可编辑源文件。"
    return "compiled", "LaTeX 源文件及 PDF 均已生成。"


def source_hashes(root: Path, paths) -> dict:
    return {name: report_skill.sha(report_skill.local(root, name)) for name in paths}


def check_sources(root: Path, evidence: dict) -> int:
    rows = evidence["sources"]
    expected = {row["path"]: row["sha256"] for row in rows}
    if (not expected or len(expected) != len(rows)
            or any(report_skill.portable_workspace_path(name) != name or not name for name in expected)
            or source_hashes(root, expected) != expected):
        raise ValueError("论文来源清单缺失、重复或文件校验值不一致。")
    return len(expected)


def fresh_destination(path: Path):
    if (path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
            or (path.exists() and (not path.is_dir() or any(path.iterdir())))):
        raise ValueError("输出位置已有文件。请指定新的输出目录；原文件将保留。")


def generate_course_paper(home: Path, *, output: Path | None = None, tex_only: bool = False):
    """Dispatch the installed skill, verify sources, and publish one self-contained paper."""
    import run_moonshine
    from integration.paper_evidence import build_paper_evidence
    from integration.paper_latex import build_paper_tex

    home = home.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:12]
    session = "paper-export-" + stamp
    output = Path(output).absolute() if output is not None else home.parent / "papers" / stamp
    fresh_destination(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = source_hashes(ROOT, IMPLEMENTATION_FILES)
    run_moonshine.bootstrap_runtime()
    identity = run_moonshine.source_identity()
    sections, loaded = report_skill.load_definition(home, "thermal-rom", session, None, course_paper=True)
    evidence = build_paper_evidence(ROOT)
    source_count = check_sources(ROOT, evidence)
    with tempfile.TemporaryDirectory(prefix=".paper-", dir=output.parent) as working:
        stage = Path(working) / "result"
        stage.mkdir()
        report_skill.write_json(stage / "load_skill_definition.json", loaded)
        report_skill.write_json(stage / "paper_input.json", evidence)
        tex = build_paper_tex(evidence, sections)
        (stage / "paper.tex").write_text(tex, encoding="utf-8", newline="\n")
        with tempfile.TemporaryDirectory(dir=working) as build:
            build = Path(build)
            shutil.copyfile(stage / "paper.tex", build / "paper.tex")
            compilation, message = compile_paper(build, not tex_only)
            if compilation == "compiled":
                (build / "paper.pdf").replace(stage / "paper.pdf")
        if source_hashes(ROOT, IMPLEMENTATION_FILES) != inputs:
            raise ValueError("写作过程中，技能、处理程序或模板发生变化。请重试。")
        check_sources(ROOT, evidence)
        receipt = {
            "schema": 1, "mode": "course_paper", "invocation": "requested_course_paper",
            "skill": report_skill.SLUG, "project": "thermal-rom", "session_id": session,
            "sections": sections, "model_calls": 0, "new_research_rounds": 0,
            "upstream_commit": identity["commit"],
            "source_count": source_count, "inputs": inputs,
            "outputs": {path.name: report_skill.sha(path) for path in sorted(stage.iterdir())},
            "status": {"compiled": "compiled", "failed": "compile_failed"}.get(compilation, "tex_only"),
            "compile_status": compilation, "message": message,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        report_skill.write_json(stage / "receipt.json", receipt)
        # Publish the complete set at once; if a concurrent writer beat us,
        # rmdir/rename refuses any nonempty destination on supported systems.
        fresh_destination(output)
        if output.is_dir():
            output.rmdir()
        stage.rename(output)
    return output, receipt
