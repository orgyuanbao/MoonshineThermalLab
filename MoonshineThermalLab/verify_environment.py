"""Offline source, numeric and Moonshine-tool check; no model/login request."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def _verify():
    from integration.moonshine_bootstrap import bootstrap_moonshine
    bootstrap_moonshine(ROOT / "source", ROOT / "source_manifest.json")
    import numpy as np
    import scipy
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import spsolve
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    import moonshine
    from moonshine.app import MoonshineApp
    from moonshine.moonshine_cli.config import ensure_runtime_home
    from moonshine.moonshine_constants import MoonshinePaths
    from run_moonshine import TOOLS, project_tools
    from integration.residual_tool import TOOL_NAME, register_residual_tool
    matrix = csr_matrix([[2.0, -1.0], [-1.0, 2.0]])
    rhs = np.array([1.0, 0.0])
    solution = spsolve(matrix, rhs)
    if not np.allclose(solution, [2 / 3, 1 / 3], atol=1e-12, rtol=0):
        raise RuntimeError("科学计算最小校验失败。")
    with tempfile.TemporaryDirectory(prefix="moonshine-environment-check-") as directory:
        temporary = Path(directory)
        figure, axis = plt.subplots(figsize=(3, 2))
        axis.plot([0, 1], solution)
        figure.savefig(temporary / "plot.png")
        plt.close(figure)
        if (temporary / "plot.png").stat().st_size < 100:
            raise RuntimeError("绘图最小校验失败。")
        paths = MoonshinePaths(temporary / "home")
        ensure_runtime_home(paths)
        config_path = temporary / "home" / "config" / "settings.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for name in ("provider", "verification_provider", "archival_provider"):
            config[name]["type"] = "offline"
        config["memory"].update(auto_extract=False, knowledge_vector_enabled=False)
        exposure = {"tools_include": project_tools("thermal-rom")}
        config["exposure"].update(exposure)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        app = MoonshineApp(home=str(temporary / "home"))
        names = {item["name"] for item in app.tool_manager.schemas(mode="research", include=TOOLS)}
        if not set(TOOLS) <= names:
            raise RuntimeError("原版 Moonshine 工具缺失：" + repr(sorted(set(TOOLS) - names)))
        register_residual_tool(app.tool_manager)
        checked = app.tool_manager.dispatch(TOOL_NAME, {"candidate": "block_two_endpoint",
                                            "boundary_levels": ["1/5"], "residual_values": [1]},
                                            {"mode": "research", "exposure": exposure})
        if checked["status"] != "no_counterexample_in_domain" or checked["checked_cases"] != 1:
            raise RuntimeError("项目反例工具未完成已知的单项精确校验。")
        if (temporary / "home" / "config" / "credentials.json").exists():
            raise RuntimeError("离线检查不应生成凭据。")
    from integration.codex_provider import resolve_codex_executable
    try:
        cli = resolve_codex_executable()
    except RuntimeError:
        cli = None
    print(json.dumps({"status": "passed", "python": sys.version,
                      "numpy": np.__version__, "scipy": scipy.__version__, "matplotlib": matplotlib.__version__,
                      "moonshine_source": str(Path(moonshine.__file__).resolve()),
                      "tool_count": len(names), "project_tool_checked": TOOL_NAME,
                      "numeric_residual": float(np.max(np.abs(matrix @ solution - rhs))),
                      "codex_executable_found": bool(cli), "model_login_or_availability_tested": False,
                      "real_model_calls": 0}, ensure_ascii=False, indent=2))
    if not cli:
        print("科学计算和 Moonshine 核心已可用。启动新研究还需安装并登录用户自己的官方 Codex CLI。")
    return 0


def main():
    # Keep matplotlib's generated font cache out of the user's global profile.
    previous = os.environ.get("MPLCONFIGDIR")
    with tempfile.TemporaryDirectory(prefix="moonshine-matplotlib-config-") as directory:
        os.environ["MPLCONFIGDIR"] = directory
        try:
            return _verify()
        finally:
            if previous is None:
                os.environ.pop("MPLCONFIGDIR", None)
            else:
                os.environ["MPLCONFIGDIR"] = previous


if __name__ == "__main__":
    raise SystemExit(main())
