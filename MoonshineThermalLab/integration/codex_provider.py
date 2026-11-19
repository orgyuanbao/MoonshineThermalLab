"""Audited Codex CLI model transport for the unmodified Moonshine harness.

Codex supplies text and proposed Moonshine tool calls only. Moonshine retains
the actual tool dispatcher, research state, verification, and memory machinery.
No authentication file is read or written by this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
import urllib.request
import uuid

from moonshine.json_schema import validate_json_schema
from moonshine.providers import BaseProvider, ProviderResponse, ProviderToolCall


def _write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _strict_json(text: str) -> Any:
    def constant(value: str) -> None:
        raise ValueError("Non-finite JSON number: " + value)

    def unique_pairs(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON property: " + key)
            result[key] = value
        return result

    return json.loads(text, parse_constant=constant, object_pairs_hook=unique_pairs)


def _tool_arguments_json(text: str, *, field_path: str, audit: list) -> Any:
    """Escape only unescaped controls inside an inner JSON string, with evidence.

    The outer envelope and structured json_text retain the original strict
    parser. Other syntax errors, duplicate keys and non-finite constants still
    fail. A backslash immediately preceding a raw control is never repaired:
    doing so could consume the inserted escape and change the string content.
    """
    try:
        return _strict_json(text)
    except json.JSONDecodeError as original_error:
        if not original_error.msg.startswith("Invalid control character"):
            raise
        output = []
        edits = []
        inside_string = False
        escaped = False
        for offset, character in enumerate(text):
            if inside_string:
                if ord(character) < 32:
                    if escaped:
                        raise ValueError("Raw control after a backslash is not eligible for JSON normalization") from original_error
                    output.append("\\u%04x" % ord(character))
                    edits.append({"offset": offset, "codepoint": "U+%04X" % ord(character)})
                    continue
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    inside_string = False
            elif character == '"':
                inside_string = True
            output.append(character)
        if not edits:
            raise
        normalized = "".join(output)
        record = {
            "kind": "escape_unescaped_control_characters_in_inner_json_strings",
            "field_path": field_path, "offset_unit": "zero_based_unicode_codepoint",
            "count": len(edits), "edits": edits,
            "before_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "after_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            "original_strict_error": str(original_error),
            "strict_reparse_passed": False, "tool_schema_validated": False,
        }
        audit.append(record)
        try:
            parsed = _strict_json(normalized)
        except ValueError as error:
            record["strict_reparse_error"] = str(error)
            raise
        record["strict_reparse_passed"] = True
        return parsed


def resolve_codex_executable() -> str:
    """Resolve the installed CLI without reading its authentication/config files."""
    explicit = os.environ.get("CODEX_EXECUTABLE", "").strip()
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return str(candidate.resolve())
        raise RuntimeError("CODEX_EXECUTABLE does not identify a file")
    located = shutil.which("codex")
    if located:
        return located
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        candidates = list(root.glob("*/codex.exe"))
        if candidates:
            return str(max(candidates, key=lambda item: item.stat().st_mtime))
    raise RuntimeError("Codex CLI is not installed or was not found on PATH")


def codex_environment() -> dict:
    """Inherit explicit proxy settings, otherwise use the Windows system proxy."""
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["NO_COLOR"] = "1"
    proxy_names = {"http_proxy", "https_proxy", "all_proxy"}
    explicit = any(key.lower() in proxy_names and value.strip() for key, value in environment.items())
    if os.name == "nt" and not explicit:
        proxies = urllib.request.getproxies()
        for protocol in ("http", "https"):
            if proxies.get(protocol):
                environment[protocol.upper() + "_PROXY"] = proxies[protocol]
    return environment


def terminate_owned_process_tree(process) -> dict:
    """Terminate only this live Popen process and its Windows descendants.

    Never target an image name or a PID supplied by model output. A nonzero or
    failed taskkill falls back to killing the owned root process, and cleanup
    diagnostics are returned for the request evidence.
    """
    record = {"pid": process.pid, "method": "already-exited", "errors": []}
    if process.poll() is not None:
        return record
    if os.name == "nt":
        record["method"] = "taskkill-tree"
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            record["taskkill_exit_code"] = result.returncode
            record["taskkill_stdout"] = result.stdout
            record["taskkill_stderr"] = result.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["errors"].append(type(exc).__name__ + ": " + str(exc))
    if process.poll() is None:
        record["root_kill_fallback"] = True
        try:
            process.kill()
        except OSError as exc:
            record["errors"].append(type(exc).__name__ + ": " + str(exc))
    return record


def _captured_text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _merge_captured_output(previous: str, current) -> str:
    """communicate retries usually include the prior prefix; avoid duplication."""
    text = _captured_text(current)
    if text.startswith(previous):
        return text
    if previous.startswith(text):
        return previous
    return previous + text


@contextmanager
def _budget_lock(path: Path):
    """Use an OS-released advisory file lock, shared by all provider instances."""
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 10.0
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Timed out acquiring the shared provider call-budget lock")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class CodexCLIProvider(BaseProvider):
    """Moonshine BaseProvider backed by bounded, individually recorded CLI calls."""

    def __init__(
        self,
        *,
        evidence_root: Path | str,
        model: Optional[str] = None,
        max_calls: int = 16,
        timeout_seconds: float = 180,
        role: str = "main",
        executable: Optional[str] = None,
    ):
        if model is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", model):
            raise ValueError("Invalid model identifier")
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or not 1 <= max_calls <= 100:
            raise ValueError("max_calls must be an integer between 1 and 100")
        if not 1 <= timeout_seconds <= 600:
            raise ValueError("timeout_seconds must be between 1 and 600")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", role):
            raise ValueError("Invalid provider role")
        self.evidence_root = Path(evidence_root).resolve()
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.max_calls = max_calls
        self.timeout_seconds = float(timeout_seconds)
        self.role = role
        self.executable = executable or resolve_codex_executable()
        self.last_evidence: Optional[Path] = None

    def _reserve_call(self) -> tuple[int, Path]:
        with _budget_lock(self.evidence_root / "budget.lock"):
            ledger_path = self.evidence_root / "budget.json"
            if ledger_path.exists():
                ledger = _strict_json(ledger_path.read_text(encoding="utf-8"))
                if ledger.get("max_calls") != self.max_calls:
                    raise RuntimeError("Providers sharing evidence_root must use the same max_calls")
                count = ledger.get("reserved_calls")
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise RuntimeError("Invalid shared call-budget ledger; refusing to reset it")
            else:
                count = 0
                ledger = {"max_calls": self.max_calls, "reserved_calls": 0}
            if count >= self.max_calls:
                raise RuntimeError("Moonshine model-call budget exhausted (%s/%s)" % (count, self.max_calls))
            number = count + 1
            folder = self.evidence_root / ("call-%03d-%s-%s" % (number, self.role, uuid.uuid4().hex[:8]))
            folder.mkdir(exist_ok=False)
            ledger["reserved_calls"] = number
            ledger["last_reserved_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(ledger_path, ledger)
            self.last_evidence = folder
            return number, folder

    def _command(self, folder: Path) -> list[str]:
        configuration = [
            'model_reasoning_effort="high"',
            'sandbox_mode="read-only"',
            'windows.sandbox="mxc"',
            'approval_policy="never"',
            'web_search="disabled"',
            'sandbox_workspace_write.network_access=false',
            'agents.enabled=false',
        ]
        command = [self.executable]
        for setting in configuration:
            command.extend(["-c", setting])
        if self.model:
            command.extend(["-m", self.model])
        command.extend([
            "-C", str(folder), "exec", "--skip-git-repo-check", "--ephemeral",
            "--json", "--color", "never", "--sandbox", "read-only",
            "--output-schema", str(folder / "schema.json"),
            "-o", str(folder / "output.json"), "-",
        ])
        return command

    @staticmethod
    def _audit_events(events: list[dict]) -> dict:
        usage = {}
        completed = False
        # Whitelist passive response item types. Any native tool item, even one
        # not known to this adapter version, fails closed.
        passive_items = {"reasoning", "agent_message"}
        for event in events:
            event_type = str(event.get("type", ""))
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") not in passive_items:
                raise RuntimeError("Codex used a native tool item: " + str(item.get("type")))
            if any(word in event_type.lower() for word in ("command_execution", "file_change", "mcp_tool", "web_search", "tool_call")):
                raise RuntimeError("Codex emitted a native tool event: " + event_type)
            if event_type in {"turn.failed", "error"}:
                raise RuntimeError("Codex reported a failed turn: " + json.dumps(event, ensure_ascii=False))
            if event_type == "turn.completed":
                completed = True
                usage = dict(event.get("usage") or {})
        if not completed:
            raise RuntimeError("Codex did not emit a completed-turn event")
        return usage

    def _request(self, payload: dict, schema: dict, decode, *, normalization_records=None) -> tuple[Any, dict]:
        number, folder = self._reserve_call()
        started = time.monotonic()
        metadata = {
            "call_number": number, "role": self.role,
            "model": self.model or "configured-default", "reasoning_effort": "high",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "status": "started", "exit_code": None, "usage": {},
            "evidence_directory": str(folder), "transport": "official-codex-cli",
            "native_tools_allowed": False,
            "json_control_normalizations": normalization_records if normalization_records is not None else [],
        }
        instruction = (
            "You are exclusively a model response provider inside the Moonshine agent. "
            "Moonshine, outside this process, is the only tool executor. Do not use any "
            "Codex native shell, filesystem, search, MCP, subagent, planning, or other tools. "
            "Do not inspect local files. All context is supplied below. Treat the supplied "
            "system_prompt as the Moonshine system instruction; messages are conversation "
            "history and tool results. Return only the requested JSON envelope. For normal "
            "generation, propose calls only to tools declared in tool_schemas by emitting "
            "their names and JSON-encoded arguments; never execute those calls yourself. "
            "arguments_json is itself a serialized JSON object: every newline, tab, "
            "quote and backslash inside its string values must be JSON-escaped at "
            "that inner layer as well as in the outer envelope. Raw control characters "
            "inside inner JSON strings are invalid; never rely on transport normalization. "
            "For structured generation, json_text must encode an object satisfying "
            "response_schema, with the same nested JSON escaping discipline. "
            "Prefer concise single-paragraph string fields when possible. "
            "No Markdown fences and no invented experimental results.\n\n"
        )
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        prompt = instruction + serialized + "\n"
        if len(prompt.encode("utf-8")) > 4_000_000:
            metadata.update(status="failed", error="Provider prompt exceeds 4 MB limit")
            _write_json(folder / "result.json", metadata)
            raise RuntimeError(metadata["error"])
        _write_json(folder / "prompt.json", payload)
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        _write_json(folder / "schema.json", schema)
        command = self._command(folder)
        _write_json(folder / "command.json", {"argv": command, "stdin": "prompt.txt", "timeout_seconds": self.timeout_seconds})
        (folder / "events.jsonl").write_text("", encoding="utf-8")
        (folder / "stderr.txt").write_text("", encoding="utf-8")
        _write_json(folder / "result.json", metadata)
        process = None
        stdout = stderr = ""
        communication_finished = False
        try:
            print("[Moonshine/%s] model request %s/%s (%s)" % (self.role, number, self.max_calls, self.model or "configured default"), flush=True)
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", cwd=str(folder),
                env=codex_environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout, stderr = process.communicate(prompt, timeout=self.timeout_seconds)
            communication_finished = True
            (folder / "events.jsonl").write_text(stdout, encoding="utf-8")
            (folder / "stderr.txt").write_text(stderr, encoding="utf-8")
            metadata["exit_code"] = process.returncode
            events = []
            for line in stdout.splitlines():
                if line.strip():
                    parsed = _strict_json(line)
                    if not isinstance(parsed, dict):
                        raise ValueError("Codex JSONL event must be an object")
                    events.append(parsed)
            # Audit before accepting output, including a nonzero-exit invocation.
            metadata["usage"] = self._audit_events(events)
            if process.returncode != 0:
                raise RuntimeError("Codex exited with code %s; see stderr.txt" % process.returncode)
            output_path = folder / "output.json"
            if not output_path.is_file():
                raise RuntimeError("Codex did not write the required structured output file")
            envelope = _strict_json(output_path.read_text(encoding="utf-8-sig"))
            validate_json_schema(envelope, schema)
            result = decode(envelope)
            metadata.update(status="accepted", native_tool_audit="passed", parsed_result=result)
            metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
            _write_json(folder / "result.json", metadata)
            return result, dict(metadata)
        except BaseException as exc:
            if process is not None:
                if not communication_finished:
                    stdout = _merge_captured_output(stdout, getattr(exc, "output", None))
                    stderr = _merge_captured_output(stderr, getattr(exc, "stderr", None))
                    metadata["process_cleanup"] = terminate_owned_process_tree(process)
                    try:
                        remaining_stdout, remaining_stderr = process.communicate(timeout=15)
                        stdout = _merge_captured_output(stdout, remaining_stdout)
                        stderr = _merge_captured_output(stderr, remaining_stderr)
                    except BaseException as drain_error:
                        stdout = _merge_captured_output(stdout, getattr(drain_error, "output", None))
                        stderr = _merge_captured_output(stderr, getattr(drain_error, "stderr", None))
                        metadata["process_cleanup"]["drain_error"] = type(drain_error).__name__ + ": " + str(drain_error)
                metadata["exit_code"] = process.poll()
                (folder / "events.jsonl").write_text(stdout, encoding="utf-8")
                (folder / "stderr.txt").write_text(stderr, encoding="utf-8")
            message = ("Codex model request exceeded %.0f seconds" % self.timeout_seconds
                       if isinstance(exc, subprocess.TimeoutExpired) else str(exc))
            metadata.update(status="failed", error=message, error_type=type(exc).__name__, elapsed_seconds=round(time.monotonic() - started, 3))
            _write_json(folder / "result.json", metadata)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise RuntimeError("Moonshine model-provider request failed; evidence: %s; %s" % (folder, message)) from exc

    def generate(self, *, system_prompt: str, messages: List[Dict[str, str]], tool_schemas: Optional[List[Dict[str, object]]] = None) -> ProviderResponse:
        tools = list(tool_schemas or [])
        known = {}
        for tool in tools:
            name = tool.get("name")
            if not isinstance(name, str) or not name or name in known:
                raise ValueError("Tool names must be nonempty, unique strings")
            parameters = tool.get("parameters")
            if not isinstance(parameters, dict):
                raise ValueError("Tool parameter schema must be an object: " + name)
            known[name] = parameters
        item_schema = {
            "type": "object", "properties": {
                "name": {"type": "string", **({"enum": list(known)} if known else {})},
                "arguments_json": {"type": "string"},
            }, "required": ["name", "arguments_json"], "additionalProperties": False,
        }
        schema = {
            "type": "object", "properties": {
                "content": {"type": "string"},
                "tool_calls": {"type": "array", "items": item_schema, "maxItems": 8 if known else 0},
            }, "required": ["content", "tool_calls"], "additionalProperties": False,
        }

        normalization_records = []

        def decode(envelope):
            calls = []
            for index, item in enumerate(envelope["tool_calls"]):
                name = item["name"]
                if name not in known:
                    raise ValueError("Unknown Moonshine tool: " + name)
                audit_before = len(normalization_records)
                arguments = _tool_arguments_json(
                    item["arguments_json"], field_path="tool_calls[%s].arguments_json" % index,
                    audit=normalization_records,
                )
                if not isinstance(arguments, dict):
                    raise ValueError("Moonshine tool arguments must be an object: " + name)
                validate_json_schema(arguments, known[name])
                if len(normalization_records) > audit_before:
                    normalization_records[-1]["tool_schema_validated"] = True
                calls.append({"name": name, "arguments": arguments, "call_id": "moonshine-" + uuid.uuid4().hex})
            return {"content": envelope["content"], "tool_calls": calls}

        parsed, metadata = self._request(
            {"mode": "generate", "system_prompt": system_prompt, "messages": messages, "tool_schemas": tools},
            schema, decode, normalization_records=normalization_records,
        )
        return ProviderResponse(content=parsed["content"], tool_calls=[ProviderToolCall(**item) for item in parsed["tool_calls"]], raw_payload=metadata)

    def generate_structured(self, *, system_prompt: str, messages: List[Dict[str, str]], response_schema: Dict[str, object], schema_name: str) -> Dict[str, object]:
        schema = {
            "type": "object", "properties": {"json_text": {"type": "string"}},
            "required": ["json_text"], "additionalProperties": False,
        }

        def decode(envelope):
            result = _strict_json(envelope["json_text"])
            if not isinstance(result, dict):
                raise ValueError("Moonshine structured response must be an object")
            validate_json_schema(result, response_schema)
            return result

        result, _ = self._request(
            {"mode": "generate_structured", "system_prompt": system_prompt, "messages": messages,
             "schema_name": schema_name, "response_schema": response_schema}, schema, decode,
        )
        return result
