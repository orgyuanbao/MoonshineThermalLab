"""Create a local isolated Python 3.12 environment; never installs Moonshine."""
from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import urllib.request
import venv

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        raise RuntimeError("请使用 Python 3.12 的 64 位版本运行此安装脚本。")
    from integration.source_integrity import source_identity
    source_identity(ROOT / "source", ROOT / "source_manifest.json")
    target = ROOT / ".venv"
    if target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
        raise RuntimeError("本项目 .venv 不能是链接或目录联接。")
    if target.resolve().parent != ROOT:
        raise RuntimeError("虚拟环境位置超出本项目。")
    executable = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if target.exists():
        config = target / "pyvenv.cfg"
        if not config.is_file() or not executable.is_file():
            raise RuntimeError("已有 .venv 不是完整虚拟环境；未删除或覆盖，请在新的交付副本中安装。")
        settings = dict(line.split("=", 1) for line in config.read_text(encoding="utf-8").splitlines() if "=" in line)
        settings = {key.strip(): value.strip() for key, value in settings.items()}
        if settings.get("include-system-site-packages", "").lower() != "false":
            raise RuntimeError("已有 .venv 继承全局包，无法作为独立复现环境；未修改，请在新目录安装。")
    else:
        print("正在创建独立虚拟环境……", flush=True)
        venv.EnvBuilder(with_pip=True, system_site_packages=False, clear=False).create(target)
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                       PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    if not any(key.lower() in {"http_proxy", "https_proxy", "all_proxy"} and value.strip()
               for key, value in environment.items()):
        proxies = urllib.request.getproxies()
        for protocol in ("http", "https"):
            if proxies.get(protocol):
                environment[protocol.upper() + "_PROXY"] = proxies[protocol]
    probe = subprocess.run([str(executable), "-I", "-c",
                            "import sys,struct,json;print(json.dumps([list(sys.version_info[:2]),struct.calcsize('P')*8]))"],
                           check=True, capture_output=True, text=True, encoding="utf-8", env=environment, timeout=30)
    if json.loads(probe.stdout) != [[3, 12], 64]:
        raise RuntimeError("已有虚拟环境并非 Python 3.12 64 位，未进行依赖安装。")
    print("正在安装固定版本的科学计算依赖；Moonshine 原版直接从已核验源码加载。", flush=True)
    subprocess.run([str(executable), "-m", "pip", "install", "--disable-pip-version-check",
                    "--only-binary=:all:", "--timeout", "30", "--retries", "2",
                    "-r", str(ROOT / "requirements-science.txt")],
                   check=True, cwd=ROOT, env=environment, timeout=600)
    subprocess.run([str(executable), "-B", "-X", "utf8", str(ROOT / "verify_environment.py")],
                   check=True, cwd=ROOT, env=environment, timeout=120)
    print("安装与离线环境检查完成；没有发起模型研究。请运行“启动热仿真研究.cmd”。", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print("安装未完成：", exc, file=sys.stderr, flush=True)
        raise SystemExit(1)
