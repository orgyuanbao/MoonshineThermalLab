"""Replay the frozen thermal parameter stream with five residual certificates (offline; no model account)."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from datetime import datetime, timezone

# Match the archived single-thread numerical protocol before importing NumPy or SciPy.
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[key] = "1"
import numpy as np
import scipy
from scipy.sparse.linalg import spsolve

from bounds import BLOCKS_PER_AXIS, Certificates, NAMES

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "thermal/home/projects/thermal-rom"
FINAL = PROJECT / "workspace/results/04_final_v1"
sys.path.insert(0, str(FINAL / "sources"))
import stage4_kernels_v1 as kernel

TOL = 0.001
FLOAT_SLACK = 2e-10   # forensic numerical checks only, never used to change an accept/fallback decision
GRID_OPTIONS = (24, 48, 96)
PREDS = ("fixed8", "old_pre")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def frozen_inputs():
    complete = read_json(FINAL / "freeze_completed.json")
    config_path = FINAL / "frozen_configuration.json"
    if digest(config_path) != complete["configuration_sha256"]:
        raise ValueError("Frozen protocol hash differs from its receipt.")
    config = read_json(config_path)
    inputs = [FINAL / "test_parameters.npy", config_path]
    required = {inputs[0]: complete["parameters_npy_sha256"]}
    for key in ("kernel", "solver", "driver"):
        required[FINAL / "sources" / config["source_filenames"][key]] = config["source_sha256"][key]
    train_path = PROJECT / config["training_input"]["basis_path"]
    required[train_path] = config["training_input"]["basis_sha256"]
    if any(digest(path) != expected for path, expected in required.items()):
        raise ValueError("A frozen input differs from its registered file digest.")
    params = np.load(inputs[0], allow_pickle=False)
    with np.load(train_path, allow_pickle=False) as data:
        train = data["train_parameters"].copy()
    if (params.shape != (256, 4) or train.shape != (24, 4) or config["tau"] != TOL or
            config["rank"] != 8 or config["h_order"] != ["left","right","bottom","top"]):
        raise ValueError("Unexpected protocol")
    return train, params, {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(inputs)|set(required))}


def basis_and_references(n, train, params):
    costs = {}
    geometry = kernel.Geometry(n)
    costs["geometry_s"] = geometry.geometry_seconds
    start = perf_counter()
    snapshots = np.column_stack([kernel.full_solve(geometry, h)[0] for h in train])
    orthogonal, _, _ = np.linalg.svd(snapshots, full_matrices=False)
    costs["24_training_solves_and_svd_s"] = perf_counter()-start
    saved_path = FINAL / f"n{n}/repeat01/worst_fields_and_bases.npz"
    with np.load(saved_path, allow_pickle=False) as saved:
        basis = saved["V_initial"].copy()
    # Orientations/signs of singular vectors are not unique across machines.
    overlap = orthogonal[:, :8].T @ basis
    err = float(np.max(np.abs(basis - orthogonal[:, :8] @ overlap)))
    if err > 1e-8:
        raise ArithmeticError("Frozen and retrained bases span different subspaces")
    start = perf_counter()
    refs = [kernel.full_solve(geometry, h)[0] for h in params]
    costs["independent_reference_solves_s"] = perf_counter()-start
    return geometry, basis, refs, costs, err, saved_path


def synthetic_probes(g, cert):
    n, width = g.n, cert.block_width
    y,x = np.indices((n,n))
    tile = (y//width)*4 + x//width
    patterns = {
        "all_plus": np.ones(n*n),
        "single_corner_cell": ((x==0)&(y==0)).ravel().astype(float),
        "block_checker": np.where(((x//width+y//width)%2)==0,1.,-1.).ravel(),
        "fine_checker": np.where((x+y)%2==0,1.,-1.).ravel(),
        "two_opposite_blocks": ((tile==0).astype(float)-(tile==15).astype(float)).ravel(),
    }
    records = []
    for code, h in (("weak", [0.2]*4),("mixed",[0.2,5.0,1.0,2.0])):
        A = g.matrix(h)
        for key, r in patterns.items():
            actual = float(np.max(np.abs(spsolve(A, r))))
            bounds = cert.all_bounds(r)
            validate_bounds(bounds, actual)
            records.append({"pattern":key,"boundary":code,"actual_linf":actual,**bounds})
    return records


def validate_bounds(bounds, error):
    values = [float(bounds[k]) for k in NAMES]
    if not np.isfinite(values+[error]).all():
        raise ArithmeticError("Nonfinite value")
    scale = max(values[0],1.)
    if any(right-left > FLOAT_SLACK*scale for left,right in zip(values,values[1:])):
        raise ArithmeticError(f"Certificate nesting violated: {values}")
    if error-values[-1] > FLOAT_SLACK*max(1.,error):
        raise ArithmeticError(f"Certificate underestimated observed reference error: {error}, {values}")


def paired_replay(n, g, basis, h_values, refs, cert):
    fixed, original = kernel.Reduced(g,basis), kernel.Reduced(g,basis)
    result_path = FINAL / f"n{n}/repeat01/result.json"
    saved = read_json(result_path)["methods"]
    if not len(saved["adaptive"]["cases"]) == len(saved["fast_pod"]["cases"]) == 256:
        raise ValueError("Incomplete old trajectory")
    rows = []
    max_archive_delta = 0.
    for i,(h,ref) in enumerate(zip(h_values, refs)):
        _, pre, info = original.adaptive(h)
        previous = saved["adaptive"]["cases"][i]
        if any(info[k] != previous[k] for k in ("trigger","rank_before","rank_after")):
            raise ArithmeticError(f"Historical decisions changed: n={n} case={i}")
        for track, u, frozen_error, frozen_eta in (
                ("fixed8", fixed.predict(h)[0], saved["fast_pod"]["cases"][i]["error"]["field_linf"],
                 saved["fast_pod"]["cases"][i]["optional_diagnostics"]["eta"]),
                ("old_pre", pre,previous["pre_error"]["field_linf"],previous["eta"])):
            residual = g.b-g.action(h,u)
            actual = float(np.max(np.abs(ref-u)))
            bounds = cert.all_bounds(residual)
            validate_bounds(bounds, actual)
            difference = max(abs(actual-frozen_error),abs(bounds["analytic"]-frozen_eta))
            max_archive_delta = max(max_archive_delta, difference)
            if difference > 1e-8 or not np.array_equal(h, previous["h"]):
                raise ArithmeticError(f"Frozen evidence mismatch: n={n} case={i}")
            rows.append({"n":n,"track":track,"index":i,"left":h[0],"right":h[1],"bottom":h[2],"top":h[3],
                         "residual_linf":float(max(abs(residual))),"error_linf":actual,**bounds})
    return rows,max_archive_delta,result_path


def summarize_pairs(rows):
    groups = {}
    for track in PREDS:
        segment = [r for r in rows if r["track"] == track]
        truth = np.array([r["error_linf"] for r in segment])
        entries = {}
        for name in NAMES:
            values = np.array([r[name] for r in segment])
            alarms, failed = values>TOL, truth>TOL
            nonzero = truth > 0.0
            entries[name] = {"alarms":int(alarms.sum()), "false_alarms":int((alarms & ~failed).sum()),
                             "missed":int((~alarms & failed).sum()),"true_exceedances":int(failed.sum()),
                             "min_bound_minus_error":float(np.min(values-truth)),
                             "median_effectivity":float(np.median(values[nonzero]/truth[nonzero])) if np.any(nonzero) else None,
                             "median_bound":float(np.median(values))}
        groups[track]=entries
    return groups




def closed_loop(n, name, cert, g, basis, h_values, refs):
    started = perf_counter()
    model = kernel.Reduced(g, basis)
    setup = perf_counter()-started
    rows, costs = [], {"online_s":0.0,"decision_s":0.0,"fallback_s":0.0,"update_s":0.0}
    for i,h in enumerate(h_values):
        # No reference argument is passed into the decision or paid fallback.
        t0 = perf_counter()
        pre, _ = model.predict(h)
        t1 = perf_counter()
        residual = g.b-g.action(h,pre)
        bound = cert.bound(name,residual)
        t2 = perf_counter()
        fallback = bound > TOL
        out = pre
        rank_before = model.V.shape[1]
        fallback_s = update_s = 0.
        if fallback:
            t3 = perf_counter()
            out,_ = kernel.full_solve(g,h)
            t4 = perf_counter()
            model.augment(out)
            fallback_s = t4-t3
            update_s = perf_counter()-t4
        costs["online_s"] += perf_counter()-t0
        costs["decision_s"] += t2-t1
        costs["fallback_s"] += fallback_s
        costs["update_s"] += update_s
        # Reference / diagnostics are outside the service clock.
        error = float(np.max(abs(refs[i]-pre)))
        returned_error = float(np.max(abs(refs[i]-out)))
        if not np.isfinite([bound,error,returned_error]).all() or bound+FLOAT_SLACK*max(1.,error)<error:
            raise ArithmeticError("Observed error exceeds the decision certificate")
        rows.append({"n":n,"method":name,"index":i,"rank_before":rank_before,"rank_after":model.V.shape[1],
                     "bound":bound,"pre_error_linf":error,"fallback":int(fallback),"returned_error_linf":returned_error})
    costs["reduced_setup_s"] = setup
    return rows,costs


def summarize_closed(rows):
    return {"fallbacks":sum(r["fallback"] for r in rows),
            "false_alarms":sum(r["fallback"] and r["pre_error_linf"]<=TOL for r in rows),
            "missed":sum(not r["fallback"] and r["pre_error_linf"]>TOL for r in rows),
            "pre_exceedances":sum(r["pre_error_linf"]>TOL for r in rows),
            "returned_exceedances":sum(r["returned_error_linf"]>TOL for r in rows),
            "max_pre_error":max(r["pre_error_linf"] for r in rows),
            "max_returned_error":max(r["returned_error_linf"] for r in rows),
            "final_rank":rows[-1]["rank_after"]}


def run_grid(n, h_values, train, repeats):
    g,basis,refs,common,subspace_error,basis_path = basis_and_references(n,train,h_values)
    cert = Certificates(g)
    synthetic = synthetic_probes(g,cert)
    paired,delta,result_path = paired_replay(n,g,basis,h_values,refs,cert)
    paired_summary = summarize_pairs(paired)
    print(f"n={n} paired old predictions: "+ ", ".join(f"{name} {paired_summary['old_pre'][name]['alarms']}" for name in NAMES),flush=True)
    closed_rows = {}
    timing_samples = {name:[] for name in NAMES}
    for repeat in range(repeats):
        # Rotate method start order between repeated services.
        order = NAMES[repeat%len(NAMES):]+NAMES[:repeat%len(NAMES)]
        for name in order:
            rows, timing = closed_loop(n,name,cert,g,basis,h_values,refs)
            if name not in closed_rows:
                closed_rows[name] = rows
            elif rows != closed_rows[name]:
                raise ArithmeticError("Distinct numerical trajectories across timing repeats")
            timing["policy_total_s"] = (common["geometry_s"] + common["24_training_solves_and_svd_s"] +
                                        cert.offline[name] + timing["reduced_setup_s"] + timing["online_s"])
            timing_samples[name].append(timing)
    archival = [r for r in paired if r["track"]=="old_pre"]
    for old,r in zip(archival,closed_rows["analytic"]):
        if old["error_linf"]!=r["pre_error_linf"] or (old["analytic"]>TOL)!=bool(r["fallback"]):
            raise ArithmeticError("New runner did not replay old scalar policy")
    closed = {}
    for name in NAMES:
        samples = timing_samples[name]
        closed[name] = {**summarize_closed(closed_rows[name]),
                        "indicator_preprocessing_s":cert.offline[name],
                        "timing_median_s":{key:float(np.median([s[key] for s in samples])) for key in samples[0]},
                        "timing_samples_s":samples}
    evidence = {"basis_artifact_sha256":digest(basis_path),"frozen_repeat01_result_sha256":digest(result_path),
                "retrained_basis_subspace_max_delta":subspace_error,"old_eta_or_error_max_abs_delta":delta,
                "old_trigger_and_rank_replay_checked":True}
    grid = {"queries":len(h_values),"preparation_seconds":cert.preparation,"common_seconds":common,
            "one_endpoint_template_bytes":cert.templates_bytes,"coefficient_checks":cert.coefficient_checks,
            "validation":evidence,"paired":paired_summary,"closed":closed,"analytic_probes":synthetic}
    print(f"n={n} closed fallbacks: "+ ", ".join(f"{key} {closed[key]['fallbacks']}" for key in NAMES),flush=True)
    return grid,paired,[r for name in NAMES for r in closed_rows[name]]


def verify_against(source, dest, grids, count):
    """Compare all numeric outputs in deterministic case tables; ignore platform-specific timings."""
    counts = {}
    for file, keys in (("paired_cases.csv",("n","track","index")),("closed_loop_cases.csv",("n","method","index"))):
        def load_rows(path):
            with path.open(encoding="utf-8",newline="") as handle:
                result = {}
                for row in csv.DictReader(handle):
                    if int(row["n"]) in grids and int(row["index"])<count:
                        key = tuple(row[k] for k in keys)
                        if key in result:
                            raise ValueError(f"Duplicate key {key}")
                        result[key]=row
                return result
        computed, expected = load_rows(dest/file),load_rows(source/file)
        if not computed or computed.keys()!=expected.keys():
            raise ValueError("Missing case rows for "+file)
        max_diff=0.
        for key, actual in computed.items():
            saved = expected[key]
            for field,value in actual.items():
                if field in keys:
                    continue
                if field in ("rank_before","rank_after","fallback"):
                    if value!=saved[field]:
                        raise ValueError(f"Decision changed: {key}/{field}")
                else:
                    a,b=float(value),float(saved[field])
                    if not np.isclose(a,b,rtol=1e-7,atol=1e-10):
                        raise ValueError(f"Numerical mismatch in {file}: {key}, {field}: {a} / {b}")
                    if file == "paired_cases.csv" and field in NAMES and (a>TOL)!=(b>TOL):
                        raise ValueError(f"Paired gate changed: {key}/{field}")
                    max_diff=max(max_diff,abs(a-b))
        counts[file]={"rows":len(computed),"max_numeric_abs_diff":max_diff}
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grids",nargs="+",type=int,choices=GRID_OPTIONS,default=list(GRID_OPTIONS))
    parser.add_argument("--queries",type=int,default=256,help="Use this many queries from the original frozen order.")
    parser.add_argument("--repeats",type=int,default=3,help="Timed closed-loop repeats with full state resets.")
    parser.add_argument("--output",type=Path,help="A new directory, created without overwriting any prior result.")
    parser.add_argument("--check-against",type=Path,help="Folder containing the two published deterministic CSVs.")
    args=parser.parse_args()
    if not 1<=args.queries<=256 or args.repeats<1 or len(set(args.grids))!=len(args.grids):
        parser.error("Use 1..256 queries, positive repeats, and distinct grid sizes.")
    now=datetime.now(timezone.utc)
    out=(args.output or ROOT/"thermal/reproductions"/("residual-"+now.strftime("%Y%m%dT%H%M%S.%fZ"))).resolve()
    out.mkdir(parents=True, exist_ok=False)
    train,params,inputs=frozen_inputs()
    summary={"schema_version":1,"origin":"Independent numerical audit using the original frozen kernels/data; zero model calls.",
             "timestamp_utc":now.isoformat(),"model_calls":0,"new_accuracy_parameters":0,
             "fixed_partition":[BLOCKS_PER_AXIS,BLOCKS_PER_AXIS],"tolerance":TOL,
             "parameter_count":args.queries,"repeats":args.repeats,
             "floating_checks_slack":FLOAT_SLACK,"timing_scope":"Observed perf_counter costs, single-thread requested. Per-method total includes one shared measured geometry/training/SVD charge, certificate preprocessing, reduced setup and online service; diagnostic references excluded. Preprocessing sampled once per grid; timing repeats reset reduced-model state and rotate policy order.",
             "environment":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__,"platform":platform.platform()},
             "input_file_sha256":inputs,"grids":{}}
    pairs,closed=[],[]
    for n in args.grids:
        result,rs,cs=run_grid(n, params[:args.queries],train,args.repeats)
        summary["grids"][str(n)] = result
        pairs.extend(rs)
        closed.extend(cs)
    write_csv(out/"paired_cases.csv",pairs)
    write_csv(out/"closed_loop_cases.csv",closed)
    if args.check_against:
        summary["reproduction_comparison"]=verify_against(args.check_against,out,set(args.grids),args.queries)
    summary["status"]="passed"
    write_json(out/"summary.json",summary)
    print(json.dumps({"status":"passed","paired_rows":len(pairs),"closed_rows":len(closed),
                      "summary":str(out/"summary.json")},ensure_ascii=True))


if __name__=="__main__":
    main()
