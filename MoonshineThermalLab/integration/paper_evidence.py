"""Build the course-paper input from the published research archive (no model calls)."""

from __future__ import annotations

import csv
from fractions import Fraction
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from statistics import median


METHODS = ("analytic", "sharp_scalar", "block_abs", "block_sign", "two_endpoint")
GRIDS = (24, 48, 96)
TRACKS = ("fixed8", "old_pre")
RESULTS = "residual_study/results/"
NATIVE = "residual_study/moonshine/"
FROZEN = "thermal/home/projects/thermal-rom/workspace/results/04_final_v1/"
EXTENSION = "residual_study/agent_extension/"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Archive:
    """Read the same bytes that are hashed and constrain references to the study."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.hashes = {}
        self.expected = {}
        index = self.root / "integration/paper_sources.sha256"
        for line in index.read_text(encoding="utf-8").splitlines():
            checksum, name = line.split("  ", 1)
            require(name not in self.expected and len(checksum) == 64, f"Invalid paper-source manifest: {name}")
            self.expected[name] = checksum

    def bytes(self, name, checksum=None):
        require(name in self.expected and PurePosixPath(name).as_posix() == name, f"Unlisted archive input: {name}")
        path = self.root / name
        require(path.resolve() == path and path.is_relative_to(self.root), f"Indirect archive path: {name}")
        data = path.read_bytes()
        actual = sha256(data).hexdigest()
        require(actual == self.expected[name] and (checksum is None or actual == checksum),
                f"Archive hash mismatch: {name}")
        self.hashes[name] = actual
        return data

    def text(self, name):
        return self.bytes(name).decode("utf-8-sig")

    def json(self, name):
        return json.loads(self.text(name))


def research_history(archive):
    turns = archive.json("evidence/iterations.json")["turns"]
    failures = archive.json("evidence/failed-calls.json")
    independent = archive.json("evidence/independent-checks.json")
    require(len(turns) == 7 and len({r["turn"] for r in turns}) == 7, "Historical round set is incomplete")
    for r in turns:
        successes = sum(call["returncode"] == 0 for call in r["python_tool_results"])
        require(successes == r["successful_python_executions"], f"Historical execution count: {r['turn']}")
        require(r["passed_verifications"] <= r["verification_attempt_count"], "Historical review count")
    totals = {
        "python_attempts": sum(len(r["python_tool_results"]) for r in turns),
        "python_successes": sum(r["successful_python_executions"] for r in turns),
        "review_attempts": sum(r["verification_attempt_count"] for r in turns),
        "passed_reviews": sum(r["passed_verifications"] for r in turns),
        "archived_records": sum(r["archived_records_reported"] for r in turns),
    }
    require(independent["passed"] and independent["real_model_calls"] == 0, "Independent audit is incomplete")
    require(all(check["passed"] for check in independent["checks"]), "Failed independent historical check")
    require(sum(r["provider_counts"].get("failed", 0) for r in turns) == len(failures),
            "Historical failure records do not match")
    oracle_path = "thermal/independent_review/theory_oracle.md"
    original_benchmark = archive.json(FROZEN + "summary.json")
    require(original_benchmark["status"] == "complete" and not original_benchmark["missing"] and not original_benchmark["invalid"],
            "Original thermal benchmark is incomplete")
    for name, fingerprint in original_benchmark["source_result_sha256"].items():
        archive.bytes(FROZEN + name, fingerprint)
    return {"turns": turns, "totals": totals, "failed_calls": failures, "independent": independent,
            "oracle_path": oracle_path, "oracle_text": archive.text(oracle_path), "baseline": original_benchmark,
            "source": "evidence/iterations.json"}


def signed_research(archive):
    receipt_path = NATIVE + "run_receipts.json"
    receipts = archive.json(receipt_path)
    for name, checksum in receipts["public_artifacts_sha256"].items():
        archive.bytes(NATIVE + name, checksum)
    turns = []
    proofs = ("workspace/residual_proof.md", "workspace/residual_interval_proof.md")
    require(len(receipts["turns"]) == len(receipts["published_stdout"]) == len(proofs), "Missing signed turns")
    for raw, recorded, proof in zip(receipts["turns"], receipts["published_stdout"], proofs):
        events = raw["native_tool_results"]
        executed = [r for r in events if r["tool"] == "run_python_script" and not r["tool_reported_error"]
                    and r["returncode"] == 0 and r["script"] == recorded["script"]]
        reviews = [r for r in events if r["tool"] == "verify_overall"]
        outcome = raw["outcome"]
        require(raw["source_preserved"] and outcome["accepted_local_research_step"]
                and not outcome["runtime_failure"] and outcome["archived_records"] > 0,
                f"Unaccepted signed turn: {raw['turn_id']}")
        require(len(executed) == outcome["successful_python_executions"] == 1
                and executed[0]["stdout_sha256"] == recorded["sha256"],
                "Signed research stdout does not match native execution")
        require(reviews and reviews[-1]["passed"] and not reviews[-1]["tool_reported_error"]
                and sum(row["passed"] for row in reviews) == outcome["passed_verifications"],
                "Signed research review does not match outcome")
        stdout_path = NATIVE + recorded["stdout_file"]
        stdout = json.loads(archive.bytes(stdout_path, recorded["sha256"]).decode("utf-8-sig"))
        require(all(value is True for value in stdout["checks"].values()), "Failed signed research check")
        turns.append({**raw, "proof_path": NATIVE + proof, "proof_text": archive.text(NATIVE + proof),
                      "stdout_path": stdout_path, "stdout": stdout, "reviews": reviews})
    require(turns[0]["session_id"] == turns[1]["session_id"], "Residual follow-up is in another session")
    return {"turns": turns, "source": receipt_path}, receipts


def four_cell_research(archive):
    prefix = "report_example/"
    run = archive.json(prefix + "run_evidence.json")
    for name, checksum in run["public_files_sha256"].items():
        archive.bytes(prefix + name, checksum)
    reported = archive.json(prefix + "receipt.json")
    loaded = archive.json(prefix + "load_skill_definition.json")
    data = archive.json(prefix + "mode_results.json")
    outcomes = run["outcome"]
    require(reported["status"] == "compiled" and reported["invocation"] == "automatic_after_research"
            and reported["session_id"] == run["session"] == loaded["native_skill_audit"]["session_id"]
            and reported["turn_id"] == run["turn"] and reported["project"] == run["project"]
            and loaded["arguments"]["slug"] == reported["skill"] == "latex-research-report",
            "The worked example has no matching automatic report receipt")
    for name, checksum in reported["outputs"].items():
        require(run["public_files_sha256"][name] == checksum, f"Four-cell output mismatch: {name}")
    require(data["proof_sha256"] == archive.hashes[prefix + "mode_proof.md"]
            and data["script_sha256"] == archive.hashes[prefix + "mode_check.py"], "Four-cell proof or script mismatch")
    require(outcomes["accepted_local_research_step"] and not outcomes["runtime_failure"]
            and run["upstream"]["verified_unchanged_after_run"] and data["all_checks_passed"], "Four-cell run failed")
    events = run["events_extracted_in_order"]
    exe = [r["line"] for r in events if r.get("tool") == "run_python_script" and r["returncode"] == 0
           and r["stdout_sha256"] == archive.hashes[prefix + "stdout.json"]]
    review = [r["line"] for r in events if r.get("tool") == "verify_overall" and r["passed"]]
    end = [r["line"] for r in events if r.get("event") == "final" and r["archived_records"] > 0]
    require(exe and review and end and exe[-1] < review[-1] < end[-1], "Four-cell execution/review chronology")
    modes = data["modes"]
    gain = {k: 1 / (Fraction(4, 21) + lam) for k, lam in (("constant", 0), ("stripes", 2), ("checkerboard", 4))}
    require(len(modes) == len(gain) and {r["name"] for r in modes} == set(gain), "Four-cell case set mismatch")
    for row in modes:
        require(row["verified"] and Fraction(row["error_inf"]) == gain[row["name"]] == Fraction(row["modal_bound"])
                and Fraction(row["baseline"]) == Fraction(21, 4), "Four-cell mode fails exact cross-check")
    proof_path = prefix + "mode_proof.md"
    return {"modes": modes, "proof_path": proof_path, "proof_text": archive.text(proof_path),
            "archive": data, "run": run, "outcome": outcomes, "receipt": reported,
            "source": prefix + "run_evidence.json"}


def read_groups(archive, name, group_field, group_names, indices, queries):
    grouped = {(n, key): {} for n in GRIDS for key in group_names}
    rows = csv.DictReader(io.StringIO(archive.text(RESULTS + name)))
    require(rows.fieldnames and len(rows.fieldnames) == len(set(rows.fieldnames)), "Duplicate CSV headers")
    for row in rows:
        group = row.pop(group_field)
        record = {k: int(v) if k in indices else float(v) for k, v in row.items()}
        record[group_field] = group
        require(all(math.isfinite(v) and v >= 0 for k, v in record.items() if k != group_field), "Invalid CSV value")
        key, index = (record["n"], group), record["index"]
        require(key in grouped and 0 <= index < queries and index not in grouped[key],
                f"Unexpected or duplicate row in {name}: {key}, {index}")
        grouped[key][index] = record
    require(all(len(rows) == queries for rows in grouped.values()), f"Incomplete {name}")
    return {key: [rows[i] for i in range(queries)] for key, rows in grouped.items()}


def checked_fields(calculated, recorded, label):
    for name, expected in calculated.items():
        actual = recorded[name]
        if isinstance(expected, float):
            equal = math.isclose(actual, expected, rel_tol=2e-12, abs_tol=2e-15)
        else:
            equal = actual == expected
        require(equal, f"CSV / summary mismatch: {label}, {name} ({expected}, {actual})")


def paired_metrics(rows, method, tolerance):
    bounds = [r[method] for r in rows]
    errors = [r["error_linf"] for r in rows]
    pairs = list(zip(bounds, errors))
    ratios = [b / e for b, e in pairs if e > 0]
    return {"alarms": sum(b > tolerance for b in bounds),
            "false_alarms": sum(e <= tolerance < b for b, e in pairs),
            "missed": sum(b <= tolerance < e for b, e in pairs),
            "true_exceedances": sum(e > tolerance for e in errors),
            "min_bound_minus_error": min(b-e for b, e in pairs),
            "median_effectivity": median(ratios) if ratios else None, "median_bound": median(bounds)}


def closed_metrics(rows, tolerance, slack):
    rank = 8
    for r in rows:
        bound, error, returned = r["bound"], r["pre_error_linf"], r["returned_error_linf"]
        require(r["fallback"] == int(bound > tolerance) and bound + slack * max(1, error) >= error,
                "Closed-loop decision disagrees with its certificate")
        require(r["rank_before"] == rank and rank <= r["rank_after"] <= rank + r["fallback"],
                "Closed-loop rank trajectory is inconsistent")
        require(r["fallback"] or returned == error, "Returned field differs from accepted prediction")
        rank = r["rank_after"]
    return {"fallbacks": sum(r["fallback"] for r in rows),
            "false_alarms": sum(r["fallback"] and r["pre_error_linf"] <= tolerance for r in rows),
            "missed": sum(not r["fallback"] and r["pre_error_linf"] > tolerance for r in rows),
            "pre_exceedances": sum(r["pre_error_linf"] > tolerance for r in rows),
            "returned_exceedances": sum(r["returned_error_linf"] > tolerance for r in rows),
            "max_pre_error": max(r["pre_error_linf"] for r in rows),
            "max_returned_error": max(r["returned_error_linf"] for r in rows), "final_rank": rank}


def numerical_evidence(archive):
    summary = archive.json(RESULTS + "summary.json")
    queries, repeats = summary["parameter_count"], summary["repeats"]
    tolerance, slack = summary["tolerance"], summary["floating_checks_slack"]
    require(summary["status"] == "passed" and summary["model_calls"] == 0 and summary["new_accuracy_parameters"] == 0
            and summary["fixed_partition"] == [4,4] and queries == 256 and repeats == 3
            and tolerance == 0.001 and 0 < slack <= 2e-10 and set(summary["grids"]) == set(map(str, GRIDS)),
            "Unexpected frozen benchmark protocol")
    for name, checksum in summary["input_file_sha256"].items():
        archive.bytes(name, checksum)
    frozen = archive.json(FROZEN + "test_parameters.json")["parameters"]
    require(len(frozen) == queries == len(set(map(tuple, frozen))), "Frozen stream is incomplete")
    pair_rows = read_groups(archive, "paired_cases.csv", "track", TRACKS, {"n","index"}, queries)
    closed_rows = read_groups(archive, "closed_loop_cases.csv", "method", METHODS,
                              {"n","index","fallback","rank_before","rank_after"}, queries)
    paired, closed, timings = {}, {}, {}
    for n in GRIDS:
        key = str(n)
        grid = summary["grids"][key]
        paired[key], closed[key], timings[key] = {}, {}, {}
        require(grid["queries"] == queries, f"Missing benchmark queries for n={n}")
        for track in TRACKS:
            rows = pair_rows[n, track]
            for i, r in enumerate(rows):
                require([r[x] for x in ("left","right","bottom","top")] == frozen[i],
                        "Frozen boundary parameters differ between tracks")
                ordered = [r[m] for m in METHODS] + [r["error_linf"]]
                require(all(a + slack*max(1.0,b) >= b for a,b in zip(ordered,ordered[1:])),
                        "Observed bounds violate expected ordering or coverage")
            metrics = {m: paired_metrics(rows,m,tolerance) for m in METHODS}
            for m in METHODS:
                checked_fields(metrics[m], grid["paired"][track][m], f"{n}/{track}/{m}")
            paired[key][track] = metrics
        for m in METHODS:
            recorded = grid["closed"][m]
            stats = closed_metrics(closed_rows[n,m], tolerance, slack)
            checked_fields(stats, recorded, f"{n}/closed/{m}")
            samples = recorded["timing_samples_s"]
            require(len(samples) == repeats and all(math.isfinite(v) and v >= 0 for s in samples for v in s.values()),
                    "Invalid timing repetition")
            timing = {k: median(s[k] for s in samples) for k in recorded["timing_median_s"]}
            checked_fields(timing, recorded["timing_median_s"], f"{n}/time/{m}")
            timings[key][m] = timing
            closed[key][m] = {**stats, "timing_median_s": timing}
        for pair, policy in zip(pair_rows[n,"old_pre"], closed_rows[n,"analytic"]):
            require(pair["error_linf"] == policy["pre_error_linf"] and pair["analytic"] == policy["bound"],
                    "Frozen original trajectory disagrees with the original policy")
    totals = {
        "old_pre_alarms": {m: sum(paired[str(n)]["old_pre"][m]["alarms"] for n in GRIDS) for m in METHODS},
        "fallbacks": {m: sum(closed[str(n)][m]["fallbacks"] for n in GRIDS) for m in METHODS},
        "returned_exceedances": {m: sum(closed[str(n)][m]["returned_exceedances"] for n in GRIDS) for m in METHODS},
    }
    endpoint_gap = max(abs(row["block_sign"] - row["two_endpoint"])
                       for segment in pair_rows.values() for row in segment)
    fixed8_endpoint_ratio = {
        str(n): median(row["two_endpoint"] / row["analytic"]
                       for row in pair_rows[n, "fixed8"] if row["analytic"] > 0)
        for n in GRIDS
    }
    return {"grids": list(GRIDS), "methods": list(METHODS), "paired": paired, "closed": closed,
            "sign_endpoint_max_abs_gap": endpoint_gap, "fixed8_median_endpoint_to_analytic": fixed8_endpoint_ratio,
            "totals": totals, "case": pair_rows[48,"old_pre"][10], "timing": timings,
            "counts": {"paired_rows": sum(map(len,pair_rows.values())),
                       "closed_rows": sum(map(len,closed_rows.values())), "queries_per_grid": queries},
            "tolerance": tolerance, "repeats": repeats, "scope": summary["origin"]}, summary, frozen


def extension_research(archive):
    """Check the exact search results reported by the new agent before quoting them."""
    from integration.residual_tool import TOOL_NAME, evaluate

    trace_path = EXTENSION + "trace.json"
    trace = archive.json(trace_path)
    tool_path = "integration/residual_tool.py"
    replay_path = EXTENSION + "replay.py"
    controller_path = "integration/bound_agent.py"
    paths = [trace_path, tool_path, replay_path, controller_path, "integration/bound_agent_model.py",
             "integration/test_bound_agent_http.py"]
    for name in paths[1:]:
        archive.bytes(name)
    require(trace["tool_name"] == TOOL_NAME and trace["mode"] == "deterministic_controller"
            and trace["model_calls"] == 0 and trace.get("model") is None
            and trace["pristine_registry_has_tool"] is False, "Unexpected agent or tool provenance")
    steps = trace["steps"]
    require(len(steps) >= 2 and steps[0]["arguments"]["candidate"] == "weak_signed"
            and steps[0]["result"]["status"] == "counterexample"
            and any(s["arguments"]["candidate"] == "block_two_endpoint"
                    and s["result"]["status"] == "no_counterexample_in_domain" for s in steps[1:]),
            "The agent's trace lacks the conjecture, its witness, or the subsequent check")
    for i, step in enumerate(steps, 1):
        require(step["round"] == i, "Missing or reordered agent step")
        result = evaluate(None, **step["arguments"])
        require(result == step["result"], f"Exact replay differs at agent step {i}")
        require(result["partition"] == "singletons" and result["boundary_levels"] == ["1/5", "5"]
                and result["residual_values"] == [-1, 0, 1], "Agent study domain changed between trials")
    require(trace["controller_status"] == "finite_search_completed"
            and trace["scale_bracket"] == {"lower": "1", "upper": "1", "no_finite_scale": False},
            "The stated scale does not match the controller's conclusion")
    last = steps[-1]["result"]
    witness = last["witness"]
    require(last["candidate"] == "block_two_endpoint" and last["partition"] == "singletons"
            and 0 < Fraction(last["scale"]) < 1 and last["status"] == "counterexample" and witness
            and list(map(Fraction, witness["boundaries"])) == [Fraction(1, 5)] * 4
            and Fraction(witness["candidate_bound"]) / Fraction(last["scale"]) == Fraction(witness["true_error_inf"]),
            "The final witness does not establish tightness under a uniform scaling")
    http_path = EXTENSION + "http_fixture.json"
    http = archive.json(http_path)
    require(http["external_model_calls"] == 0 and http["http_requests"]
            and http["controller_result"]["status"] == "finite_search_completed",
            "The model-adapter fixture must identify a completed local protocol test")
    return {**trace, "trace_path": trace_path, "tool_path": tool_path, "controller_path": controller_path,
            "replay_path": replay_path, "http_path": http_path, "http_requests": len(http["http_requests"]),
            "citation_paths": paths + [http_path]}


def live_model_research(archive, reference):
    """Read the observed remote policy and compare its tool feedback to exact replay."""
    from residual_study.agent_extension.verify_live_trace import validate_trace

    source = EXTENSION + "live_trace.json"
    verifier = EXTENSION + "verify_live_trace.py"
    archive.bytes(verifier)
    trace = archive.json(source)
    validate_trace(trace)
    steps = trace["steps"]
    require(len(steps) == 2 and [s["arguments"]["candidate"] for s in steps] ==
            ["weak_signed", "block_two_endpoint"], "Unexpected sequence of live mathematical checks")
    # These two calls use precisely the same arguments as the first two local trials,
    # whose results were independently recomputed above, including the exact witness.
    for live, exact in zip(steps, reference["steps"]):
        require(live["result"] == exact["result"], "Live tool observation differs from exact replay")
    return {**trace, "source_path": source, "verifier_path": verifier}


def build_paper_evidence(root: Path) -> dict:
    """Verify archived study inputs and regenerate paper tables from individual CSV rows."""
    archive = Archive(root)
    history = research_history(archive)
    signed, receipts = signed_research(archive)
    four_cell = four_cell_research(archive)
    extension = extension_research(archive)
    live = live_model_research(archive, extension)
    benchmark, summary, frozen = numerical_evidence(archive)
    fresh = archive.json(RESULTS + "fresh_stream.json")
    params = set(map(tuple, fresh["parameters"]))
    require(fresh["grid"] == 48 and fresh["query_count"] == len(params) == len(fresh["parameters"]) == 128
            and fresh["shared_with_training_tuning_or_original_stream"] == 0 and not params.intersection(map(tuple, frozen))
            and all(len(p) == 4 and all(.2 <= v <= 5 for v in p) for p in params), "Holdout stream identities")
    require(set(fresh["policies"]) == set(METHODS), "Missing holdout policy")
    for m, p in fresh["policies"].items():
        indices = p["fallback_indices_zero_based"]
        require(len(set(indices)) == len(indices) == p["fallbacks"] and all(0 <= i < fresh["query_count"] for i in indices)
                and p["fallbacks"] - p["false_alarms"] == p["pre_exceedances"] - p["missed"],
                f"Inconsistent holdout results for {m}")
    exact = archive.json(RESULTS + "exact_audit.json")
    require(exact["status"] == "passed" and exact["case_pattern_pairs"] == exact["boundary_parameter_cases"] * exact["ternary_residual_patterns"]
            and exact["cell_partition_enclosures"] == 4 * len(exact["nested_partitions"]) * exact["case_pattern_pairs"],
            "Independent exact audit case counts mismatch")
    archived = signed["turns"][1]["stdout"]["counterexample"]
    require(Fraction(exact["unsafe_shortcut_counterexample"]["actual_norm"]) == Fraction(archived["actual_error"]["exact"]),
            "Independent and native counterexample magnitudes differ")
    for path in ("residual_study/bounds.py","residual_study/exact_audit.py","residual_study/run_experiment.py",
                 "residual_study/fresh_stream.py"):
        archive.bytes(path)
    require(set(archive.hashes) == set(archive.expected), "The course paper used a different set of archived inputs")
    sources = [{"path": key, "sha256": value} for key, value in sorted(archive.hashes.items())]
    return {"schema_version":3, "history":history, "signed":signed, "four_cell":four_cell, "agent_extension":extension,
            "live_model_study":live,
            "benchmark":benchmark, "summary":summary, "receipts":receipts, "fresh":fresh, "exact":exact,
            "sources": sources, "source_sha256": dict(sorted(archive.hashes.items()))}


collect_paper_evidence = build_paper_evidence
