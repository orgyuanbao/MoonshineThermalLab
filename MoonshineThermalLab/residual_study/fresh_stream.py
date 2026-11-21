"""Test unchanged policies on a second deterministic parameter stream, n=48."""
import argparse
import json
from pathlib import Path

from run_experiment import (
    FINAL, PROJECT, Certificates, NAMES, basis_and_references, closed_loop, frozen_inputs,
    np, read_json, summarize_closed,
)


SEED, N, COUNT = 20261121, 48, 128
STUDY = Path(__file__).resolve().parent
REFERENCE = STUDY / "results" / "fresh_stream.json"


def evaluate():
    training, original, _ = frozen_inputs()
    archive = read_json(FINAL / "frozen_configuration.json")
    with np.load(PROJECT / archive["training_input"]["basis_path"], allow_pickle=False) as datasets:
        tuning = datasets["tune_parameters"]
    values = np.exp(np.random.default_rng(SEED).uniform(np.log(0.2), np.log(5), size=(COUNT, 4)))
    previous = {tuple(h) for h in np.vstack((training, tuning, original))}
    if len({tuple(h) for h in values}) != COUNT or any(tuple(h) in previous for h in values):
        raise ArithmeticError("Unexpected overlap of parameter streams")
    geom, basis, refs, _, _, _ = basis_and_references(N, training, values)
    cert = Certificates(geom)
    strategies = {}
    for name in NAMES:
        decisions, _ = closed_loop(N, name, cert, geom, basis, values, refs)
        stats = summarize_closed(decisions)
        strategies[name] = {key: stats[key] for key in
                            ("fallbacks","false_alarms","missed","pre_exceedances","returned_exceedances","final_rank")}
        strategies[name]["fallback_indices_zero_based"] = [r["index"] for r in decisions if r["fallback"]]
    return {
        "scope": "Additional parameter stream with the same numerical code, training set and policy definitions; no model calls.",
        "grid": N, "query_count": COUNT, "sampling": "independent uniform log-coordinates on [log(0.2), log(5)]",
        "seed": SEED, "shared_with_training_tuning_or_original_stream": 0,
        "parameters": values.tolist(), "policies": strategies,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="write evidence after an intentional protocol update")
    args = parser.parse_args()
    data = evaluate()
    if args.record:
        REFERENCE.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    else:
        saved = read_json(REFERENCE)
        if data["policies"] != saved["policies"] or not np.allclose(data["parameters"], saved["parameters"], rtol=2e-15, atol=0):
            raise SystemExit("Fresh-stream reproduction differs from published results")
    print(json.dumps({k: [v["fallbacks"],v["returned_exceedances"]] for k,v in data["policies"].items()}))


if __name__ == "__main__":
    main()
