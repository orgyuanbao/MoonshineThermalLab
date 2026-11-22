"""State, feedback and stopping rules of the project's Residual Bound Agent."""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path


LOCAL_GOAL = "在指定的四格有限域上检验候选上界；遇到反例则修正，再检验修正式能否按比例收紧。"
DEFAULT_GOAL = LOCAL_GOAL


def get_local_checker(home: Path):
    """Use the same registered mathematical tool as the interactive Moonshine integration."""
    import run_moonshine
    from integration.residual_tool import register_residual_tool, TOOL_NAME

    run_moonshine.bootstrap_runtime()
    from moonshine.moonshine_constants import MoonshinePaths
    from moonshine.tools.manager import ToolManager

    manager = ToolManager(MoonshinePaths(Path(home)))
    register_residual_tool(manager)

    def check(arguments):
        return manager.dispatch(TOOL_NAME, arguments, {"mode": "research"})

    return check


def scale_bracket(history):
    """Bracket the required nonnegative scale for the last formula on its own domain."""
    if not history:
        return None
    last = history[-1]["result"]
    fields = ("candidate", "partition", "grid", "boundary_levels", "residual_values")
    upper, lower = None, Fraction(0)
    for step in history:
        result = step["result"]
        if any(result[key] != last[key] for key in fields):
            continue
        factor = Fraction(result["scale"])
        if result["status"] == "no_counterexample_in_domain":
            upper = factor if upper is None else min(upper, factor)
        else:
            witness = result["witness"]
            base_bound = Fraction(witness["candidate_bound"]) / factor
            if base_bound > 0:
                lower = max(lower, Fraction(witness["true_error_inf"]) / base_bound)
            elif Fraction(witness["true_error_inf"]) > 0:
                if upper is not None:
                    raise ValueError("同一搜索域出现不相容的精确结果。")
                return {"lower": None, "upper": None, "no_finite_scale": True}
    if upper is not None and lower > upper:
        raise ValueError("通过的倍数与精确见证不相容。")
    return {"lower": str(lower), "upper": None if upper is None else str(upper), "no_finite_scale": False}


def local_policy(initial="weak_signed", domain=None):
    """Choose the next conjecture from exact feedback for one fixed search domain."""
    domain = dict(domain or {})
    if set(domain) - {"partition", "boundary_levels", "residual_values"}:
        raise ValueError("未知的搜索域参数。")

    def propose(candidate, scale, reason):
        return {"action": "check", "reason": reason,
                "arguments": {**domain, "candidate": candidate, "scale": str(scale)}}

    def policy(goal, history):
        if not history:
            return propose(initial, 1, "先在给定搜索域检验原始猜想。")
        current = history[-1]["result"]
        candidate = current["candidate"]
        bracket = scale_bracket(history)
        if bracket["upper"] is None:
            if candidate == "block_two_endpoint":
                return {"action": "finish", "reason": "双端点修正式也出现反例；保留见证，需重新推导。"}
            return propose("block_two_endpoint", 1, "原式出现反例，改用分块双端点包络。")
        lower, upper = Fraction(bracket["lower"]), Fraction(bracket["upper"])
        if lower == upper:
            return {"action": "finish", "reason": f"该有限域上最小可行倍数是 {upper}。"
                    "完整枚举给出可行倍数，已记录的等号样本排除了所有更小倍数。"}
        trial = (lower + upper) / 2
        return propose(candidate, trial, f"已由见证得到下限 {lower}，由全域枚举得到可行上限 {upper}，检验中点。")

    return policy


default_policy = local_policy()


def run_agent(policy, check, *, goal, max_rounds=4):
    """Run an independent observe/decide/execute loop; return prior work even on failure."""
    from integration.residual_tool import completed_search
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("研究目标不能为空。")
    if isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or not 1 <= max_rounds <= 16:
        raise ValueError("研究轮数必须是 1 至 16 之间的整数。")
    history, decisions, seen = [], [], set()

    def end(status, reason):
        return {"goal": goal, "history": history, "status": status, "reason": reason, "decisions": decisions,
                "scale_bracket": scale_bracket(history)}

    while len(history) <= max_rounds:
        try:
            decision = policy(goal, history)
            if not isinstance(decision, dict) or decision.get("action") not in ("check", "finish"):
                raise ValueError("策略必须返回 check 或 finish。")
            reason = decision.get("reason", "")
            if not isinstance(reason, str):
                raise ValueError("决策说明必须是文本。")
            if decision["action"] == "finish":
                if not history or not reason.strip():
                    raise ValueError("结束研究前须有实际检查和结束说明。")
                decisions.append({"action": "finish", "reason": reason})
                completed = scale_bracket(history)["upper"] is not None
                return end("finite_search_completed" if completed else "counterexample_found", reason)
            if len(history) == max_rounds:
                return end("budget_exhausted", "已达到本次允许的工具调用轮数。")
            args = decision.get("arguments")
            if not isinstance(args, dict):
                raise ValueError("工具参数必须是对象。")
            identity = json.dumps(args, sort_keys=True, ensure_ascii=False, allow_nan=False)
            if identity in seen:
                return end("repeated_candidate", "策略重复提交同一候选和参数，已保留现有记录。")
            seen.add(identity)
            decisions.append({"action": "check", "arguments": dict(args), "reason": reason})
            result = check(args)
            if not completed_search(result):
                raise ValueError("候选或工具回执不合法，请核对工具参数。")
            history.append({"round": len(history) + 1, "arguments": dict(args), "result": result, "reason": reason})
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            return end("error", str(exc))
