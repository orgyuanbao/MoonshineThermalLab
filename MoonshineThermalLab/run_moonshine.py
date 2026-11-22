"""Run the original Moonshine research loop through a local Codex provider.

The upstream source is pinned and unchanged. The adapter supplies only model
responses; Moonshine itself executes the project tools and verification flow.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT
HOME = ROOT / "home"
SOURCE = ROOT / "source"
PROJECT = "harmony-active-ranging"
TITLE = "Moonshine 鸿蒙定位研究试用"
CONTINUE_PROMPT = (
    "继续同一鸿蒙定位数学子问题。先读取项目研究记忆和第一轮程序，针对最坏误差、"
    "阈值等号、多次测量或程序精确性寻找反例和漏洞，实际运行复核并修订。"
    "保留原程序版本和失败信息。用 verify_overall(scope='intermediate',review_count=1)"
    "审核修订后的局部结论，保存中文复核说明。"
)
ENTRYPOINT = None
COMMIT = "bb0e4aa025fdcc5297fff1025ab4876f120ed615"
TOOLS = [
    "query_memory", "load_skill_definition", "load_tool_definition", "read_runtime_file",
    "mcp_filesystem_write_file", "mcp_filesystem_read_file", "mcp_filesystem_list_directory",
    "run_python_script", "assess_problem_quality", "verify_overall",
]


def select_project(data_root, *, project, title, continue_prompt, entrypoint=None):
    """Select a separately stored project before constructing the upstream app."""
    import re
    global DATA_ROOT, HOME, PROJECT, TITLE, CONTINUE_PROMPT, ENTRYPOINT
    candidate = Path(data_root).resolve()
    if candidate == ROOT or ROOT not in candidate.parents:
        raise ValueError("新题的数据目录必须是启动器目录下的独立子目录。")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project):
        raise ValueError("研究项目标识无效。")
    if not (candidate / "problem.md").is_file():
        raise ValueError("新题缺少 problem.md 题面。")
    saved_path = candidate / "active_session.json"
    if saved_path.exists():
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
        if saved.get("project") != project or saved.get("mode") != "research":
            raise ValueError("新题保存的会话身份不匹配。")
    DATA_ROOT, HOME, PROJECT = candidate, candidate / "home", project
    TITLE, CONTINUE_PROMPT = title, continue_prompt
    ENTRYPOINT = Path(entrypoint).resolve() if entrypoint else None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    from integration.source_integrity import source_identity as pinned_source_identity
    identity = pinned_source_identity(SOURCE, ROOT / "source_manifest.json")
    if identity["commit"] != COMMIT:
        raise ValueError("Runner commit and pinned source manifest do not match.")
    return identity


def bootstrap_runtime():
    from integration.moonshine_bootstrap import bootstrap_moonshine
    return bootstrap_moonshine(SOURCE, ROOT / "source_manifest.json")


def resolve_evidence_reference(value):
    """Resolve old absolute or new relative indexes only inside current DATA_ROOT.

    Historical evidence contents are never rewritten. Even when the old absolute
    location still exists, it is not read; its run identifier selects this copy.
    """
    import re
    from pathlib import PurePosixPath, PureWindowsPath
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if any(part in {".", ".."} for part in parts):
        raise ValueError("研究证据索引不允许相对跳转。")
    windows = PureWindowsPath(value)
    absolute = PurePosixPath(normalized).is_absolute() or windows.is_absolute()
    if windows.drive and not windows.is_absolute():
        raise ValueError("研究证据索引不允许驱动器相对路径。")
    if not absolute and (len(parts) != 2 or normalized != "/".join(parts)):
        raise ValueError("研究证据索引必须是 evidence/<runid>。")
    if len(parts) < 2 or parts[-2] != "evidence":
        raise ValueError("研究证据索引不属于 evidence 目录。")
    run_id = parts[-1]
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{8}", run_id):
        raise ValueError("研究证据轮次标识无效。")
    data_root = DATA_ROOT.resolve()
    evidence_root = (data_root / "evidence").resolve()
    if not evidence_root.is_relative_to(data_root):
        raise ValueError("研究证据目录不能指向当前项目以外。")
    candidate = (evidence_root / run_id).resolve()
    if candidate.parent != evidence_root:
        raise ValueError("研究证据轮次不能指向当前证据目录以外。")
    return candidate


def current_model():
    preference = DATA_ROOT / "model.json"
    if preference.exists():
        model = json.loads(preference.read_text(encoding="utf-8"))["model"]
    else:
        config = Path.home() / ".codex" / "config.toml"
        model = tomllib.loads(config.read_text(encoding="utf-8")).get("model")
    if not isinstance(model, str) or not model.strip() or any(c.isspace() for c in model) or model.startswith("-"):
        raise ValueError("没有有效的模型选择，请用 --model 指定本机可用的模型。")
    return model


def optional_current_model():
    """Read a display preference without making model setup a menu requirement.

    Research and provider construction continue to use current_model directly;
    this fallback never supplies a default model or launches a request.
    """
    try:
        return current_model()
    except (OSError, ValueError, KeyError, TypeError):
        return None


def model_display():
    return optional_current_model() or "未配置；可在菜单选 4 选择模型，开始研究前需完成配置"


def configure_home(model):
    bootstrap_runtime()
    from moonshine.moonshine_cli.config import ensure_runtime_home
    from moonshine.moonshine_constants import MoonshinePaths
    ensure_runtime_home(MoonshinePaths(HOME))
    settings_path = HOME / "config" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for name in ("provider", "verification_provider", "archival_provider"):
        settings[name].update(type="codex_cli", model=model, stream=False, reasoning_effort="high")
        if name != "provider":
            settings[name]["inherit_from_main"] = False
    settings["memory"].update(auto_extract=False, knowledge_vector_enabled=False)
    settings["agent"].update(max_model_rounds=8, max_tool_rounds=7, max_tool_calls_per_round=3,
                              max_tool_validation_retries=1, max_empty_response_retries=0,
                              max_consecutive_errors=1,
                              research_max_iterations=1, verification_dimension_review_count=1,
                              research_final_report_enabled=True, research_final_report_retries=1)
    settings["exposure"]["tools_include"] = TOOLS
    write_json(settings_path, settings)
    return settings


def build_app(model, evidence, *, max_calls=16):
    bootstrap_runtime()
    import moonshine.app as implementation
    from integration.codex_provider import CodexCLIProvider
    providers = {name: CodexCLIProvider(evidence_root=evidence, model=model, max_calls=max_calls,
                                      timeout_seconds=300, role=name)
                 for name in ("main", "verification", "archival")}
    with patch.object(implementation, "resolve_runtime_provider", lambda config: providers["main"]), \
         patch.object(implementation, "resolve_verification_provider", lambda config, **kwargs: providers["verification"]), \
         patch.object(implementation, "resolve_archival_provider", lambda config, **kwargs: providers["archival"]):
        app = implementation.MoonshineApp(home=str(HOME))
    return app


def research_outcome(finals, tool_results):
    """Classify observed work, including upstream failure termination reasons."""
    reason = finals[-1].get("payload", {}).get("reason", "") if finals else "no_final_message"
    fatal = reason in {
        "no_final_message", "provider_error", "provider_errors_exhausted", "provider_offline",
        "verification_provider_offline", "archival_provider_offline", "tool_validation_exhausted",
        "empty_response_exhausted",
    }
    experiments = [item for item in tool_results if item.get("text") == "run_python_script"
                   and not item.get("payload", {}).get("error")
                   and item.get("payload", {}).get("output", {}).get("returncode") == 0]
    verified = [item for item in tool_results if item.get("text") == "verify_overall"
                and not item.get("payload", {}).get("error")
                and item.get("payload", {}).get("output", {}).get("passed") is True]
    archive = (finals[-1].get("payload", {}).get("research_workflow", {}).get("research_log_archive", {})
               if finals else {})
    archived = archive.get("archived", 0)
    archived = archived if isinstance(archived, int) and not isinstance(archived, bool) else 0
    return {"final_reason": reason, "runtime_failure": fatal,
            "successful_python_executions": len(experiments), "passed_verifications": len(verified),
            "archived_records": archived,
            "accepted_local_research_step": bool(not fatal and experiments and verified and archived > 0),
            "industrial_problem_solved_asserted": False}


def switch_model():
    bootstrap_runtime()
    from integration.codex_provider import codex_environment, resolve_codex_executable
    existing_model = optional_current_model()
    print("正在读取可选模型……", flush=True)
    try:
        response = subprocess.run([resolve_codex_executable(), "debug", "models"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=30, env=codex_environment())
        if response.returncode:
            raise RuntimeError("读取模型目录失败，请检查 Codex 登录和网络。")
        available = [item for item in json.loads(response.stdout)["models"]
                     if item.get("visibility") == "list" and "high" in {
                         level.get("effort") for level in item.get("supported_reasoning_levels", [])}]
        if not available:
            raise ValueError("没有读到支持当前推理设置的模型。")
        for number, item in enumerate(available, 1):
            marker = " [当前]" if item["slug"] == existing_model else ""
            print(f"{number}  {item.get('display_name', item['slug'])} ({item['slug']}){marker}")
        answer = input("选择模型编号，直接回车取消：").strip()
        if not answer:
            return
        if not answer.isdecimal() or not 1 <= int(answer) <= len(available):
            print("没有这个编号。")
            return
        from integration.codex_provider import CodexCLIProvider
        model = available[int(answer)-1]["slug"]
        CodexCLIProvider(evidence_root=DATA_ROOT / "checks", model=model)
        write_json(DATA_ROOT / "model.json", {"model": model})
        print("已保存：", model, "；从下一轮研究生效。")
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print("切换未成功：", exc)


def show_status():
    selection = DATA_ROOT / "active_session.json"
    print("Moonshine 原版研究模式；本地 Codex CLI 模型适配。")
    print("模型：", model_display(), "；推理强度：high")
    if selection.is_file():
        saved = json.loads(selection.read_text(encoding="utf-8"))
        print("研究会话：", saved["session_id"])
        evidence = resolve_evidence_reference(saved.get("latest_evidence"))
        print("最新运行记录：", evidence if evidence else "尚无")
        summary = evidence / "turn_summary.json" if evidence else None
        if summary is not None and summary.is_file():
            data = json.loads(summary.read_text(encoding="utf-8"))
            if "outcome" not in data:
                events = [json.loads(line) for line in summary.with_name("moonshine_events.jsonl").read_text(encoding="utf-8").splitlines()]
                data["outcome"] = research_outcome(data.get("final_events", []),
                                                   [item for item in events if item.get("type") == "tool_result"])
            print("最近一轮：", "局部研究步骤已验证并归档" if data["outcome"]["accepted_local_research_step"]
                  else "存在失败或尚缺执行、审核、归档证据，请查看记录。")
            receipt = evidence / "report" / "receipt.json"
            if receipt.is_file():
                report = json.loads(receipt.read_text(encoding="utf-8"))
                print("LaTeX 报告：", report["status"], receipt.parent)
        else:
            print("最近一轮：尚无结束摘要，可能仍在运行，或这份副本未包含该历史记录。")
    else:
        print("尚未发起研究。")
    print("研究目录：", HOME / "projects" / PROJECT)


def report_for_turn(evidence, *, app=None):
    """Dispatch the installed report skill without making a model request."""
    from integration.report_skill import run_report_skill
    result = run_report_skill(evidence, HOME, PROJECT, app=app)
    print("LaTeX 报告：", result["status"], result.get("message", ""), evidence / "report", flush=True)
    return result


def retry_report(turn=None):
    if turn:
        evidence = resolve_evidence_reference("evidence/" + turn)
    else:
        selection = json.loads((DATA_ROOT / "active_session.json").read_text(encoding="utf-8"))
        evidence = resolve_evidence_reference(selection["latest_evidence"])
    if evidence is None or not (evidence / "turn_summary.json").is_file():
        raise ValueError("所选轮次缺少结束摘要。")
    bootstrap_runtime()
    result = report_for_turn(evidence)
    return 0 if result["status"] in {"compiled", "tex_only"} else 2


def run_research(prompt_file=None, *, model=None, max_calls=16):
    model = model or current_model()
    identity = source_identity()
    settings = configure_home(model)
    turn = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    evidence = DATA_ROOT / "evidence" / turn
    evidence.mkdir(parents=True, exist_ok=False)
    write_json(evidence / "source.json", identity)
    write_json(evidence / "settings.json", settings)
    write_json(evidence / "integration.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "reasoning_effort": "high", "mode": "research", "project": PROJECT,
        "max_provider_calls": max_calls,
        "provider_timeout_seconds": 300,
        "runner_sha256": digest(Path(__file__)),
        "provider_sha256": digest(ROOT / "integration" / "codex_provider.py"),
        "source_integrity_sha256": digest(ROOT / "integration" / "source_integrity.py"),
        "moonshine_bootstrap_sha256": digest(ROOT / "integration" / "moonshine_bootstrap.py"),
        "source_manifest_sha256": digest(ROOT / "source_manifest.json"),
        "problem_sha256": digest(DATA_ROOT / "problem.md"),
        "entrypoint_sha256": digest(ENTRYPOINT) if ENTRYPOINT else None,
        "description": "Original Moonshine orchestrator/tools/verification/archive; custom Codex CLI model provider.",
    })
    snapshot = evidence / "integration_source"
    snapshot.mkdir()
    (snapshot / "run_moonshine.py").write_bytes(Path(__file__).read_bytes())
    (snapshot / "codex_provider.py").write_bytes((ROOT / "integration" / "codex_provider.py").read_bytes())
    (snapshot / "source_integrity.py").write_bytes((ROOT / "integration" / "source_integrity.py").read_bytes())
    (snapshot / "moonshine_bootstrap.py").write_bytes((ROOT / "integration" / "moonshine_bootstrap.py").read_bytes())
    (snapshot / "source_manifest.json").write_bytes((ROOT / "source_manifest.json").read_bytes())
    (snapshot / "problem.md").write_bytes((DATA_ROOT / "problem.md").read_bytes())
    if ENTRYPOINT:
        (snapshot / "entrypoint.py").write_bytes(ENTRYPOINT.read_bytes())
    project_root = HOME / "projects" / PROJECT
    os.environ["MOONSHINE_MCP_FILESYSTEM_ROOT"] = str(project_root)
    app = build_app(model, evidence, max_calls=max_calls)
    app.ensure_project(PROJECT)
    selection = DATA_ROOT / "active_session.json"
    saved = json.loads(selection.read_text(encoding="utf-8")) if selection.is_file() else {}
    if saved and (saved.get("project") != PROJECT or saved.get("mode") != "research"):
        raise ValueError("保存的 Moonshine 会话身份不匹配。")
    state = app.start_shell_state(mode="research", project_slug=PROJECT, session_id=saved.get("session_id"))
    staged = app.stage_input_file(str(DATA_ROOT / "problem.md"), project_slug=PROJECT)
    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8")
    elif saved:
        prompt = CONTINUE_PROMPT
    else:
        prompt = (DATA_ROOT / "problem.md").read_text(encoding="utf-8")
    prompt += ("\n\n题面备份：" + staged["relative_path"] +
               "\n本轮最多8次主模型轮次，总模型调用受外层预算限制。请高效推进实质研究，"
               "完整写出程序后用原版工具实际运行，不把计划当成执行结果。")
    (evidence / "input.txt").write_text(prompt, encoding="utf-8")
    write_json(selection, {"mode": "research", "project": PROJECT, "session_id": state.session_id,
                           "latest_evidence": evidence.relative_to(DATA_ROOT).as_posix()})
    print("Moonshine 研究已启动。模型：", model, flush=True)
    print("会话：", state.session_id, "；预算：", max_calls, "次模型调用", flush=True)
    started = time.monotonic()
    stopped = threading.Event()

    def heartbeat():
        while not stopped.wait(15):
            print("[等待] Moonshine 仍在研究，已用时 {} 秒。".format(int(time.monotonic() - started)), flush=True)

    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    finals = []
    tool_results = []
    outcome = research_outcome([], [])
    error = None
    try:
        with (evidence / "moonshine_events.jsonl").open("x", encoding="utf-8") as events:
            for event in app.run_research_autopilot_events(prompt, state, max_iterations=1):
                item = asdict(event)
                events.write(json.dumps(item, ensure_ascii=False) + "\n")
                events.flush()
                if event.type in {"status", "tool_call", "tool_result"}:
                    print("[{}] {}".format(event.type, event.text[:400]), flush=True)
                if event.type == "tool_result":
                    tool_results.append(item)
                if event.type == "final":
                    finals.append(item)
                    print("\n" + event.text, flush=True)
        if not finals:
            raise RuntimeError("Moonshine 本轮没有生成最终消息，请查看保存的事件。")
        outcome = research_outcome(finals, tool_results)
        if outcome["runtime_failure"]:
            raise RuntimeError("Moonshine 未完成研究调用：" + outcome["final_reason"])
    except BaseException as exc:
        error = str(exc) or type(exc).__name__
        raise
    finally:
        stopped.set()
        worker.join(timeout=1)
        write_json(evidence / "turn_summary.json", {
            "session_id": state.session_id, "model": model, "elapsed_seconds": time.monotonic() - started,
            "error": error, "final_events": finals, "outcome": research_outcome(finals, tool_results),
            "tools_executed": [item["text"] for item in tool_results],
            "source_preserved": source_identity() == identity,
        })
        try:
            report_for_turn(evidence, app=app)
        except Exception as exc:
            print("报告步骤未完成。研究记录已保存，可用 report 命令重试。", exc, flush=True)
        finally:
            app.close_session(state)
        print("本轮记录：", evidence, flush=True)
        print("研究产物：", project_root, flush=True)
    if outcome["accepted_local_research_step"]:
        print("本轮局部研究已取得程序执行、审核与归档证据。", flush=True)
        return 0
    print("本轮仅为部分进展；尚缺完整的程序执行、审核或归档证据。", flush=True)
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["check", "run", "status", "report"])
    parser.add_argument("--turn", help="指定需要重新排版的研究轮次，默认取当前项目最近一轮")
    parser.add_argument("--model")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.max_calls <= 24:
        parser.error("--max-calls 必须在 1 到 24 之间")
    if args.model:
        bootstrap_runtime()
        from integration.codex_provider import CodexCLIProvider
        CodexCLIProvider(evidence_root=DATA_ROOT / "checks", model=args.model, max_calls=args.max_calls)
        write_json(DATA_ROOT / "model.json", {"model": args.model})
    if args.action == "check":
        identity = source_identity()
        configure_home(current_model())
        app = build_app(current_model(), DATA_ROOT / "checks", max_calls=args.max_calls)
        names = {item["name"] for item in app.tool_manager.schemas(mode="research", include=TOOLS)}
        missing = set(TOOLS) - names
        if missing:
            raise RuntimeError("Moonshine 工具缺失：" + ", ".join(sorted(missing)))
        print(json.dumps({"upstream_commit": identity["commit"], "model": current_model(),
                          "tools": sorted(names), "check": "passed", "model_calls": 0}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "status":
        show_status()
        return 0
    if args.action == "report":
        return retry_report(args.turn)
    if args.action == "run":
        return run_research(args.prompt_file, model=args.model, max_calls=args.max_calls)
    print(TITLE)
    while True:
        print("\n当前模型：", model_display())
        print("1  开始 / 继续一轮 Moonshine 研究\n2  查看会话和结果位置\n3  打开研究文件夹\n4  切换模型\n0  退出")
        answer = input("请输入数字并回车：").strip()
        if answer == "0":
            return 0
        if answer == "1":
            try:
                run_research(max_calls=args.max_calls)
            except Exception as exc:
                print("本轮未完成：", exc)
        elif answer == "2":
            show_status()
        elif answer == "3":
            path = HOME / "projects" / PROJECT
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        elif answer == "4":
            switch_model()
        else:
            print("请选择 0 到 4。")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n已停止，已有研究记录保留。")
        raise SystemExit(130)
    except Exception as error:
        print("无法继续：", error, file=sys.stderr, flush=True)
        raise SystemExit(1)
