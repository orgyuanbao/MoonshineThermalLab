#!/usr/bin/env python3
"""Deterministic exact-arithmetic checker; Python standard library only.
Direct solves occur only in offline_precompute and reference checks.
The online estimator uses stored responses, block maxima and arithmetic.
"""
from fractions import Fraction as F
from itertools import product
import json


def matrix(n, h):
    delta = F(1, n)
    beta = [delta / (1 / t + delta / 2) for t in h]
    N = n * n
    A = [[F(0) for _ in range(N)] for _ in range(N)]
    for y in range(n):
        for x in range(n):
            i = y * n + x
            for yy, xx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                if 0 <= yy < n and 0 <= xx < n:
                    A[i][yy*n+xx] = F(-1)
                    A[i][i] += 1
            # Independent tests count all four boundary faces when n=1.
            for incident, b in zip((x == 0, x == n-1, y == 0, y == n-1), beta):
                if incident:
                    A[i][i] += b
    return A


def solve_many(A, B):
    """Exact Gauss-Jordan solve for multiple right-hand sides."""
    N, K = len(A), len(B[0])
    M = [list(a) + list(b) for a, b in zip(A, B)]
    for k in range(N):
        pivot = next(i for i in range(k, N) if M[i][k])
        M[k], M[pivot] = M[pivot], M[k]
        d = M[k][k]
        M[k] = [v / d for v in M[k]]
        for i in range(N):
            if i != k and M[i][k]:
                c = M[i][k]
                M[i] = [a - c*b for a, b in zip(M[i], M[k])]
    return [row[N:N+K] for row in M]


def multiply(A, B):
    return [[sum((A[i][j] * B[j][k] for j in range(len(B))), F(0))
             for k in range(len(B[0]))] for i in range(len(A))]


def blocks_for(n):
    cut = (n + 1) // 2
    groups = {}
    for y in range(n):
        for x in range(n):
            groups.setdefault((y >= cut, x >= cut), []).append(y*n+x)
    return list(groups.values())


def offline_precompute(n):
    blocks = blocks_for(n)
    N = n*n
    assert sorted(i for b in blocks for i in b) == list(range(N))
    H = [[F(int(i in b)) for b in blocks] for i in range(N)]
    A0 = matrix(n, (F(1, 5),)*4)
    W = solve_many(A0, H)
    assert multiply(A0, W) == H
    assert all(v >= 0 for row in W for v in row)
    z = [sum(row, F(0)) for row in W]
    assert multiply(A0, [[v] for v in z]) == [[F(1)] for _ in range(N)]
    return blocks, W, z


def online_bound(r, blocks, W, z):
    """No matrix assembly, factorization, or solve is used here."""
    ap = [max(max(r[i], F(0)) for i in b) for b in blocks]
    am = [max(max(-r[i], F(0)) for i in b) for b in blocks]
    aa = [max(abs(r[i]) for i in b) for b in blocks]
    def response(coeff):
        return [sum((v*c for v, c in zip(row, coeff)), F(0)) for row in W]
    p, q, unsigned = response(ap), response(am), response(aa)
    return {'upper': p, 'lower': [-v for v in q],
            'bound': max(max(p), max(q)),
            'unsigned_bound': max(unsigned),
            'baseline': max(abs(v) for v in r) * max(z)}


def residual_cases(n):
    N = n*n
    cut = (n+1)//2
    return {
        'zero': [F(0)]*N,
        'constant_positive': [F(1)]*N,
        'constant_negative': [F(-1)]*N,
        'row_sign_split': [F(1 if y < cut else -1) for y in range(n) for x in range(n)],
        'checkerboard': [F((-1)**(x+y)) for y in range(n) for x in range(n)],
        'corner_spike': [F(int(i == 0)) for i in range(N)],
        'center_spike': [F(int(i == (n//2)*n+n//2)) for i in range(N)],
        'deterministic_mixed': [F((7*i+3) % 11 - 5, 5) for i in range(N)],
    }


def number(x):
    return {'exact': str(x), 'decimal': float(x)}


def case_record(n, name, h, r, result, actual):
    base = result['baseline']
    return {'n': n, 'residual': name, 'h_left_right_top_bottom': [str(t) for t in h],
            'residual_values': [str(t) for t in r],
            'actual_error': number(actual), 'candidate_bound': number(result['bound']),
            'unsigned_spatial_bound': number(result['unsigned_bound']),
            'uniform_baseline': number(base),
            'candidate_over_baseline': number(result['bound']/base) if base else None,
            'covered': actual <= result['bound'],
            'strict_gain': result['bound'] < base}


def main():
    grids = (1, 2, 3, 4)
    values = (F(1, 5), F(1), F(5))
    hmin = (values[0],)*4
    checks = {'partition_coverage': True, 'offline_response_equations': True,
              'componentwise_coverage': True, 'norm_coverage': True,
              'candidate_le_unsigned_le_baseline': True,
              'reference_equations_exact': True, 'n1_four_faces': True}
    examples, grid_records = {}, []
    total, strict_count = 0, 0
    min_slack, max_ratio = None, F(0)
    for n in grids:
        blocks, W, z = offline_precompute(n)
        cases = residual_cases(n)
        names = list(cases)
        estimates = {name: online_bound(r, blocks, W, z) for name, r in cases.items()}
        R = [[cases[name][i] for name in names] for i in range(n*n)]
        count = 0
        for h in product(values, repeat=4):
            A = matrix(n, h)
            if n == 1:
                assert A[0][0] == sum((F(1)/(1/t+F(1, 2)) for t in h), F(0))
            E = solve_many(A, R)  # Reference only; never called by online_bound.
            assert multiply(A, E) == R
            for k, name in enumerate(names):
                r, est = cases[name], estimates[name]
                e = [row[k] for row in E]
                actual = max(abs(v) for v in e)
                assert all(lo <= v <= hi for lo, v, hi in zip(est['lower'], e, est['upper']))
                assert actual <= est['bound'] <= est['unsigned_bound'] <= est['baseline']
                slack = est['bound'] - actual
                min_slack = slack if min_slack is None else min(min_slack, slack)
                if est['baseline']:
                    max_ratio = max(max_ratio, est['bound']/est['baseline'])
                strict_count += int(est['bound'] < est['baseline'])
                count += 1
                if h == hmin and name in ('constant_positive', 'constant_negative', 'zero'):
                    assert actual == est['bound'] == est['baseline']
                if n == 2 and h == hmin and name == 'row_sign_split':
                    assert actual == F(21, 46)
                    assert est['bound'] == F(525, 184)
                    assert est['baseline'] == F(21, 4)
                    assert est['bound'] < est['unsigned_bound']
                    examples['strict_sign_gain'] = case_record(n, name, h, r, est, actual)
                if n == 2 and h == hmin and name == 'constant_positive':
                    examples['equality'] = case_record(n, name, h, r, est, actual)
                if n == 1 and h == hmin and name == 'constant_positive':
                    examples['n1_equality'] = case_record(n, name, h, r, est, actual)
                if n == 4 and h == hmin and name in ('corner_spike', 'center_spike', 'checkerboard'):
                    examples[name] = case_record(n, name, h, r, est, actual)
        total += count
        grid_records.append({'n': n, 'blocks': blocks, 'parameter_cases': len(values)**4,
                             'residual_cases': len(cases), 'tested_pairs': count})
    checks['strict_tighter_example'] = examples['strict_sign_gain']['strict_gain']
    eq = examples['equality']
    checks['equality_case'] = eq['actual_error']['exact'] == eq['candidate_bound']['exact'] == eq['uniform_baseline']['exact']
    assert all(checks.values())
    print(json.dumps({'arithmetic': 'Exact fractions; decimal fields are display only.',
          'numerical_tolerance': 0, 'parameter_values': [str(v) for v in values],
          'parameter_order': ['left', 'right', 'top', 'bottom'],
          'grids': grid_records, 'total_tested_pairs': total,
          'strict_gain_pairs': strict_count, 'minimum_coverage_slack': number(min_slack),
          'maximum_candidate_over_baseline': number(max_ratio),
          'offline_solve_batches': len(grids),
          'reference_solve_batches': len(grids)*len(values)**4,
          'online_solve_calls': 0, 'checks': checks, 'examples': examples,
          'scope': 'Finite exact checks corroborate the continuous-parameter mathematical proof; no novelty or timing claim.'},
          indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
