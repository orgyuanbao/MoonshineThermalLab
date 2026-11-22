"""User entry point for the project's independent residual-bound research loop."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from uuid import uuid4

from integration.bound_agent import LOCAL_GOAL, default_policy, get_local_checker, run_agent, scale_bracket
from integration.residual_tool import completed_search


def save_trace(path, data):
    """Publish one complete JSON snapshot on the same filesystem as the destination."""
    tmp = NamedTemporaryFile(mode="w", dir=path.parent, prefix=".trace-", suffix=".tmp",
                             delete=False, encoding="utf-8", newline="\n")
    staging = Path(tmp.name)
    try:
        with tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2, allow_nan=False)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def reserve_trace(path, initial):
    """Serialize competing creators; a successful reservation is already readable JSON."""
    lock = path.with_name(".trace-create.lock")
    lock.open("x").close()
    try:
        if os.path.lexists(path):
            raise FileExistsError(f"已有研究记录，另选一个输出目录：{path}")
        save_trace(path, initial)
    finally:
        lock.unlink()


def investigate(root, *, model=False, goal=None, max_rounds=4, output=None):
    root = Path(root)
    if not model and goal:
        raise ValueError("自定义研究问题请使用 --model；本地模式复算预设的上界收紧问题。")
    policy = default_policy
    if model:
        from integration.bound_agent_model import load_settings, make_model_policy
        envfile = root / ".env"
        if not envfile.exists():
            try:
                with (root / ".env.example").open("rb") as template, envfile.open("xb") as dest:
                    dest.write(template.read())
            except FileExistsError:
                pass
        policy = make_model_policy(load_settings(envfile))
    if type(max_rounds) is not int or not 1 <= max_rounds <= 16:
        raise ValueError("--max-rounds 必须在 1 至 16 之间。")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:10]
    folder = Path(output) if output is not None else root / "thermal" / "bound_agent_runs" / stamp
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / "trace.json"
    research_goal = goal if goal is not None else LOCAL_GOAL
    policy_name = "chat_completions" if model else "exact_feedback"
    snapshot = {"goal": research_goal, "policy": policy_name, "status": "running",
                "reason": "研究进行中。", "history": [], "decisions": [], "scale_bracket": None}
    reserve_trace(receipt, snapshot)
    proposal = {}

    def choose(current_goal, history):
        nonlocal proposal
        proposal = policy(current_goal, history)
        return proposal

    try:
        with TemporaryDirectory(dir=folder, prefix=".moonshine-") as home:
            native_check = get_local_checker(Path(home))

            def check(arguments):
                n = len(snapshot["history"]) + 1
                print(f"第 {n} 轮，检验 {arguments.get('candidate', '?')}，倍数 {arguments.get('scale', '1')}。", flush=True)
                result = native_check(arguments)
                if completed_search(result):
                    reason = proposal.get("reason", "")
                    snapshot["history"].append({"round": n, "arguments": dict(arguments), "result": result, "reason": reason})
                    snapshot["decisions"].append({"action": "check", "arguments": dict(arguments), "reason": reason})
                    snapshot["scale_bracket"] = scale_bracket(snapshot["history"])
                    save_trace(receipt, snapshot)
                    if result["status"] == "counterexample":
                        witness = result["witness"]
                        print(f"找到反例：真实误差 {witness['true_error_inf']}，候选上界 {witness['candidate_bound']}。", flush=True)
                    else:
                        print(f"已检查 {result['checked_cases']} 组，给定有限域内未发现反例。", flush=True)
                return result

            print("自研残差上界研究智能体：" + ("API 模型策略" if model else "本地有理数策略"), flush=True)
            run = run_agent(choose, check, goal=research_goal, max_rounds=max_rounds)
    except KeyboardInterrupt:
        snapshot.update(status="interrupted", reason="研究已中断，已完成的检验保存在本记录中。")
        save_trace(receipt, snapshot)
        raise
    except Exception:
        snapshot.update(status="error", reason="研究未能正常结束，已保留完成的检验。")
        save_trace(receipt, snapshot)
        raise
    run["policy"] = policy_name
    save_trace(receipt, run)
    print(run["reason"], flush=True)
    print("研究记录：", receipt.resolve(), flush=True)
    return 0 if run["status"] in ("finite_search_completed", "counterexample_found") else 2
