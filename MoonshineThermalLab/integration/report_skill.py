"""Post-archive integration for the project's installed Moonshine reporting skill."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tempfile
import uuid


SLUG = "latex-research-report"
ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "project_skills" / SLUG / "SKILL.md"
# SHA-256 of the complete v1 native installed file with LF line endings.
# This is also independently archived at report_example/installed_skill.md.
RELEASED_V1 = "76501f76335d412a6d790517b3375908a1a93dd0738eafa9739de6e5364c3f62"
TURN_FILES = ("input.txt", "integration.json", "moonshine_events.jsonl", "turn_summary.json")
OUTPUTS = {"report_input.json", "load_skill_definition.json", "report.tex", "report.pdf"}
SELECTIONS = {
    "research_question": "turn_prompt",
    "proofs": "reviewed_blueprint_or_submitted_proof",
    "experiments": "python_tool_results",
    "reviews": "chronological_reviews_and_archive",
    "sources": "turn_file_digests",
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path, value):
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        tmp.write_bytes(json_bytes(value))
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def local(base, name):
    path = base / name
    if path.resolve() != path or not path.is_relative_to(base):
        raise ValueError("报告路径超出本轮目录或包含重定向。")
    return path


def portable_workspace_path(value):
    value = str(value or "").replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        return ""
    return path.as_posix() if value else ""


def load_definition(home, project, session, app, *, course_paper=False):
    from integration.codex_provider import _budget_lock
    from moonshine.moonshine_cli.config import ensure_runtime_home, load_config
    from moonshine.moonshine_constants import MoonshinePaths
    from moonshine.skills.manager import SkillManager
    from moonshine.skills.skill_document import ensure_valid_skill_document, parse_skill_document
    from moonshine.tools.manager import ToolManager

    paths = app.paths if app else MoonshinePaths(home)
    if app is None:
        ensure_runtime_home(paths)
    skills = app.skill_manager if app else SkillManager(paths)
    tools = app.tool_manager if app else ToolManager(paths)
    config = app.config if app else load_config(paths)
    meta, body = parse_skill_document(DEFINITION.read_text(encoding="utf-8"))
    ensure_valid_skill_document(meta, body, expected_name=SLUG)
    installed = local(home, Path("skills") / "installed" / SLUG / "SKILL.md")
    lock = local(home, Path("skills") / (SLUG + ".lock"))
    with _budget_lock(lock):
        existing = skills.get_skill(SLUG)
        if existing is None:
            skills.create_skill(slug=SLUG, title=meta["metadata"]["title"],
                                description=meta["description"], body=body, category="installed")
        elif Path(existing.path).resolve() != installed:
            raise ValueError("同名已安装技能与项目定义冲突，请检查 Moonshine home 中的技能。")
        elif existing.body.strip() != body.strip():
            # Only the exact released v1 may be upgraded. Local body and
            # frontmatter edits both survive a conflicting upgrade attempt.
            previous = installed.read_text(encoding="utf-8").encode("utf-8")
            if hashlib.sha256(previous).hexdigest() != RELEASED_V1:
                raise ValueError("本机同名技能已有个人改动，请检查 Moonshine home 中的技能。")
            skills.edit_skill(slug=SLUG, title=meta["metadata"]["title"],
                              description=meta["description"], body=body)
        registered = skills.list_skills()["installed"]
        if not any(s["slug"] == SLUG and Path(s["path"]).resolve() == installed for s in registered):
            raise ValueError("Moonshine 已安装技能注册表未返回该技能。")
        audit_file = paths.skills_audit_log
        offset = audit_file.stat().st_size if audit_file.exists() else 0
        arguments = {"slug": SLUG}
        result = tools.dispatch("load_skill_definition", arguments, {
            "skill_manager": skills, "mode": "research", "session_id": session,
            "project_slug": project, "exposure": config.exposure,
        })
        with audit_file.open("rb") as stream:
            stream.seek(offset)
            audit = [json.loads(line) for line in stream if line.strip()]
    match = next((entry for entry in audit if entry.get("event") == "skill_load"
                  and entry.get("slug") == SLUG and entry.get("session_id") == session
                  and entry.get("project_slug") == project), None)
    if match is None or result["slug"] != SLUG or result["body"].strip() != body.strip():
        raise ValueError("原生技能加载回执与本轮身份或已安装内容不一致。")
    section_name = "Course Paper Layout" if course_paper else "Evidence Layout"
    section = result["sections"].get(section_name, "").strip().splitlines()
    if len(section) < 3 or section[0] != chr(96) * 3 + "json" or section[-1] != chr(96) * 3:
        raise ValueError("技能缺少有效的 " + section_name + "。")
    layout = json.loads("\n".join(section[1:-1]))
    if course_paper:
        required = {"problem", "bounds", "four_cell", "research", "experiments", "discussion", "sources"}
        if (not isinstance(layout, list) or len(layout) != len(required)
                or not all(isinstance(key, str) for key in layout) or set(layout) != required):
            raise ValueError("综合论文布局缺少章节、包含重复章节或存在未知章节。")
    elif not isinstance(layout, dict) or not layout or any(SELECTIONS.get(k) != v for k, v in layout.items()):
        raise ValueError("技能指定了不受支持的证据栏或材料类型。")
    native_hash = hashlib.sha256(json_bytes(result)).hexdigest()
    public_result = dict(result, path=installed.relative_to(home).as_posix())
    return layout, {
        "tool": "load_skill_definition", "arguments": arguments, "project": project,
        "session_id": session, "registry": "installed", "native_skill_audit": match,
        "dispatch": "Moonshine.ToolManager.dispatch", "native_response_sha256": native_hash,
        "path_base": "Moonshine runtime home", "output": public_result,
        "skill_source_sha256": sha(DEFINITION), "installed_file_sha256": sha(installed),
    }


def event_ref(number):
    return f"moonshine_events.jsonl#L{number}"


def records(events):
    for number, event in enumerate(events, 1):
        if event.get("type") == "tool_result":
            payload = event["payload"]
            yield number, event["text"], payload, payload.get("output") or {}


def valid_review(payload, result, project):
    return (not payload.get("error") and result.get("project_slug", project) == project
            and result.get("passed") is True)


def proof_material(events, project):
    writes, proofs = {}, []
    for number, name, payload, result in records(events):
        args = payload.get("arguments") or {}
        path = portable_workspace_path(args.get("path"))
        if (name == "mcp_filesystem_write_file" and not payload.get("error")
                and result.get("status") == "ok" and path.lower().endswith((".md", ".txt"))
                and isinstance(args.get("content"), str)):
            writes[path] = (number, args["content"])
        if name != "verify_overall" or not valid_review(payload, result, project):
            continue
        blueprint = portable_workspace_path(args.get("blueprint_path") or result.get("blueprint_path"))
        line, body = writes.get(blueprint, (number, ""))
        if not body.strip():
            body = str(args.get("proof") or "").strip()
            line = number
        if body:
            proofs.append({
                "title": f"审核对应的推导 {len(proofs) + 1}", "text": body,
                "source": event_ref(line) + (f"（{blueprint}）" if line != number else "（送审证明）"),
            })
    return proofs


def experiments(events):
    outputs = []
    for number, name, payload, result in records(events):
        if name != "run_python_script":
            continue
        path = portable_workspace_path(result.get("relative_path") or payload.get("arguments", {}).get("path"))
        code = result.get("returncode")
        success = not payload.get("error") and code == 0
        stdout = str(result.get("stdout") or "").strip()
        stderr = str(result.get("stderr") or payload.get("error") or result.get("error") or "").strip()
        chunks = ["标准输出\n" + stdout] if stdout else []
        if stderr:
            chunks.append("标准错误或工具错误\n" + stderr)
        outputs.append({
            "title": path or f"Python 执行 {len(outputs)+1}", "source": event_ref(number),
            "status": "成功" if success else "未成功",
            "metrics": [{"label": "退出码", "value": str(code) if code is not None else "无"}],
            "summary": "\n\n".join(chunks) or "该回执没有标准输出或标准错误。",
        })
    return outputs


def reviews(events, outcome):
    items = []
    for number, name, payload, result in records(events):
        if name != "verify_overall":
            continue
        scope = str(result.get("scope") or payload.get("arguments", {}).get("scope") or "未注明")
        remark = str(result.get("summary") or payload.get("error") or result.get("overall_verdict") or "")
        items.append({"label": f"第 {len(items)+1} 次审核（{scope}）", "source": event_ref(number),
                      "status": "通过" if not payload.get("error") and result.get("passed") is True else "未通过",
                      "summary": remark})
    items.append({"label": "本轮归档", "source": "turn_summary.json",
                  "status": "已记录", "summary": f"原生结束回执记录 {outcome['archived_records']} 条归档。"})
    return items


def report_inputs(folder, summary, events, meta, layout, hashes):
    project = meta["project"]
    question = (folder / "input.txt").read_text(encoding="utf-8").split("\n\n题面备份：", 1)[0].strip()
    header = next((line.lstrip("# ").strip() for line in question.splitlines() if line.startswith("# ")), "")
    first_line = next((line.strip() for line in question.splitlines() if line.strip()), "")
    title = header or (first_line if 1 <= len(first_line) <= 85 else "研究轮次报告")
    data = {"title": title,
            "project": project, "session_id": summary["session_id"], "turn_id": folder.name,
            "model": summary["model"], "status": "本轮局部结果已执行、审核并归档。",
            "sections": list(layout)}
    extractors = {
        "turn_prompt": lambda: question,
        "reviewed_blueprint_or_submitted_proof": lambda: proof_material(events, project),
        "python_tool_results": lambda: experiments(events),
        "chronological_reviews_and_archive": lambda: reviews(events, summary["outcome"]),
        "turn_file_digests": lambda: [{"label": name, "path": name, "sha256": hashes[name]} for name in TURN_FILES],
    }
    for section, selector in layout.items():
        data[section] = extractors[selector]()
    if "proofs" in layout and not data["proofs"]:
        raise ValueError("通过审核的原生回执没有可引用的证明或本轮蓝图，请补充推导。")
    return data


def skip_reason(summary, events, meta, project):
    from run_moonshine import research_outcome
    if meta.get("project") != project or meta.get("mode") != "research" or meta.get("model") != summary.get("model"):
        raise ValueError("报告输入中的项目、模式或模型不匹配。")
    if not summary.get("session_id"):
        raise ValueError("轮次摘要缺少会话标识。")
    finals = [e for e in events if e.get("type") == "final"]
    tools = [e for e in events if e.get("type") == "tool_result"]
    if finals != summary.get("final_events") or research_outcome(finals, tools) != summary.get("outcome"):
        raise ValueError("原生事件与结束摘要不一致，需核对本轮证据后重试。")
    if summary.get("error") or summary.get("source_preserved") is not True:
        return "研究中断或源码身份未确认。"
    if not summary["outcome"]["accepted_local_research_step"]:
        return "尚未同时取得成功执行、审核通过与归档记录。"
    observed = [(p, r) for _, n, p, r in records(events) if n == "verify_overall"]
    if not observed or not valid_review(*observed[-1], project):
        return "最后一次审核没有确认本项目本轮结论。"
    return ""


def preserve_previous(out):
    """Keep even manually edited products before a new attempt becomes current."""
    files = [local(out, name) for name in sorted(OUTPUTS | {"receipt.json"})]
    files = [path for path in files if path.is_file()]
    if not files:
        return None
    history = local(out, Path("previous") / uuid.uuid4().hex)
    history.mkdir(parents=True)
    for path in files:
        path.replace(history / path.name)
    return history.relative_to(out).as_posix()


def run_report_skill(folder: Path, home: Path, project: str, *, app=None):
    """Finalize one turn. Repeating a verified export is a no-op; failures can be retried."""
    from integration.codex_provider import _budget_lock

    folder, home = Path(folder).resolve(), Path(home).resolve()
    if folder.parent != home.parent / "evidence" or not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{8}", folder.name):
        raise ValueError("报告仅接受当前项目的本地轮次目录。")
    out = local(folder, "report")
    out.mkdir(exist_ok=True)
    receipt_path = local(out, "receipt.json")
    with _budget_lock(local(out, ".report.lock")):
        receipt = {"schema": 1, "skill": SLUG, "turn_id": folder.name, "project": project,
                   "invocation": "automatic_after_research" if app else "manual_retry",
                   "dispatch": "Moonshine.ToolManager.dispatch/load_skill_definition",
                   "generation": "evidence-driven, no additional model call",
                   "started_at_utc": datetime.now(timezone.utc).isoformat(),
                   "status": "processing", "inputs": {}, "outputs": {}}
        prepared = False
        try:
            for name in TURN_FILES:
                path = local(folder, name)
                if path.is_file():
                    receipt["inputs"][name] = sha(path)
            receipt["inputs"].update({
                "project_skill": sha(DEFINITION), "report_adapter": sha(Path(__file__)),
                "report_renderer": sha(ROOT / "integration" / "report_latex.py"),
                "runner": sha(ROOT / "run_moonshine.py"),
            })
            if receipt_path.is_file():
                try:
                    previous = read_json(receipt_path)
                except (OSError, ValueError):
                    previous = {}
                previous = previous if isinstance(previous, dict) else {}
                outputs = previous.get("outputs") or {}
                if (previous.get("status") == "compiled" and previous.get("project") == project
                        and previous.get("inputs") == receipt["inputs"]
                        and set(outputs) == OUTPUTS and all(local(out, k).is_file() and sha(out / k) == v
                                                           for k, v in outputs.items())):
                    return previous
            prior = preserve_previous(out)
            prepared = True
            if prior:
                receipt["previous_attempt"] = prior
            write_json(receipt_path, receipt)
            summary = read_json(folder / "turn_summary.json")
            receipt["session_id"] = summary["session_id"]
            meta = read_json(folder / "integration.json")
            events = [json.loads(line) for line in (folder / "moonshine_events.jsonl").read_text(encoding="utf-8").splitlines()]
            reason = skip_reason(summary, events, meta, project)
            if reason:
                receipt.update(status="skipped", message=reason)
            else:
                layout, loaded = load_definition(home, project, summary["session_id"], app)
                write_json(local(out, "load_skill_definition.json"), loaded)
                receipt["outputs"]["load_skill_definition.json"] = sha(out / "load_skill_definition.json")
                data = report_inputs(folder, summary, events, meta, layout, receipt["inputs"])
                write_json(local(out, "report_input.json"), data)
                receipt["outputs"]["report_input.json"] = sha(out / "report_input.json")
                write_json(receipt_path, receipt)
                from integration.report_latex import render_report
                with tempfile.TemporaryDirectory(prefix=".render-", dir=out) as tmp:
                    stage = Path(tmp)
                    result = render_report(data, stage, compile_pdf=True)
                    status = result["compile_status"]
                    if result["tex"] != "report.tex" or (result.get("pdf") not in (None, "report.pdf")):
                        raise ValueError("报告排版器返回了无效的文件路径。")
                    names = ["report.tex"]
                    if status == "compiled":
                        if result.get("pdf") != "report.pdf":
                            raise ValueError("报告排版器未提供所声明的 PDF。")
                        names.append("report.pdf")
                    if any(sha(local(folder, k)) != receipt["inputs"][k] for k in TURN_FILES):
                        raise ValueError("报告生成期间原始输入发生变化，请核对并重试。")
                    for name in names:
                        path = local(stage, name)
                        if not path.is_file() or path.stat().st_size == 0:
                            raise ValueError("报告排版器缺少所声明的非空成品。")
                        path.replace(local(out, name))
                        receipt["outputs"][name] = sha(out / name)
                receipt.update(status={"compiled": "compiled", "unavailable": "tex_only",
                                       "disabled": "tex_only"}.get(status, "failed"),
                               compile_status=status, message=result.get("message") or "")
        except Exception as exc:
            receipt.update(status="failed", message=str(exc) or type(exc).__name__)
            if not prepared:
                prior = preserve_previous(out)
                if prior:
                    receipt["previous_attempt"] = prior
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(receipt_path, receipt)
        return receipt

