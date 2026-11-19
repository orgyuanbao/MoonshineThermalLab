"""Externally supplied evaluation harness for Moonshine's frozen thermal kernels.

This orchestration/measurement code is external assistance, not autonomous agent
discovery. Moonshine must review and execute it through its native Python tool.
No experiment runs on import. Final parameters are generated only by `freeze`,
after the configuration and source snapshots have been saved exclusively.
"""
from __future__ import annotations
import os
THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS")
for _name in THREAD_KEYS:
    os.environ[_name] = "1"
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "workspace" / "results" / "04_final_v1"
METHODS = ("raw_fom", "fast_fom", "raw_pod", "fast_pod", "adaptive")
GRIDS = (24, 48, 96)
REPEATS = (1, 2, 3)
SEED, COUNT, RANK, TAU = 20261027, 256, 8, 1e-3
ORIGIN = "Externally supplied evaluation harness; native Moonshine kernels and native execution tracked separately."


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(value):
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def load_kernel(directory):
    global np
    import numpy as np
    directory = Path(directory).resolve()
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("frozen_stage4_kernels", directory / "stage4_kernels_v1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if Path(sys.modules["thermal_solver"].__file__).resolve() != directory / "thermal_solver.py":
        raise RuntimeError("Unexpected thermal_solver module source")
    if module.TAU != TAU or module.MAX_RANK != 32 or module.CORRELATION != 1e-10:
        raise RuntimeError("Kernel constants differ from registered method")
    return module


def training_input(project=ROOT):
    baseline_path = Path(project) / "workspace/results/02_baseline.json"
    baseline = read(baseline_path)
    if baseline["selected_rank"] != RANK or baseline["exit_code"] != 0:
        raise RuntimeError("Registered rank-8 baseline missing")
    basis_path = Path(project) / baseline["basis_path"]
    with np.load(basis_path, allow_pickle=False) as saved:
        train, tune = saved["train_parameters"].copy(), saved["tune_parameters"].copy()
    if train.shape != (24, 4) or tune.shape != (12, 4):
        raise RuntimeError("Unexpected development parameter shapes")
    return train, tune, {"baseline_path": str(baseline_path.relative_to(project)).replace("\\", "/"),
                         "baseline_sha256": sha(baseline_path),
                         "basis_path": str(basis_path.relative_to(project)).replace("\\", "/"),
                         "basis_sha256": sha(basis_path), "train_array_sha256": array_sha(train)}


def source_files(directory):
    return {"kernel": Path(directory) / "stage4_kernels_v1.py",
            "solver": Path(directory) / "thermal_solver.py", "driver": Path(__file__).resolve()}


def freeze():
    kernel_dir = Path(__file__).resolve().parent
    load_kernel(kernel_dir)
    train, tune, training = training_input()
    sources = source_files(kernel_dir)
    # Existing output, even an incomplete freeze, is intentionally never overwritten.
    FINAL.mkdir(parents=True, exist_ok=False)
    config = {
        "origin": ORIGIN, "frozen_at_utc": now(), "n_values": list(GRIDS),
        "repetitions": list(REPEATS), "seed": SEED, "test_count": COUNT,
        "sampling": "exp(default_rng(20261027).uniform(log(0.2),log(5),size=(256,4)))",
        "rank": RANK, "tau": TAU, "max_rank": 32, "correlation": 1e-10,
        "h_order": ["left", "right", "bottom", "top"], "method_order": list(METHODS),
        "prefixes": [24, 256], "source_sha256": {name: sha(p) for name, p in sources.items()},
        "source_filenames": {name: p.name for name, p in sources.items()}, "training_input": training,
        "parameters_generated_at_configuration_write": False,
        "counting_policy": "Each repetition physically rebuilds one shared training set/SVD; each independent deployment ledger includes its full necessary share once. These ledger shares are not separate observed training executions.",
        "service_contract": "Return full field. Fixed-method optional residual diagnostics and reference errors are post hoc, outside primary service. Adaptive decision residual/fallback/update are inside service.",
        "update": "Two-pass block reorthogonalization (CGS2), not column-by-column MGS.",
        "raw_pod_implementation": "Equivalent full-space Galerkin implementation in this external driver, using the unchanged native thermal assembler; not a direct call to Moonshine's Reduced.predict.",
        "timing": "perf_counter; fixed method order; no preliminary final-stream warmup; numerical library imports/process startup excluded. Prior methods may warm shared hardware caches. Repetitions reset algorithm state, not hardware/OS cache state.",
        "floating_point": "Ordinary double-precision indicator; not outward-rounded certification.",
    }
    exclusive_json(FINAL / "frozen_configuration.json", config)
    snapshots = FINAL / "sources"
    snapshots.mkdir()
    for name, path in sources.items():
        with (snapshots / path.name).open("xb") as stream:
            stream.write(path.read_bytes())
    # This is the ONLY use of the final RNG in the complete driver.
    parameters = np.exp(np.random.default_rng(SEED).uniform(np.log(.2), np.log(5.), size=(COUNT, 4)))
    corners=np.array(list(itertools.product((.2,5.),repeat=4)))
    if any(np.array_equal(a, b) for a in np.vstack((train,tune,corners)) for b in parameters):
        raise RuntimeError("Final parameters overlap training/tuning/development corners")
    with (FINAL / "test_parameters.npy").open("xb") as stream:
        np.save(stream, parameters, allow_pickle=False)
    exclusive_json(FINAL / "test_parameters.json", {
        "generated_at_utc": now(), "role": "Frozen final online stream; repeated timings reuse these same accuracy samples",
        "seed": SEED, "count": COUNT, "array_sha256": array_sha(parameters), "parameters": parameters.tolist()})
    exclusive_json(FINAL / "freeze_completed.json", {
        "completed_at_utc": now(), "configuration_sha256": sha(FINAL / "frozen_configuration.json"),
        "parameters_npy_sha256": sha(FINAL / "test_parameters.npy"),
        "parameters_json_sha256": sha(FINAL / "test_parameters.json"), "parameter_array_sha256": array_sha(parameters),
        "configuration_saved_before_parameter_generation": True})
    print(json.dumps({"status": "frozen", "output": str(FINAL), "final_parameters_generated": COUNT, "origin": ORIGIN}, ensure_ascii=False))
    return 0


def verify_freeze():
    kernel_dir = Path(__file__).resolve().parent
    kernel = load_kernel(kernel_dir)
    config, completion = read(FINAL / "frozen_configuration.json"), read(FINAL / "freeze_completed.json")
    if sha(FINAL / "frozen_configuration.json") != completion["configuration_sha256"]:
        raise RuntimeError("Frozen configuration changed")
    for name, path in source_files(kernel_dir).items():
        if sha(path) != config["source_sha256"][name]:
            raise RuntimeError("Frozen source changed: " + name)
    if sha(FINAL / "test_parameters.npy") != completion["parameters_npy_sha256"]:
        raise RuntimeError("Frozen parameters changed")
    if sha(FINAL / "test_parameters.json") != completion["parameters_json_sha256"]:
        raise RuntimeError("Frozen parameter metadata changed")
    parameters = np.load(FINAL / "test_parameters.npy", allow_pickle=False)
    if parameters.shape != (COUNT, 4) or array_sha(parameters) != completion["parameter_array_sha256"]:
        raise RuntimeError("Invalid final parameter array")
    if not np.isfinite(parameters).all() or (parameters < .2).any() or (parameters > 5).any():
        raise RuntimeError("Out-of-domain final parameter")
    train, _, training = training_input()
    if training != config["training_input"]:
        raise RuntimeError("Frozen training provenance changed")
    return kernel, config, parameters, train


def raw_prediction(kernel, n, h, V):
    """Field-only full-space Galerkin baseline, with no unused fast caches."""
    t0 = time.perf_counter()
    kernel.checked_h(h)
    A, b, _ = kernel.assemble(n, h)
    t1 = time.perf_counter()
    Ar, br = V.T @ (A @ V), V.T @ b
    t2 = time.perf_counter()
    a = kernel.finite(np.linalg.solve(Ar, br))
    t3 = time.perf_counter()
    u = kernel.finite(V @ a)
    t4 = time.perf_counter()
    return u, {"assembly_seconds": t1-t0, "projection_seconds": t2-t1,
               "reduced_solve_seconds": t3-t2, "reconstruction_seconds": t4-t3, "service_seconds": t4-t0}


def actual_threads():
    try:
        from threadpoolctl import threadpool_info
        return {"available": True, "pools": threadpool_info()}
    except ImportError:
        return {"available": False, "note": "Requested environment recorded; actual pool counts unavailable"}


def execute_stream(kernel, parameters, train, n, repeat, destination, *, development=False, config_sha=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    events = (destination / "progress.jsonl").open("x", encoding="utf-8")
    counts = {"training_fom": 0, "raw_fom_service": 0, "fast_fom_service_and_reference": 0,
              "raw_pod": 0, "fast_pod": 0, "adaptive_rom": 0, "adaptive_trigger_fom": 0}
    def event(kind, **data):
        events.write(json.dumps({"utc": now(), "kind": kind, **data}, ensure_ascii=False, allow_nan=False) + "\n")
        events.flush()
    exclusive_json(destination / "run_started.json", {"started_at_utc": now(), "origin": ORIGIN, "n": n, "repeat": repeat,
                   "development_check": development, "query_count": len(parameters), "parameter_array_sha256": array_sha(parameters),
                   "configuration_sha256": config_sha, "status": "running"})
    try:
        # Initialization is physically repeated for every grid/repetition.
        t0 = time.perf_counter()
        geometry = kernel.Geometry(n)
        geometry_constructor_wall = time.perf_counter()-t0
        geometry_unattributed = max(0., geometry_constructor_wall-geometry.geometry_seconds-geometry.barrier_seconds)
        geometry_cost = geometry.geometry_seconds + geometry_unattributed
        event("geometry_ready", geometry_seconds=geometry_cost, barrier_seconds=geometry.barrier_seconds)
        training_rows, snapshots = [], []
        t0 = time.perf_counter()
        for i, h in enumerate(train):
            case_started = time.perf_counter()
            u, timing = kernel.full_solve(geometry, h, fast=True)
            counts["training_fom"] += 1
            snapshots.append(u)
            snapshot_pipeline_seconds = time.perf_counter()-case_started
            training_rows.append({"index": i, "h": h.tolist(), "timing": timing,
                                  "snapshot_pipeline_seconds":snapshot_pipeline_seconds})
            event("training_case", index=i, timing=timing)
        # Exclude log writes and list bookkeeping from required snapshot service;
        # include the necessary stacking allocation explicitly.
        training_wall_including_logging = time.perf_counter()-t0
        t0 = time.perf_counter()
        snapshots = np.column_stack(snapshots)
        snapshot_stack_seconds = time.perf_counter()-t0
        training_service = sum(r["snapshot_pipeline_seconds"] for r in training_rows) + snapshot_stack_seconds
        t0 = time.perf_counter()
        U, singular, _ = np.linalg.svd(snapshots, full_matrices=False)
        svd_seconds = time.perf_counter()-t0
        t0 = time.perf_counter()
        numerical_rank = int(np.sum(singular > max(snapshots.shape)*np.finfo(float).eps*singular[0]))
        if numerical_rank < RANK:
            raise RuntimeError("Training snapshots cannot supply registered rank")
        initial = U[:, :RANK]
        initial_orthogonality = float(np.linalg.norm(initial.T @ initial-np.eye(RANK), ord=np.inf))
        if initial_orthogonality > 1e-10:
            raise RuntimeError("Initial basis is not orthonormal")
        validation_seconds = time.perf_counter()-t0
        t0 = time.perf_counter()
        raw_basis = initial.copy()
        raw_copy_seconds = time.perf_counter()-t0
        t0 = time.perf_counter()
        fast = kernel.Reduced(geometry, initial)
        fast_initialization = time.perf_counter()-t0
        t0 = time.perf_counter()
        adaptive = kernel.Reduced(geometry, initial)
        adaptive_initialization = time.perf_counter()-t0
        if not np.array_equal(raw_basis, fast.V) or not np.array_equal(raw_basis, adaptive.V):
            raise RuntimeError("Methods do not share identical initial basis")
        common_pod = {"geometry": geometry_cost, "training_snapshot_service_and_stack": training_service,
                      "svd": svd_seconds, "rank_and_orthogonality_validation": validation_seconds}
        offline = {
            "raw_fom": {}, "fast_fom": {"geometry": geometry_cost},
            "raw_pod": {**common_pod, "basis_copy": raw_copy_seconds},
            "fast_pod": {**common_pod, "basis_copy_and_fast_cache": fast_initialization},
            "adaptive": {**common_pod, "basis_copy_and_fast_cache": adaptive_initialization,
                         "analytic_barrier": geometry.barrier_seconds},
        }
        offline_total = {m: sum(offline[m].values()) for m in METHODS}
        event("offline_complete", numerical_rank=numerical_rank, initial_rank=RANK, offline_per_method=offline_total)
        q, size = len(parameters), n*n
        fields = {m: np.empty((q, size)) for m in METHODS}
        pre_fields = np.empty((q, size))
        service = {m: [] for m in METHODS}
        initial_hash = array_sha(initial)
        # Complete every algorithm stream before reference-error evaluation.
        # Kernel calls see h, geometry and their own basis, never reference arrays.
        for method in METHODS:
            event("method_started", method=method)
            for i, h in enumerate(parameters):
                if method in ("raw_fom", "fast_fom"):
                    u, timing = kernel.full_solve(geometry, h, fast=method=="fast_fom")
                    counts["raw_fom_service" if method=="raw_fom" else "fast_fom_service_and_reference"] += 1
                    info = {"timing": timing}
                elif method == "raw_pod":
                    u, timing = raw_prediction(kernel, n, h, raw_basis)
                    counts["raw_pod"] += 1
                    info = {"timing": timing, "rank": RANK}
                elif method == "fast_pod":
                    u, timing = fast.predict(h, fast=True)
                    counts["fast_pod"] += 1
                    info = {"timing": timing, "rank": RANK}
                else:
                    basis_hash = array_sha(adaptive.V)
                    u, pre, info = adaptive.adaptive(h)
                    info["basis_before_sha256"] = basis_hash
                    pre_fields[i] = pre
                    counts["adaptive_rom"] = adaptive.rom_calls
                    counts["adaptive_trigger_fom"] = adaptive.fom_calls
                fields[method][i] = u
                row = {"index": i, "h": h.tolist(), **info}
                service[method].append(row)
                event("query_completed", method=method, **row)
            event("method_completed", method=method, query_count=q)

        event("all_algorithm_streams_completed_before_reference_evaluation")
        evaluation_started = time.perf_counter()
        references = fields["fast_fom"]
        methods = {}
        worst_arrays = {"V_initial": initial, "V_final": adaptive.V, "singular_values": singular}
        validation = []
        def check(name, passed, **details):
            validation.append({"name": name, "passed": bool(passed), **details})
        check("raw_and_fast_fom_equivalent", np.max(abs(fields["raw_fom"]-references)) <= 1e-9,
              max_abs=float(np.max(abs(fields["raw_fom"]-references))))
        check("raw_and_fast_fixed_pod_equivalent", np.max(abs(fields["raw_pod"]-fields["fast_pod"])) <= 1e-9,
              max_abs=float(np.max(abs(fields["raw_pod"]-fields["fast_pod"]))))
        check("adaptive_call_accounting", adaptive.fom_calls == sum(r["trigger"] for r in service["adaptive"]) and adaptive.rom_calls == q)
        check("rank_cap", adaptive.V.shape[1] <= min(32, size))
        final_orthogonality = float(np.linalg.norm(adaptive.V.T@adaptive.V-np.eye(adaptive.V.shape[1]), ord=np.inf))
        check("final_orthogonality", final_orthogonality <= 1e-10, value=final_orthogonality)
        prefixes = [1, q] if development else [24, COUNT]
        for method in METHODS:
            rows = service[method]
            for i, row in enumerate(rows):
                metric_started = time.perf_counter()
                row["error"] = kernel.errors(fields[method][i], references[i])
                row["reference_error_evaluation_seconds"] = time.perf_counter()-metric_started
                # Optional diagnostics for all returned fields are separate from service.
                row["optional_diagnostics"] = kernel.diagnostics(geometry, parameters[i], fields[method][i])
                if method == "adaptive":
                    t0 = time.perf_counter()
                    row["pre_error"] = kernel.errors(pre_fields[i], references[i])
                    epre = row["pre_error"]["field_linf"]
                    row["effectivity"] = row["eta"]/epre if epre > 0 else None
                    row["false_alarm"] = bool(row["trigger"] and epre <= TAU)
                    row["missed_failure"] = bool(not row["trigger"] and epre > TAU)
                    row["pre_error_evaluation_seconds"] = time.perf_counter()-t0
            worst_i = int(np.argmax([r["error"]["field_linf"] for r in rows]))
            worst_arrays[method+"_worst_field"] = fields[method][worst_i]
            worst_arrays[method+"_worst_reference"] = references[worst_i]
            worst_arrays[method+"_worst_h"] = parameters[worst_i]
            if method == "adaptive":
                pre_worst = int(np.argmax([r["pre_error"]["field_linf"] for r in rows]))
                worst_arrays["adaptive_worst_pre_field"] = pre_fields[pre_worst]
                worst_arrays["adaptive_worst_pre_reference"] = references[pre_worst]
                worst_arrays["adaptive_worst_pre_h"] = parameters[pre_worst]
            ledgers = {}
            for count in prefixes:
                prefix = rows[:count]
                online = sum(r["timing"]["service_seconds"] for r in prefix)
                extra_diag = sum(r["optional_diagnostics"]["seconds"] for r in prefix)
                ledger = {"queries": count, "offline_seconds": offline_total[method], "online_service_seconds": online,
                          "total_required_seconds": offline_total[method]+online,
                          "optional_diagnostics_seconds": extra_diag,
                          "total_with_optional_diagnostics_seconds": offline_total[method]+online+extra_diag,
                          "max_field_linf": max(r["error"]["field_linf"] for r in prefix),
                          "max_hotspot_error": max(r["error"]["hotspot"] for r in prefix),
                          "max_relative_l2": max(r["error"]["relative_l2"] for r in prefix),
                          "field_exceedances": sum(r["error"]["field_linf"]>TAU for r in prefix),
                          "hotspot_exceedances": sum(r["error"]["hotspot"]>TAU for r in prefix)}
                if method == "adaptive":
                    ledger.update(triggers=sum(r["trigger"] for r in prefix), updates=sum(r["status"]=="augmented" for r in prefix),
                                  correlated=sum(r["status"]=="correlated" for r in prefix), rank_cap_rejections=sum(r["status"]=="rank_cap" for r in prefix),
                                  zero_solution_rejections=sum(r["status"]=="zero_solution" for r in prefix),
                                  false_alarms=sum(r["false_alarm"] for r in prefix), missed_failures=sum(r["missed_failure"] for r in prefix),
                                  final_rank=prefix[-1]["rank_after"])
                ledgers[str(count)] = ledger
            methods[method] = {"offline_components_seconds": offline[method], "prefixes": ledgers,
                               "worst_query_index": worst_i, "cases": rows}
        for count in prefixes:
            for method in METHODS:
                ledger = methods[method]["prefixes"][str(count)]
                fast_reference = methods["fast_fom"]["prefixes"][str(count)]
                ledger["fast_fom_over_method_total_ratio"] = fast_reference["total_required_seconds"]/ledger["total_required_seconds"]
                ledger["fast_fom_over_method_online_ratio"] = fast_reference["online_service_seconds"]/ledger["online_service_seconds"]
        evaluation_wall = time.perf_counter()-evaluation_started
        check("all_returned_fields_finite", all(np.isfinite(value).all() for value in fields.values()))
        check("training_fom_count", counts["training_fom"] == 24)
        for name in ("raw_fom_service", "fast_fom_service_and_reference", "raw_pod", "fast_pod", "adaptive_rom"):
            check(name+"_count", counts[name] == q)
        check("trigger_definition", all(r["trigger"] == (r["eta"]>TAU) and r["returned_fom"]==r["trigger"] for r in service["adaptive"]))
        check("no_false_acceptances_in_observed_stream", not any(r["missed_failure"] for r in service["adaptive"]))
        # Store only worst-case fields and bases, not every large field array.
        with (destination / "worst_fields_and_bases.npz").open("xb") as stream:
            np.savez_compressed(stream, **worst_arrays)
        result = {
            "origin": ORIGIN, "completed_at_utc": now(), "execution_complete": True,
            "validation_passed": all(c["passed"] for c in validation), "n": n, "repeat": repeat,
            "development_check": development, "parameter_array_sha256": array_sha(parameters), "configuration_sha256": config_sha,
            "methods": methods, "counts_actual_executed": counts, "quality_checks": validation,
            "shared_actual_offline_work": {"physical_training_fom_calls": 24, "physical_svd_calls": 1,
                "geometry_constructor_wall_seconds": geometry_constructor_wall,
                "geometry_component_seconds": geometry.geometry_seconds, "geometry_unattributed_overhead_seconds": geometry_unattributed,
                "barrier_component_seconds": geometry.barrier_seconds, "training_service_seconds": training_service,
                "training_wall_including_log_writes_seconds": training_wall_including_logging, "snapshot_stack_seconds": snapshot_stack_seconds,
                "svd_seconds": svd_seconds, "basis_validation_seconds": validation_seconds,
                "raw_basis_copy_seconds": raw_copy_seconds, "fast_initialization_wall_seconds": fast_initialization,
                "adaptive_initialization_wall_seconds": adaptive_initialization, "numerical_rank": numerical_rank,
                "initial_orthogonality_inf": initial_orthogonality, "initial_basis_sha256": initial_hash,
                "training_case_records": training_rows,
                "ledger_explanation": "Shared work physically measured once in this repetition, fully charged to each standalone POD deployment. Geometry/barrier components are disjoint; initialization wall times are used once, never added to their internal subcomponents."},
            "reference_policy": "Fast FOM service outputs reused only after all algorithm streams complete. Adaptive fallback solves are additional real kernel calls; no reference answers passed to adaptive(h).",
            "environment": {"python": sys.version, "numpy": np.__version__, "requested_threads": {k:os.environ[k] for k in THREAD_KEYS}, "actual_threadpools": actual_threads()},
            "evaluation_wall_seconds_including_optional_diagnostics": evaluation_wall,
            "wall_seconds_before_result_write": time.perf_counter()-began,
            "array_storage_bytes_not_peak_memory": {"csr_data_indices_indptr": geometry.K.data.nbytes+geometry.K.indices.nbytes+geometry.K.indptr.nbytes,
                "training_snapshots": snapshots.nbytes, "initial_basis": initial.nbytes, "final_adaptive_basis": adaptive.V.nbytes,
                "fast_reduced_cache": fast.Kr.nbytes+fast.Dr.nbytes+fast.br.nbytes,
                "adaptive_final_reduced_cache": adaptive.Kr.nbytes+adaptive.Dr.nbytes+adaptive.br.nbytes,
                "stored_in_memory_comparison_fields": sum(a.nbytes for a in fields.values())+pre_fields.nbytes},
            "worst_fields_sha256": sha(destination/"worst_fields_and_bases.npz"),
            "limitations": ["Repeated timings reuse the same accuracy samples; no new independent accuracy sample count.",
                "Errors use a floating discrete FOM reference; no continuous PDE/industrial temperature certification.",
                "Floating barrier is not interval-certified.", "Fixed method order; hardware cache effects are not reset.",
                "Timing excludes library imports, process start, report/log persistence and post-hoc reference comparison.",
                "Total deployment cost excludes one-time research/tuning search, whose historical cost remains in Stage 2 evidence."]}
        exclusive_json(destination / "result.json", result)
        code = 0 if result["validation_passed"] else 2
        exclusive_json(destination / "completed.json", {"completed_at_utc": now(), "result_sha256": sha(destination/"result.json"),
                       "requested_exit_code": code, "execution_complete": True, "validation_passed": result["validation_passed"],
                       "exit_code_note": "Actual process return code must be read from native Moonshine tool evidence."})
        event("completed", exit_code=code)
        print(json.dumps({"status": "complete" if code==0 else "validation_failed", "n":n,"repeat":repeat,"output":str(destination),
              "counts":counts,"adaptive_prefixes":methods["adaptive"]["prefixes"],"requested_exit_code":code},ensure_ascii=False))
        return code
    except BaseException as exc:
        failure = {"origin": ORIGIN, "failed_at_utc": now(), "execution_complete": False, "status": "partial_failed",
                   "n":n,"repeat":repeat,"development_check":development,"counts_actual_executed":counts,
                   "exception":repr(exc),"traceback":traceback.format_exc(),"requested_exit_code":1}
        exclusive_json(destination / "failure.json", failure)
        event("failed", exception=repr(exc), counts=counts)
        print(failure["traceback"],file=sys.stderr,flush=True)
        return 1
    finally:
        events.close()


def run(n, repeat):
    kernel, config, parameters, train = verify_freeze()
    if n not in GRIDS or repeat not in REPEATS:
        raise ValueError("Grid/repetition not registered")
    return execute_stream(kernel, parameters, train, n, repeat, FINAL/f"n{n}"/f"repeat{repeat:02d}",
                          config_sha=sha(FINAL/"frozen_configuration.json"))


def run_group(n):
    if n not in (24,48):
        raise ValueError("Only n=24 or n=48 may run as a group; split n=96 repetitions")
    completed=[]
    for repeat in REPEATS:
        code=run(n,repeat)
        if code:
            print(json.dumps({"group_n":n,"completed_repetitions":completed,"stopped_at_repeat":repeat,"requested_exit_code":code}))
            return code
        completed.append(repeat)
    print(json.dumps({"group_n":n,"completed_repetitions":completed,"requested_exit_code":0}))
    return 0


def summarize():
    verify_freeze()
    records, missing, invalid, sources = [], [], [], {}
    for n in GRIDS:
        for repeat in REPEATS:
            directory=FINAL/f"n{n}"/f"repeat{repeat:02d}"
            path=directory/"result.json"
            complete=directory/"completed.json"
            if not path.exists() or not complete.exists():
                missing.append({"n":n,"repeat":repeat,"partial_failure_present":(directory/"failure.json").exists()})
                continue
            result, marker = read(path), read(complete)
            if marker["result_sha256"]!=sha(path) or not result["execution_complete"] or not result["validation_passed"]:
                invalid.append({"n":n,"repeat":repeat,"reason":"hash/completion/validation failed"})
                continue
            records.append(result)
            sources[str(path.relative_to(FINAL)).replace("\\","/")]=sha(path)
    comparisons=[]
    for n in GRIDS:
        group=[r for r in records if r["n"]==n]
        if not group:
            continue
        for count in [24,COUNT]:
            for method in METHODS:
                ledgers=[r["methods"][method]["prefixes"][str(count)] for r in group]
                def stats(key):
                    values=[r[key] for r in ledgers]
                    return {"median":float(np.median(values)),"minimum":float(min(values)),"maximum":float(max(values)),"values":values}
                row={"n":n,"queries":count,"method":method,"observed_repetitions":len(group),
                     "total_required_seconds":stats("total_required_seconds"),"online_service_seconds":stats("online_service_seconds"),
                     "offline_seconds":stats("offline_seconds"),"fast_fom_over_method_total_ratio":stats("fast_fom_over_method_total_ratio"),
                     "fast_fom_over_method_online_ratio":stats("fast_fom_over_method_online_ratio"),
                     "max_field_linf":stats("max_field_linf"),"max_hotspot_error":stats("max_hotspot_error"),
                     "field_exceedances_per_repetition":[r["field_exceedances"] for r in ledgers]}
                if method=="adaptive":
                    for key in ("triggers","updates","false_alarms","missed_failures","final_rank","correlated","rank_cap_rejections"):
                        row[key+"_per_repetition"]=[r[key] for r in ledgers]
                comparisons.append(row)
    done=not missing and not invalid and len(records)==9
    summary={"origin":ORIGIN,"created_at_utc":now(),"status":"complete" if done else "partial",
             "required_repetitions":9,"completed_valid_repetitions":len(records),"missing":missing,"invalid":invalid,
             "comparisons":comparisons,"source_result_sha256":sources,
             "interpretation":"A total ratio >1 means faster than cached fast FOM, including full necessary offline cost. Online ratios omit offline cost. Three repetitions reuse the same 256 samples; do not count 768 independent cases.",
             "counts_actual_executed_complete_runs":{k:sum(r["counts_actual_executed"][k] for r in records) for k in (records[0]["counts_actual_executed"] if records else [])}}
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    exclusive_json(FINAL/f"summary_{stamp}.json",summary)
    if done:
        final_path=FINAL/"summary.json"
        if not final_path.exists():
            exclusive_json(final_path,summary)
        elif read(final_path)["source_result_sha256"]!=sources:
            raise RuntimeError("Existing final summary refers to different source results")
    def compact_number(value):
        return float(format(value,".7g"))
    scientific=[]
    for row in comparisons:
        entry={"n":row["n"],"q":row["queries"],"method":row["method"],"repeats":row["observed_repetitions"],
               "T":[compact_number(row["total_required_seconds"][k]) for k in ("median","minimum","maximum")],
               "S":[compact_number(row["fast_fom_over_method_total_ratio"][k]) for k in ("median","minimum","maximum")],
               "field_range":[compact_number(row["max_field_linf"][k]) for k in ("minimum","maximum")],
               "hotspot_range":[compact_number(row["max_hotspot_error"][k]) for k in ("minimum","maximum")],
               "field_exceedances":row["field_exceedances_per_repetition"]}
        if row["method"]=="adaptive":
            entry["adaptive"]={key:row[key+"_per_repetition"] for key in ("triggers","updates","false_alarms","missed_failures","final_rank","correlated","rank_cap_rejections")}
        scientific.append(entry)
    stdout={"status":summary["status"],"complete_runs":len(records),"missing":missing,"invalid":invalid,"output":str(FINAL),
            "compact_keys":{"T":"[median,min,max] total required seconds including offline","S":"[median,min,max] fast-FOM/method total cost; >1 means faster",
                            "field_range":"min/max of repetition-wise worst field errors","hotspot_range":"min/max of repetition-wise worst hotspot errors"},
            "scientific_summary":scientific,"actual_counts_complete_runs":summary["counts_actual_executed_complete_runs"],
            "accuracy_sample_note":"Same 256 parameters reused across timing repetitions; not 768 independent samples.",
            "full_precision_summary_json":str(FINAL/"summary.json") if done else str(FINAL/f"summary_{stamp}.json")}
    serialized=json.dumps(stdout,ensure_ascii=False,separators=(",",":"))
    if len(serialized)>=15000:
        raise RuntimeError("Compact scientific summary unexpectedly exceeds 15000 characters; full summary saved")
    print(serialized)
    return 0 if done else 2


def development_check(kernel_dir, project, output, n=24):
    kernel=load_kernel(kernel_dir)
    train,tune,training=training_input(project)
    # Existing development values only. Deliberately do not invoke any RNG.
    parameters=tune[:4].copy()
    code=execute_stream(kernel,parameters,train,n,1,output,development=True)
    if code==0:
        result=read(Path(output)/"result.json")
        for method in METHODS:
            for ledger in result["methods"][method]["prefixes"].values():
                assert abs(ledger["total_required_seconds"]-ledger["offline_seconds"]-ledger["online_service_seconds"])<1e-12
        exclusive_json(Path(output)/"development_harness_check.json",{"passed":True,"final_rng_called":False,
            "final_test_generated":False,"source":"First four existing tuning parameters", "training_provenance":training,
            "reused_as_final_results":False,"driver_sha256":sha(__file__)})
    return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("freeze")
    run_parser=sub.add_parser("run")
    run_parser.add_argument("--n",type=int,choices=GRIDS,required=True)
    run_parser.add_argument("--repeat",type=int,choices=REPEATS,required=True)
    group_parser=sub.add_parser("run-group")
    group_parser.add_argument("--n",type=int,choices=(24,48),required=True)
    sub.add_parser("summarize")
    development=sub.add_parser("development-check")
    development.add_argument("--kernel-dir",type=Path,required=True)
    development.add_argument("--project",type=Path,required=True)
    development.add_argument("--output",type=Path,required=True)
    development.add_argument("--n",type=int,choices=GRIDS,default=24)
    args=parser.parse_args()
    if args.action=="freeze": return freeze()
    if args.action=="run": return run(args.n,args.repeat)
    if args.action=="run-group": return run_group(args.n)
    if args.action=="summarize": return summarize()
    return development_check(args.kernel_dir,args.project,args.output,args.n)


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted; partial logs preserved.",file=sys.stderr,flush=True)
        raise SystemExit(130)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)
