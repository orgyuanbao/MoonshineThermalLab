from fractions import Fraction as F
from pathlib import Path
import hashlib
import json

EDGES = ((0, 1), (0, 2), (1, 3), (2, 3))
A = [[F(0) for j in range(4)] for i in range(4)]
for i, j in EDGES:
    A[i][i] += 1
    A[j][j] += 1
    A[i][j] -= 1
    A[j][i] -= 1
for i in range(4):
    A[i][i] += F(4, 21)

def mv(matrix, vector):
    return [sum((x * y for x, y in zip(row, vector)), F(0)) for row in matrix]

def solve(rhs):
    b = [A[i][:] + [F(rhs[i])] for i in range(4)]
    for k in range(4):
        pivot = next(i for i in range(k, 4) if b[i][k])
        b[k], b[pivot] = b[pivot], b[k]
        divisor = b[k][k]
        b[k] = [v / divisor for v in b[k]]
        for i in range(4):
            if i != k:
                factor = b[i][k]
                b[i] = [x - factor * y for x, y in zip(b[i], b[k])]
    return [row[-1] for row in b]

def norm_inf(v):
    return max(map(abs, v))

BASIS = ((1, 1, 1, 1), (1, 1, -1, -1), (1, -1, 1, -1), (1, -1, -1, 1))
GAIN = (F(21, 4), F(21, 46), F(21, 46), F(21, 88))

def modal_solution(r):
    coefficients = [sum((F(x) * y for x, y in zip(r, v)), F(0)) / 4 for v in BASIS]
    e = [sum((GAIN[k] * coefficients[k] * BASIS[k][i] for k in range(4)), F(0)) for i in range(4)]
    bound = sum((g * abs(c) for g, c in zip(GAIN, coefficients)), F(0))
    return e, bound

for k, v in enumerate(BASIS):
    assert mv(A, v) == [F(x) / GAIN[k] for x in v]
    for j, w in enumerate(BASIS):
        assert sum(x * y for x, y in zip(v, w)) == (4 if j == k else 0)

unit_vectors = [[F(int(i == j)) for i in range(4)] for j in range(4)]
inverse_columns = [solve(u) for u in unit_vectors]
for u, column in zip(unit_vectors, inverse_columns):
    assert mv(A, column) == u
    assert all(x >= 0 for x in column)
    assert modal_solution(u)[0] == column

one_solution = solve(BASIS[0])
baseline_constant = norm_inf(one_solution)
assert one_solution == [F(21, 4)] * 4
assert all(sum((column[i] for column in inverse_columns), F(0)) == F(21, 4) for i in range(4))

records = []
for name, k in (("constant", 0), ("stripes", 1), ("checkerboard", 3)):
    r = [F(x) for x in BASIS[k]]
    e = solve(r)
    modal_e, modal_bound = modal_solution(r)
    exact_norm = norm_inf(e)
    baseline = baseline_constant * norm_inf(r)
    assert mv(A, e) == r
    assert e == [GAIN[k] * x for x in r] == modal_e
    assert exact_norm == GAIN[k] == modal_bound
    assert exact_norm <= baseline
    records.append({"name": name, "residual": [int(x) for x in r], "solution": [str(x) for x in e], "error_inf": str(exact_norm), "baseline": str(baseline), "modal_bound": str(modal_bound), "verified": True})

workspace = Path(__file__).resolve().parents[1]
proof_path = workspace / "mode_proof.md"
result = {"arithmetic": "fractions.Fraction", "method": "Gauss-Jordan elimination plus exact substitution and modal checks", "modes": records, "basis_verified": True, "inverse_nonnegative_verified": True, "modal_inverse_verified_on_coordinate_basis": True, "all_checks_passed": True, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "proof_sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(), "scope": "Fixed four-cell matrix only; computation is not independent proof review"}
archive = workspace / "mode_results.json"
archive.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
assert json.loads(archive.read_text(encoding="utf-8")) == result
print(json.dumps({"modes": [{key: record[key] for key in ("name", "error_inf", "baseline", "modal_bound", "verified")} for record in records], "all_checks_passed": True, "archive": "workspace/mode_results.json"}, separators=(",", ":")))
