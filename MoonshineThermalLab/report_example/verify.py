"""Check the published run receipt and reproduce the four-cell result offline."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

HERE = Path(__file__).resolve().parent
FILES = {
    "report_input.json", "load_skill_definition.json", "report.tex", "report.pdf", "source_skill.md", "installed_skill.md",
    "receipt.json", "stdout.json", "mode_results.json", "mode_proof.md", "mode_check.py", "problem.md", "input.txt",
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))

def fingerprint(name):
    return sha256((HERE / name).read_bytes()).hexdigest()

def check_hashes(run, report):
    hashes = run["public_files_sha256"]
    require(set(hashes) == FILES, "The public manifest does not contain the expected research artifacts.")
    for name, checksum in hashes.items():
        require(fingerprint(name) == checksum, f"Public artifact differs from the captured file: {name}")
    for name in ("report_input.json", "load_skill_definition.json", "report.tex", "report.pdf"):
        require(report["outputs"][name] == hashes[name], f"Report output hash mismatch: {name}")
    for name, checksum in run["source_files_sha256"].items():
        require(report["inputs"][name] == checksum, f"Archived research source hash mismatch: {name}")
    require(report["inputs"]["input.txt"] == fingerprint("input.txt"), "The preserved prompt differs.")
    require((HERE / "report.pdf").read_bytes().startswith(b"%PDF-"), "The reported PDF is unreadable.")

def check_flow(run, receipt, loaded, data):
    require(receipt["invocation"] == "automatic_after_research" and receipt["status"] == "compiled", "Missing automatic compiled report receipt.")
    require(run["outcome"]["accepted_local_research_step"] and not run["outcome"]["runtime_failure"], "Research failed or did not reach acceptance.")
    require(run["upstream"]["verified_unchanged_after_run"], "Pinned upstream source check failed.")
    for key, expected in (("session_id", run["session"]), ("turn_id", run["turn"]), ("project", run["project"])):
        require(data[key] == expected and receipt[key] == expected, f"Mismatched {key}")
    audit = loaded["native_skill_audit"]
    require(loaded["tool"] == "load_skill_definition" and audit["event"] == "skill_load", "No native skill-load receipt.")
    require(loaded["arguments"]["slug"] == audit["slug"] == receipt["skill"] == "latex-research-report", "Wrong skill.")
    require(loaded["registry"] == "installed" and audit["session_id"] == run["session"] and audit["project_slug"] == run["project"], "Registry receipt is not from this study.")
    require(loaded["skill_source_sha256"] == receipt["inputs"]["project_skill"] == fingerprint("source_skill.md"), "Project definition hash differs.")
    require(loaded["installed_file_sha256"] == fingerprint("installed_skill.md"), "Native installed file hash differs.")
    installed = (HERE / "installed_skill.md").read_text(encoding="utf-8")
    source = (HERE / "source_skill.md").read_text(encoding="utf-8")
    require(source.split("---", 2)[2].strip() == installed.split("---", 2)[2].strip() == loaded["output"]["body"].strip(),
            "Loaded skill body differs from the archived, installed definition.")
    rows = run["events_extracted_in_order"]
    valid_exec = [row for row in rows if row.get("stdout_sha256") == fingerprint("stdout.json") and row.get("returncode") == 0]
    accepted = [row for row in rows if row.get("tool") == "verify_overall" and row.get("passed") is True]
    archives = [row for row in rows if row.get("event") == "final" and row.get("archived_records", 0) > 0]
    require(valid_exec and accepted and archives and valid_exec[-1]["line"] < accepted[-1]["line"] < archives[-1]["line"], "Expected execution, review and archive in this order.")
    ref = "moonshine_events.jsonl#L" + str(valid_exec[-1]["line"])
    cited = [exp for exp in data["experiments"] if exp["source"] == ref and exp["status"] == "成功"]
    require(len(cited) == 1, "The report input lacks the original successful experiment.")
    expected_stdout = (HERE / "stdout.json").read_text(encoding="utf-8").strip()
    require(expected_stdout in cited[0]["summary"], "The original stdout is absent from the report input.")

def reproduce():
    # The model's script expects a workspace sibling for its proof and writes a JSON archive.
    # Recreate that layout outside the checkout, preserving every captured input byte.
    with tempfile.TemporaryDirectory() as folder:
        workspace = Path(folder) / "workspace"
        scripts = workspace / "experiments"
        scripts.mkdir(parents=True)
        shutil.copyfile(HERE / "mode_check.py", scripts / "mode_check.py")
        shutil.copyfile(HERE / "mode_proof.md", workspace / "mode_proof.md")
        output = subprocess.check_output(
            [sys.executable, "-B", str(scripts / "mode_check.py")],
            cwd=workspace, encoding="utf-8", timeout=20,
        )
        archived = json.loads((workspace / "mode_results.json").read_text("utf-8"))
    actual = json.loads(output)
    require(actual == read("stdout.json"), "The new output differs from the captured native execution.")
    require(archived == read("mode_results.json"), "The reproduced scientific archive differs.")
    require(archived["script_sha256"] == fingerprint("mode_check.py") and
            archived["proof_sha256"] == fingerprint("mode_proof.md"), "Wrong experimental inputs.")
    # The square graph has eigenvalues 0, 2, 4 on the three specified signed patterns.
    # Adding the Robin shift gives the reciprocal gains below independently of the run.
    baseline = Fraction(21, 4)
    eigenvalues = {"constant": 0, "stripes": 2, "checkerboard": 4}
    require(len(actual["modes"]) == len(eigenvalues) and actual["all_checks_passed"], "Missing modes.")
    observed = {row["name"]: row for row in actual["modes"]}
    require(set(observed) == set(eigenvalues), "Unexpected modes.")
    for name, laplacian_value in eigenvalues.items():
        expected = 1 / (Fraction(4, 21) + laplacian_value)
        row = observed[name]
        require(Fraction(row["error_inf"]) == expected == Fraction(row["modal_bound"]),
                f"Incorrect error or modal certificate for {name}.")
        require(row["verified"] and Fraction(row["baseline"]) == baseline, f"Baseline mismatch for {name}.")
    return actual

if __name__ == "__main__":
    run, receipt = read("run_evidence.json"), read("receipt.json")
    check_hashes(run, receipt)
    check_flow(run, receipt, read("load_skill_definition.json"), read("report_input.json"))
    result = reproduce()
    print("OK: native skill load, automatic export, artifact hashes and reproduced experiment.")
