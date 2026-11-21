"""Independent exact-arithmetic audit for the four-cell Robin grid (standard library)."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path


RESULT = Path(__file__).resolve().parent / "results" / "exact_audit.json"
PARTITIONS = (
    ((0, 1, 2, 3),),
    ((0, 1), (2, 3)),
    ((0,), (1,), (2,), (3,)),
)


def inverse_grid(n, h):
    """Independently assemble cell fluxes and invert by rational elimination."""
    dx = F(1, n)
    faces = [dx / (1 / coef + dx / 2) for coef in h]
    size = n*n
    rows = []
    for i in range(size):
        y, x = divmod(i, n)
        values = [F(0) for _ in range(size)]
        adjacent = ((y, x-1), (y, x+1), (y-1, x), (y+1, x))
        for face, (iy, ix) in enumerate(adjacent):
            if 0 <= iy < n and 0 <= ix < n:
                values[i] += 1
                values[iy*n+ix] -= 1
            else:
                values[i] += faces[face]
        rows.append(values + [F(i == j) for j in range(size)])
    for k in range(size):
        pivot = rows[k][k]
        rows[k] = [v / pivot for v in rows[k]]
        for i in range(size):
            if i != k:
                factor = rows[i][k]
                rows[i] = [x - factor*y for x, y in zip(rows[i], rows[k])]
    return [row[size:] for row in rows]


def apply(matrix, v):
    return [sum(x*y for x, y in zip(row, v)) for row in matrix]


def envelopes(green_min, green_max, partition, residual):
    boxes = []
    for cells in partition:
        lo = min(residual[i] for i in cells)
        hi = max(residual[i] for i in cells)
        boxes.append((cells, lo, hi))
    out = []
    for i in range(4):
        unsigned = pos = neg = lower = upper = F(0)
        for cells, lo, hi in boxes:
            g = sum(green_min[i][j] for j in cells)
            G = sum(green_max[i][j] for j in cells)
            unsigned += G * max(-lo, hi)
            pos += G * max(0, hi)
            neg += G * max(0, -lo)
            lower += g * max(0, lo) - G * max(0, -lo)
            upper += G * max(0, hi) - g * max(0, -hi)
        out.append((lower, upper, max(-lower, upper), max(pos, neg), unsigned))
    return out


def require(ok, message):
    if not ok:
        raise ArithmeticError(message)


def compute():
    h_lo, h_hi = F(1, 5), F(5)
    weak = inverse_grid(2, (h_lo,)*4)
    strong = inverse_grid(2, (h_hi,)*4)
    kernels = [(h, inverse_grid(2, h)) for h in
               [*product((h_lo, h_hi), repeat=4), (F(1),)*4, (F(1), F(1, 2), F(3), F(2))]]
    residuals = list(product((-1, 0, 1), repeat=4))
    count = 0
    for r in residuals:
        boxes = [envelopes(strong, weak, p, r) for p in PARTITIONS]
        scalar = max(map(sum, weak)) * max(map(abs, r))
        for h, G in kernels:
            error = apply(G, r)
            for i, e in enumerate(error):
                previous = None
                for grid in boxes:
                    low, high, two_sided, signed, unsigned = grid[i]
                    require(low <= e <= high, f"Enclosure failed at {h}, {r}, cell {i}")
                    require(abs(e) <= two_sided <= signed <= unsigned <= scalar,
                            "Bound ordering failed")
                    if previous is not None:
                        require(previous[0] <= low and high <= previous[1],
                                "Nested partitions widened an interval")
                    previous = (low, high)
                    count += 1
    coherent = max(abs(x) for x in apply(weak, (1, 1, 1, 1)))
    checker = max(abs(x) for x in apply(weak, (1, -1, -1, 1)))
    require(coherent == F(21, 4) and checker == F(21, 88), "Unexpected exact illustration")
    # Move one positive unit source without changing its magnitude or sign.
    g3 = inverse_grid(3, (h_hi,)*4)
    g3weak = inverse_grid(3, (h_lo,)*4)
    impulses = {label: {"actual_at_strong_boundary": str(max(row[index] for row in g3)),
                        "singleton_position_bound_all_boundaries": str(max(row[index] for row in g3weak))}
                for label, index in (("corner", 0), ("center", 4))}
    # A componentwise matrix order can reverse under multiplication by a signed vector.
    mixed = (F(-46, 21), F(46, 21), F(-46, 21), F(46, 21))
    unsafe = max(map(abs, apply(weak, mixed)))
    actual = max(map(abs, apply(inverse_grid(2, (h_hi, h_lo, h_lo, h_lo)), mixed)))
    require((unsafe, actual) == (1, F(437, 269)), "Unsafe signed shortcut counterexample failed")
    return {
        "three_by_three_positive_impulse": impulses,
        "unsafe_shortcut_counterexample": {"weak_signed_norm": str(unsafe), "actual_norm": str(actual)},
        "arithmetic": "rational, standard-library Fraction",
        "grid": [2, 2],
        "boundary_parameter_cases": len(kernels),
        "ternary_residual_patterns": len(residuals),
        "nested_partitions": [len(p) for p in PARTITIONS],
        "case_pattern_pairs": len(kernels)*len(residuals),
        "cell_partition_enclosures": count,
        "weak_boundary_example": {
            "boundary_coefficients": ["1/5"]*4, "residual_infinity_norm": 1,
            "uniform_residual_true_error": str(coherent),
            "checkerboard_residual_true_error": str(checker),
            "error_ratio": str(coherent/checker),
        },
        "status": "passed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="update the saved exact audit")
    args = parser.parse_args()
    data = compute()
    if args.record:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    elif json.loads(RESULT.read_text(encoding="utf-8")) != data:
        raise SystemExit("Exact counts or values differ from the published audit.")
    print(json.dumps(data))


if __name__ == "__main__":
    main()
