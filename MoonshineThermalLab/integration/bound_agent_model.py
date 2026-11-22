"""OpenAI-compatible chat policy for the project-owned residual research controller."""
from dataclasses import dataclass, field
import ipaddress
import json
from pathlib import Path
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from integration.residual_tool import GUIDE, SCHEMA, TOOL_NAME

DEFAULT_ENV = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_GOAL = (
    "先检查弱散热端点逆矩阵直接乘带符号残差的无穷范数能否给出误差上界。使用默认有限域、"
    "单格分块和原始倍数 1。如果找到反例，请选择同时保留正负及两个端点信息的替代式，"
    "在同一域上检验，并说明有限枚举能支持的范围。"
)
SYSTEM = (
    "你为数学研究智能体选择下一步。根据研究目标、工具说明和真实观测，只选择一次精确检验，"
    "或在目标已达到时停止并解释。申请检验时写一句理由并调用工具。停止时只写结论。"
    "不得虚构输出，不得把有限枚举当成连续参数上的证明。\n\n" + GUIDE
)


@dataclass(frozen=True)
class Settings:
    endpoint: str
    api_key: str = field(repr=False)
    model: str


def load_settings(envfile=None):
    """Read only the named project file. Never log or substitute any key value."""
    path = Path(envfile) if envfile is not None else DEFAULT_ENV
    if not path.is_file():
        raise ValueError("找不到项目 .env，请复制 .env.example 为 .env 并填写模型配置。")
    required = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    values = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f".env 第 {number} 行格式有误。")
        if name not in required:
            continue
        if name in values:
            raise ValueError(".env 变量重复：" + name)
        value = value.strip()
        if value[:1] in ('"', "'"):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].lstrip().startswith("#")):
                raise ValueError(f".env 第 {number} 行的引号格式有误。")
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[name] = value
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ValueError("请在项目 .env 填写 " + "、".join(missing) + " 后再运行在线模式。")
    base = values["LLM_BASE_URL"]
    try:
        url = urllib.parse.urlsplit(base)
        host = url.hostname or ""
        url.port
    except ValueError:
        raise ValueError(".env 中 LLM_BASE_URL 格式有误。") from None
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if (not host or url.username is not None or url.password is not None or url.query or url.fragment
            or re.search(r"[\s\\]", base)
            or (url.scheme != "https" and not (url.scheme == "http" and loopback))):
        raise ValueError("LLM_BASE_URL 应为 HTTPS 服务地址，本机回环测试也可用 HTTP。")
    if not values["LLM_API_KEY"].isascii() or re.search(r"[\s\x00-\x1f\x7f]", values["LLM_API_KEY"]):
        raise ValueError("LLM_API_KEY 包含无效字符。")
    endpoint = base.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    return Settings(endpoint, values["LLM_API_KEY"], values["LLM_MODEL"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def json_object(text):
    def unique(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("模型返回的 JSON 有重复字段。")
            obj[key] = value
        return obj

    def disallow(value):
        raise ValueError("模型返回了非有限数值。")

    try:
        obj = json.loads(text, object_pairs_hook=unique, parse_constant=disallow)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("模型响应不是有效的 JSON。") from None
    if not isinstance(obj, dict):
        raise ValueError("模型响应必须是 JSON 对象。")
    return obj


class ModelPolicy:
    def __init__(self, settings):
        self.settings = settings
        self.turns = []
        self.opener = urllib.request.build_opener(NoRedirect())

    def __call__(self, goal, history):
        if len(history) != len(self.turns):
            raise ValueError("模型会话与控制器的观测历史不一致。")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": goal}]
        for step, turn in zip(history, self.turns):
            if step["arguments"] != turn["arguments"]:
                raise ValueError("控制器历史与已选工具参数不一致。")
            messages.append({"role": "assistant", "content": turn["content"],
                             "tool_calls": [turn["tool_call"]]})
            messages.append({"role": "tool", "tool_call_id": turn["tool_call"]["id"],
                             "content": json.dumps(step["result"], ensure_ascii=False)})
        payload = {"model": self.settings.model, "messages": messages, "tools": [{"type": "function",
                   "function": {"name": TOOL_NAME, "description": "Exact four-cell residual counterexample search",
                                "parameters": SCHEMA}}], "tool_choice": "auto"}
        req = urllib.request.Request(self.settings.endpoint, method="POST",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": "Bearer " + self.settings.api_key})
        try:
            with self.opener.open(req, timeout=60) as response:
                body = response.read(1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"模型服务返回 HTTP {exc.code}。请检查 .env 配置和服务状态。") from None
        except (urllib.error.URLError, socket.timeout, OSError):
            raise RuntimeError("无法连接模型服务，请检查 .env 中的地址、网络和服务状态。") from None
        if len(body) > 1024 * 1024:
            raise ValueError("模型响应超过 1 MiB。")
        data = json_object(body)
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("模型服务必须返回一条决策。")
        choice = choices[0]
        msg = choice.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            raise ValueError("模型决策缺少 assistant 消息。")
        reason = msg.get("content")
        if reason is None:
            reason = ""
        if not isinstance(reason, str):
            raise ValueError("模型决策的文字说明格式有误。")
        calls = msg.get("tool_calls", [])
        if not isinstance(calls, list):
            raise ValueError("tool_calls 必须是数组。")
        # Only persist the model's decision fields; credentials and raw server responses are never archived.
        public = json.dumps([reason, calls], ensure_ascii=False)
        if len(self.settings.api_key) >= 6 and self.settings.api_key in public:
            raise ValueError("服务响应包含敏感配置，已停止。")
        finish = choice.get("finish_reason")
        if finish == "stop" and not calls and reason.strip():
            self.turns.append({"action": "finish", "content": reason})
            return {"action": "finish", "reason": reason}
        if finish != "tool_calls" or len(calls) != 1 or not isinstance(calls[0], dict):
            raise ValueError("模型应一次申请一个工具，或明确结束。")
        call = calls[0]
        fn = call.get("function")
        if (not isinstance(fn, dict) or call.get("type") != "function" or fn.get("name") != TOOL_NAME
                or not isinstance(call.get("id"), str) or not call["id"].strip()
                or not isinstance(fn.get("arguments"), str)):
            raise ValueError("模型请求了未知工具，或工具调用格式有误。")
        if any(t.get("tool_call", {}).get("id") == call["id"] for t in self.turns):
            raise ValueError("模型复用了已有的工具调用标识。")
        args = json_object(fn["arguments"])
        wire = {"id": call["id"], "type": "function", "function": {"name": TOOL_NAME, "arguments": fn["arguments"]}}
        self.turns.append({"action": "check", "content": reason, "tool_call": wire, "arguments": args})
        return {"action": "check", "arguments": args, "reason": reason}


def make_model_policy(settings):
    return ModelPolicy(settings)
