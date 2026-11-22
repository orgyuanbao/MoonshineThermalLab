"""Typeset a Moonshine evidence snapshot without executing model-authored TeX."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

SECTIONS = ("research_question", "proofs", "experiments", "reviews", "sources")
HEADINGS = ("研究问题", "推导与数学结论", "实验与计算结果", "审核与局限", "证据索引")
ESCAPES = dict(zip("\\{}$&#_%^~", (
    r"\textbackslash{}", r"\{", r"\}", r"\$", r"\&", r"\#", r"\_", r"\%",
    r"\textasciicircum{}", r"\textasciitilde{}",
)))
SECRET = re.compile(
    r"(?i)\b(?:sk-[a-z0-9_-]{10,}|(?:gh[pousr]_|github_pat_)[a-z0-9_]{12,}|"
    r"bearer\s+[\w.=/+-]{8,}|(?:api[_-]?key|access[_-]?token|password|secret)"
    r"[\s\x22\x27]*[:=][\s\x22\x27]*[^\s,;\x22\x27]{3,})"
)
LOCAL_PATH = re.compile(r"(?i)(?:[A-Z]:[/\\]|/(?:home|users|tmp)/)[^\s，。；、<>\"']+")
UNICODE_MATH = {
    "≤": r"\le ", "≥": r"\ge ", "≈": r"\approx ", "≠": r"\ne ", "∞": r"\infty ",
    "∑": r"\sum ", "±": r"\pm ", "×": r"\times ", "·": r"\cdot ", "∈": r"\in ",
    "→": r"\to ", "⇒": r"\Rightarrow ", "‖": r"\Vert ", "−": "-", "α": r"\alpha ",
    "β": r"\beta ", "γ": r"\gamma ", "δ": r"\delta ", "Δ": r"\Delta ", "λ": r"\lambda ",
    "Σ": r"\Sigma ", "∼": r"\sim ",
}
# No definitions, file access, macros taking text, or environments are permitted.
MATH_COMMANDS = set((
    "frac dfrac tfrac sqrt le leq ge geq lt gt ne neq equiv approx sim simeq propto "
    "sum prod max min sup inf lim log exp sin cos det diag infty in notin subset subseteq "
    "forall exists times cdot circ pm mp colon mid vert Vert lvert rvert lVert rVert "
    "left right big Big bigl bigr Bigl Bigr mapsto to gets rightarrow Rightarrow "
    "leftrightarrow Leftrightarrow partial nabla top perp mathbb mathrm mathbf mathcal "
    "operatorname text ldots cdots dots quad qquad ldots leqslant geqslant underbrace overbrace "
    "alpha beta gamma delta epsilon varepsilon zeta eta theta iota kappa lambda mu nu xi pi "
    "rho sigma tau phi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega "
    "hat bar tilde overline underline langle rangle emptyset setminus cup cap ast dagger "
    "binom choose mod bmod pmod parallel ell mathsf mathit textstyle displaystyle"
).split())
MARKER = "% Created by MoonshineThermalLab report_latex\n"
TICK = chr(96)


def clean(value, limit=4000):
    if not isinstance(value, (str, int, float, bool)):
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in text if c in "\t\n" or unicodedata.category(c)[0] != "C")
    text = LOCAL_PATH.sub("［本机路径］", SECRET.sub("［已隐去］", text))
    if len(text) > limit:
        return text[:limit] + "…（节录）"
    return text


def esc(text):
    parts = []
    for c in re.findall(r"⁻¹|.", text, re.S):
        if c == "⁻¹":
            parts.append(r"\ensuremath{{}^{-1}}")
        elif c in UNICODE_MATH:
            parts.append(r"\ensuremath{" + UNICODE_MATH[c] + "}")
        else:
            parts.append(ESCAPES.get(c, c))
    return "".join(parts)


def math_tex(value):
    """Accept a small TeX math vocabulary or render unsupported syntax literally."""
    value = value.strip()
    if not value or len(value) > 350 or "^^" in value:
        return None
    value = (value.replace("Σ_", r"\sum_").replace("⁻¹", "^{-1}")
             .replace("‖∞", r"\Vert_{\infty}").replace("||∞", r"\Vert_{\infty}")
             .replace("||", r"\Vert ").replace("<=", r"\le ").replace(">=", r"\ge ")
             .replace("!=", r"\ne ").replace("_infinity", r"_{\infty}"))
    value = re.sub(r"(?<![\\a-zA-Z])(?:sum|max|min|infinity|in|Delta|beta)(?=[^a-zA-Z]|$)",
                   lambda m: "\\" + ("infty" if m[0] == "infinity" else m[0]) + " ", value)
    value = re.sub(r"(\\(?:max|min)) \{([^{}]+)\}",
                   lambda m: m[1] + r"\{" + m[2] + r"\}", value)
    value = "".join(UNICODE_MATH.get(c, c) for c in value)
    value = value.strip()
    if re.search(r"[^a-zA-Z0-9{}()[\]., \t:+*/=|!_^\-<>\\']", value):
        return None
    # Ensure every backslash is consumed by an approved command or spacing symbol.
    for command in re.findall(r"\\([A-Za-z]+|.)", value):
        if command not in MATH_COMMANDS and command not in {",", ";", "!", " ", "{", "}", "|", ":", "_"}:
            return None
    if value.endswith("\\"):
        return None
    bare = re.sub(r"\\[{}]", "", value)
    depth = 0
    for c in bare:
        depth += (c == "{") - (c == "}")
        if depth < 0 or depth > 16:
            return None
    if depth or re.search(r"[\^_] *[}\^_]|[\^_] *$", bare):
        return None
    return value.replace(",", r",\allowbreak{}")


def formula(text, display, typeset):
    math = math_tex(text) if typeset else None
    if math:
        return (r"\[" + math + r"\]") if display else (r"\(" + math + r"\)")
    literal = esc(text.strip())
    return (r"\par\noindent{\small " + literal + r"}\par") if display else literal


def inline(line, typeset):
    parts = re.split(r"(\$[^$\n]+\$|\\\([^\n]*?\\\)|" + TICK + r"[^" + TICK + r"\n]+" + TICK + r"|\*\*[^*\n]+\*\*)", line)
    rendered = []
    for part in parts:
        if part.startswith("$") and part.endswith("$") and len(part) > 2:
            rendered.append(formula(part[1:-1], False, typeset))
        elif part.startswith(r"\(") and part.endswith(r"\)"):
            rendered.append(formula(part[2:-2], False, typeset))
        elif len(part) > 2 and part.startswith(TICK) and part.endswith(TICK):
            rendered.append(r"{\small\ttfamily " + esc(part[1:-1]) + "}")
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            rendered.append(r"\textbf{" + esc(part[2:-2]) + "}")
        else:
            rendered.append(esc(part))
    return "".join(rendered)


def markdown(value, typeset):
    lines, out = clean(value, 40000).splitlines(), []
    display, fence = None, ""
    for raw in lines[:650]:
        line = raw.strip()
        if display is not None:
            if line == fence or (fence == TICK * 3 and line.startswith(fence)):
                for math_line in display:
                    out.append(formula(math_line, True, typeset))
                display = None
            else:
                display.append(line)
        elif line in {"$$", r"\["} or line.startswith(TICK * 3):
            display, fence = [], ("$$" if line == "$$" else r"\]" if line == r"\[" else TICK * 3)
        elif (line.startswith("$$") and line.endswith("$$") and len(line) > 4) or (
                line.startswith(r"\[") and line.endswith(r"\]") and len(line) > 4):
            out.append(formula(line[2:-2], True, typeset))
        elif raw.startswith(("    ", "\t")) and line:
            out.append(formula(line, True, typeset))
        elif line.startswith("#"):
            out.append(r"\subsubsection*{" + inline(line.lstrip("# ").strip(), typeset) + "}")
        elif line.startswith(("- ", "* ")):
            out.append(r"\par\noindent\textbullet\enspace " + inline(line[2:], typeset))
        elif line:
            out.append(inline(line, typeset))
        else:
            out.append("")
    if display is not None:
        out.extend(formula(s, True, typeset) for s in display)
    if len(lines) > 650:
        out.append(r"\par （以下内容节录于来源文件。）")
    return "\n".join(out)


PREAMBLE = r"""\documentclass[UTF8,a4paper,11pt]{ctexart}
\usepackage[margin=25mm,top=24mm,bottom=24mm]{geometry}
\usepackage{amsmath,amssymb,xcolor,booktabs,array,longtable,fancyhdr}
\definecolor{ink}{HTML}{162F40}
\definecolor{accent}{HTML}{176563}
\definecolor{muted}{HTML}{4D616B}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small\color{muted}Moonshine\quad 数学研究记录}
\fancyfoot[C]{\small\color{muted}\thepage}
\setlength{\headheight}{16pt}
\ctexset{section={format=\Large\bfseries\color{ink}},subsection={format=\large\bfseries\color{accent}}}
\setlength{\parskip}{.38em}
\setlength{\parindent}{0pt}
\setlength{\emergencystretch}{4em}
\raggedbottom
\begin{document}
"""


def records(value, limit):
    if not isinstance(value, (list, tuple)):
        return []
    return [r for r in value[:limit] if isinstance(r, dict)]


def path_text(value):
    """Optional line breaks within a printed evidence path or SHA-256 digest."""
    text = clean(value, 300)
    return "".join(esc(c) + (r"\allowbreak{}" if i % 12 == 11 or c in "/_-" else "")
                   for i, c in enumerate(text))


def table(headers, rows):
    width = .95 / len(headers)
    spec = "@{}" + (f"p{{{width:.3f}\\linewidth}}" + r"@{\hspace{.01\linewidth}}") * (len(headers) - 1)
    spec += f"p{{{width:.3f}\\linewidth}}" + "@{}"
    lines = [r"\begin{longtable}{" + spec + "}", r"\toprule " +
             " & ".join(headers) + r" \\\midrule\endhead"]
    lines.extend(" & ".join(row) + r" \\" for row in rows)
    return lines + [r"\bottomrule\end{longtable}"]


def json_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return path_text(value)
    if isinstance(value, list) and len(value) <= 12 and all(not isinstance(v, (dict, list)) for v in value):
        return "[" + ", ".join(json_scalar(v) for v in value) + "]"
    return None


def json_output(obj):
    """Compare similarly shaped records; show other nested fields by their original key."""
    out, remaining = [], 100

    def emit(node, prefix, depth):
        nonlocal remaining
        if remaining <= 0:
            return
        remaining -= 1
        if depth == 8:
            out.append(r"\par 更深层字段见工具回执。\par")
            return
        label = path_text(prefix)
        scalar = json_scalar(node)
        if scalar is not None:
            out.append(r"\par " + (label + r"\quad " if label else "") + scalar + r"\par")
            return
        entries = list(node.items()) if isinstance(node, dict) else list(enumerate(node, 1))
        if label:
            out.append(r"\par\textbf{" + label + r"}\par")
        if 2 <= len(entries) <= 4 and all(isinstance(v, dict) and v for _, v in entries):
            keys = list(entries[0][1])
            if len(keys) <= 20 and all(set(v) == set(keys) and all(json_scalar(x) is not None for x in v.values())
                                       for _, v in entries):
                name_key = next((k for k in ("name", "mode", "pattern", "case", "id")
                                 if k in keys and all(isinstance(v[k], str) for _, v in entries)), None)
                labels = [(v[name_key] if name_key else str(k)) for k, v in entries]
                body = [[path_text(k)] + [json_scalar(v[k]) for _, v in entries] for k in keys if k != name_key]
                if body:
                    out.extend(table(["字段"] + [path_text(s) for s in labels], body))
                    return
        rows = []
        for k, v in entries:
            if remaining <= 0:
                break
            val = json_scalar(v)
            if val is None:
                if rows:
                    out.extend(table(["字段", "记录值"], rows))
                    rows = []
                emit(v, str(k), depth + 1)
            else:
                remaining -= 1
                rows.append([path_text(str(k)), val])
        if rows:
            out.extend(table(["字段", "记录值"], rows))
        if not entries:
            out.append(r"\par （空集合）\par")

    emit(obj, "", 0)
    if remaining <= 0:
        out.append(r"\par 篇幅所限，仅列前部字段，完整输出见该次工具回执。\par")
    return out


def experiment_body(summary, typeset):
    stdout, sep, errors = str(summary).partition("\n\n标准错误或工具错误\n")
    if stdout.startswith("标准输出\n"):
        payload = stdout.removeprefix("标准输出\n").strip()
        if payload.startswith(("{", "[")) and len(payload) <= 100000:
            try:
                parsed = json.loads(payload)
            except (ValueError, RecursionError):
                pass
            else:
                body = [r"\textbf{标准输出}\par", *json_output(parsed)]
                if sep:
                    body += [r"\textbf{标准错误或工具错误}\par", markdown(errors, typeset)]
                return "\n".join(body)
    return markdown(summary, typeset)


def build_tex(evidence, typeset=True):
    title = clean(evidence.get("title"), 230) or "Moonshine 研究记录"
    available = dict(zip(SECTIONS, HEADINGS))
    chosen = evidence.get("sections", SECTIONS)
    if not isinstance(chosen, (list, tuple)):
        raise ValueError("sections must be a sequence")
    if not chosen or any(not isinstance(s, str) or s not in available for s in chosen) or len(set(chosen)) != len(chosen):
        raise ValueError("sections must contain unique supported identifiers")
    sources = records(evidence.get("sources"), 100)
    index = {s.get("path"): i for i, s in enumerate(sources, 1) if isinstance(s.get("path"), str)}
    out = [MARKER + PREAMBLE, r"{\small\sffamily\bfseries\color{accent} MOONSHINE \quad / \quad RESEARCH REPORT}\par",
           r"\vspace{.45em}{\LARGE\bfseries\color{ink} " + esc(title) + r"}\par",
           r"\vspace{.25em}{\color{accent}\rule{\linewidth}{.8pt}}\par"]
    meta = []
    for key, name in (("project", "项目"), ("turn_id", "研究轮次"), ("model", "模型"), ("status", "任务状态")):
        val = clean(evidence.get(key), 100)
        if val:
            meta.append(name + r"\enspace " + path_text(val))
    if meta:
        out.append(r"{\small\color{muted} " + r"\quad ".join(meta) + r"}\par")
    if evidence.get("session_id"):
        out.append(r"{\small\color{muted} 会话\enspace " + path_text(evidence["session_id"]) + r"}\par")

    def cite(row):
        source = clean(row.get("source"), 300)
        if source:
            file, _, suffix = source.partition("#")
            if file in index and "sources" in chosen:
                reference = f"[E{index[file]}]"
                if suffix:
                    reference += r"\enspace " + path_text(suffix)
            else:
                reference = path_text(source)
            out.append(r"\par\noindent{\footnotesize\color{muted} 证据\enspace " + reference + r"}\par")

    for section in chosen:
        out.append(r"\section{" + available[section] + "}")
        if section == "research_question":
            out.append(markdown(evidence.get(section), typeset) or "本轮未记录研究问题。")
            continue
        rows = sources if section == "sources" else records(evidence.get(section), 60)
        if not rows:
            out.append("本轮提供的材料中没有此项记录。")
        for i, row in enumerate(rows, 1):
            if section == "sources":
                label = clean(row.get("label"), 150)
                out.append(r"\noindent\textbf{[E" + str(i) + "] " + esc(label) + r"}\par")
                if row.get("path") != label:
                    out.append(r"{\small " + path_text(row.get("path")) + r"}\par")
                digest = clean(row.get("sha256"))
                if re.fullmatch(r"[a-fA-F0-9]{64}", digest):
                    out.append(r"{\footnotesize\color{muted} SHA-256\quad " + path_text(digest) + r"}\par")
                continue
            title = clean(row.get("title") or row.get("label"), 200)
            out.append(r"\subsection*{" + esc(title or f"记录 {i}") + "}")
            if section in {"experiments", "reviews"} and row.get("status"):
                out.append(r"{\small\color{muted} 记录状态\enspace " + esc(clean(row["status"], 120)) + r"}\par")
            body = row.get("text" if section == "proofs" else "summary")
            if body:
                out.append(experiment_body(body, typeset) if section == "experiments" else markdown(body, typeset))
            if section == "experiments":
                metrics = records(row.get("metrics"), 100)
                if metrics:
                    out.extend([r"\begin{longtable}{@{}p{.47\linewidth}p{.46\linewidth}@{}}",
                                r"\toprule 指标 & 工具记录值\\\midrule\endhead"])
                    for m in metrics:
                        out.append(inline(clean(m.get("label"), 250), typeset) + " & " +
                                   inline(clean(m.get("value"), 350), typeset) + r" \\")
                    out.append(r"\bottomrule\end{longtable}")
            cite(row)
    return "\n".join(out) + "\n\\end{document}\n"


def render_report(evidence: dict, out_dir: Path, *, compile_pdf: bool = True) -> dict:
    """Return artifact names relative to out_dir. A failed build still saves the source."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tex, pdf = out_dir / "report.tex", out_dir / "report.pdf"
    if tex.is_symlink() or pdf.is_symlink():
        raise ValueError("report destination must not be a symlink")
    if tex.exists():
        with tex.open(encoding="utf-8") as f:
            if f.readline() != MARKER:
                raise FileExistsError("report.tex already exists and belongs to another document")
    elif pdf.exists():
        raise FileExistsError("report.pdf already exists without its generated source")
    source = build_tex(evidence)
    receipt = {"tex": tex.name, "pdf": None, "compile_status": "disabled", "message": "已保存 LaTeX 源文件。"}
    engine = shutil.which("xelatex") if compile_pdf else None
    with tempfile.TemporaryDirectory(dir=out_dir, prefix=".report-") as tmp:
        work = Path(tmp)
        draft = work / tex.name
        rendered = work / pdf.name
        draft.write_text(source, encoding="utf-8")
        if compile_pdf and not engine:
            receipt.update(compile_status="unavailable", message="未找到 XeLaTeX。可在安装中文 TeX 支持后编译源文件。")
        if engine:
            cmd = [engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
                   "-file-line-error", tex.name]
            for attempt in range(2):
                if attempt:
                    # Bad model math (e.g. double subscripts) cannot invalidate the report.
                    draft.write_text(build_tex(evidence, typeset=False), encoding="utf-8")
                try:
                    run = subprocess.run(cmd, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, timeout=100, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    break
                if run.returncode == 0 and rendered.is_file() and rendered.stat().st_size:
                    receipt.update(pdf=pdf.name, compile_status="compiled",
                                   message="已生成 PDF。" if not attempt else "已生成 PDF。部分公式语法需人工检查，正文保留原始表达式。")
                    break
            if not receipt["pdf"]:
                receipt.update(compile_status="failed", message="XeLaTeX 编译未完成。已保留源文件，请检查中文 TeX 环境及研究材料。")
        os.replace(draft, tex)
        if receipt["pdf"]:
            os.replace(rendered, pdf)
        else:
            pdf.unlink(missing_ok=True)
    return receipt
