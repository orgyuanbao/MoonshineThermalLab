"""Replay the archived small-grid checks using only the Python standard library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main() -> None:
    record = json.loads((HERE / "run_receipts.json").read_text(encoding="utf-8"))
    for relative, expected_hash in record["public_artifacts_sha256"].items():
        actual_hash = hashlib.sha256((HERE / relative).read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            raise ValueError(f"Archived file has changed: {relative}")

    receipts = record["published_stdout"]
    if not receipts:
        raise ValueError("No successful native Python output was recorded.")
    for receipt in receipts:
        name = receipt["script"]
        script = HERE / "workspace" / "experiments" / name
        archived = json.loads((HERE / receipt["stdout_file"]).read_text(encoding="utf-8"))
        # The native interval checker writes JSON next to its own script.
        with tempfile.TemporaryDirectory(prefix="moonshine-residual-") as tmp:
            temporary_script = Path(tmp) / script.name
            temporary_script.write_bytes(script.read_bytes())
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", str(temporary_script)],
                cwd=tmp, text=True, encoding="utf-8", capture_output=True,
                check=True, timeout=180,
            )
        if json.loads(result.stdout) != archived:
            raise ValueError(f"Recomputed data differ from {receipt['stdout_file']}.")
        print(f"{name}: archived JSON output reproduced")


if __name__ == "__main__":
    main()
