"""Independent deterministic checks plus a stdlib execution/report supervisor.
Run from project root: python workspace/experiments/check_thermal_solver.py
The supervisor records the actual worker return code; Moonshine records its own process result.
"""
import sys
import json
import time
import platform
import traceback
import subprocess
import importlib
import hashlib
from pathlib import Path
from datetime import datetime, timezone


def worker():
    result = {'project': 'thermal-rom', 'stage': '01_model',
              'provenance': 'Agent-generated scripts executed by Moonshine run_python_script',
              'external_independent_review': False, 'verification_status': 'pending',
              'python': {'version': sys.version, 'executable': sys.executable, 'platform': platform.platform()},
              'dependencies': {}, 'checks': [], 'cases': [], 'full_solve_count': 0,
              'source_rule': 'rectangle/control-volume overlap area integration; no centre sampling',
              'main_grid_n': 24, 'auxiliary_grids': {'1': 'hand-computable scalar system', '2': 'hand matrix and source vector'},
              'parameter_order': ['left', 'right', 'bottom', 'top'],
              'tolerances': {'symmetry_abs': 1e-14, 'analytic_abs': 1e-12, 'source_total_abs': 1e-13,
                             'relative_residual_l2': 1e-10, 'relative_balance': 1e-10,
                             'temperature_abs': 1e-10},
              'normalization': {'residual': '||A*T-b||2/||b||2 when ||b||2>0, otherwise absolute ||A*T-b||2',
                                'balance': '|outward_heat-source_total|/|source_total| when nonzero; otherwise absolute difference'},
              'limitations': ['Finite deterministic cases are not a parameter-domain numerical certificate.',
                              'SPD follows from the energy argument; small Cholesky is only an implementation check.',
                              'No continuum error bound, grid convergence order, POD, or speedup claim.',
                              'Timings are single-run observations, include timer noise, and are not a benchmark.']}
    started = time.perf_counter()
    modules = {}
    for name in ('numpy', 'scipy'):
        try:
            modules[name] = importlib.import_module(name)
            result['dependencies'][name] = {'available': True, 'version': modules[name].__version__}
        except Exception as exc:
            result['dependencies'][name] = {'available': False, 'error': repr(exc)}
    result['dependency_probe_seconds'] = time.perf_counter() - started
    if len(modules) != 2:
        result.update(status='incomplete_dependency', next_step='Supply dependencies externally or implement a separately labelled tiny stdlib dense solver; no packages installed and no substitute experiment claimed.')
        return result, 2
    np = modules['numpy']
    try:
        from thermal_solver import assemble, solve, boundary_heat
        def check(name, value, tolerance):
            value = float(value)
            passed = bool(np.isfinite(value) and value <= tolerance)
            result['checks'].append({'name': name, 'value': value if np.isfinite(value) else None,
                                     'tolerance': tolerance, 'passed': passed})
        def solve_counted(*args, **kwargs):
            result['full_solve_count'] += 1
            return solve(*args, **kwargs)
        validation_start = time.perf_counter()
        # Hand-derived N=1: each face has area 1, distance 1/2, h=2, g=1.
        # A=[4], b=0.04+2*0.04=0.12, hence T=0.03.
        T, A, b, meta, timing = solve_counted(1, (2, 2, 2, 2))
        check('n1_matrix_expected_4', abs(A[0, 0] - 4.0), 1e-12)
        check('n1_source_expected_0.12', abs(b[0] - 0.12), 1e-13)
        check('n1_temperature_expected_0.03', abs(T[0] - 0.03), 1e-12)
        result['n1'] = {'matrix': float(A[0, 0]), 'rhs': float(b[0]), 'temperature': float(T[0]), 'timing': timing}
        # Hand-derived N=2 boundary conductances: 2/5, 2/3, 6/7, 1.
        # Row ordering: bottom-left, bottom-right, top-left, top-right.
        A2, b2, _ = assemble(2, (1, 2, 3, 4))
        expected_A = np.array([[2+2/5+6/7, -1, -1, 0],
                               [-1, 2+2/3+6/7, 0, -1],
                               [-1, 0, 2+2/5+1, -1],
                               [0, -1, -1, 2+2/3+1]], dtype=float)
        expected_b = np.array([0.04, 0.0, 0.0, 0.08])
        check('n2_hand_matrix_max_abs_error', np.max(np.abs(A2.toarray()-expected_A)), 1e-12)
        check('n2_hand_source_max_abs_error', np.max(np.abs(b2-expected_b)), 1e-13)
        L = np.linalg.cholesky(A2.toarray())
        check('n2_cholesky_reconstruction_max_abs', np.max(np.abs(L @ L.T-A2.toarray())), 1e-12)
        result['n2_cholesky_min_diagonal'] = float(np.min(np.diag(L)))
        parameters = [(0.2, 0.2, 0.2, 0.2), (1, 1, 1, 1), (5, 5, 5, 5), (0.2, 5, 1, 2)]
        for case_id, h in enumerate(parameters):
            T, A, b, meta, timing = solve_counted(24, h)
            check_start = time.perf_counter()
            prefix = 'n24_case_' + str(case_id)
            difference = A-A.T
            symmetry = float(np.max(np.abs(difference.data))) if difference.nnz else 0.0
            residual_abs = float(np.linalg.norm(A @ T-b))
            rhs_norm = float(np.linalg.norm(b))
            residual = residual_abs/rhs_norm if rhs_norm > 0 else residual_abs
            # Independent flux calculation directly from edge temperatures and known geometry.
            field = T.reshape(24, 24)
            edge_values = (field[:, 0], field[:, -1], field[0, :], field[-1, :])
            flux = np.array([np.sum(values) / (24.0/float(hs) + 0.5)
                             for values, hs in zip(edge_values, h)])
            total_source = float(np.sum(b))
            balance_abs = abs(float(np.sum(flux))-total_source)
            balance = balance_abs/abs(total_source) if total_source else balance_abs
            check(prefix+'_symmetry', symmetry, 1e-14)
            check(prefix+'_source_total_expected_0.12', abs(total_source-0.12), 1e-13)
            check(prefix+'_relative_residual_l2', residual, 1e-10)
            check(prefix+'_negative_temperature_violation', max(0.0, -float(np.min(T))), 1e-10)
            check(prefix+'_relative_heat_balance', balance, 1e-10)
            check(prefix+'_flux_api_against_independent_formula', np.max(np.abs(boundary_heat(T, meta)-flux)), 1e-12)
            result['cases'].append({'n': 24, 'h': list(h), 'temperature_min': float(np.min(T)),
                                    'temperature_max': float(np.max(T)), 'source_total': total_source,
                                    'boundary_heat_by_side': flux.tolist(), 'relative_heat_balance': balance,
                                    'residual_l2_absolute': residual_abs, 'relative_residual_l2': residual,
                                    'symmetry_max_abs': symmetry, 'timing': timing,
                                    'indicator_and_check_seconds': time.perf_counter()-check_start})
        for ambient in (0.0, 3.0):
            T, A, b, meta, timing = solve_counted(24, (0.2, 5, 1, 2), source='zero', ambient=ambient)
            error = float(np.max(np.abs(T-ambient)))
            check('zero_source_equilibrium_ambient_'+str(ambient), error, 1e-10)
            residual_abs = float(np.linalg.norm(A @ T-b))
            bnorm = float(np.linalg.norm(b))
            check('zero_source_residual_ambient_'+str(ambient), residual_abs/bnorm if bnorm else residual_abs, 1e-10)
            result.setdefault('equilibrium_cases', []).append({'ambient': ambient, 'max_abs_error': error, 'timing': timing})
        result['validation_seconds_including_assembly_solve_checks'] = time.perf_counter()-validation_start
        result['status'] = 'checks_passed_pending_review' if all(c['passed'] for c in result['checks']) else 'checks_failed'
        return result, 0 if result['status'] == 'checks_passed_pending_review' else 1
    except Exception:
        result['status'] = 'execution_failed'
        result['traceback'] = traceback.format_exc()
        return result, 3


def supervise():
    script = Path(__file__).resolve()
    project = script.parents[2]
    output_dir = project / 'workspace' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    try:
        completed = subprocess.run([sys.executable, str(script), '--worker'], cwd=str(project),
                                   capture_output=True, text=True, encoding='utf-8', timeout=45)
        try:
            result = json.loads(completed.stdout)
        except Exception:
            result = {'project': 'thermal-rom', 'status': 'worker_output_invalid', 'worker_stdout': completed.stdout}
        result['worker_exit_code'] = completed.returncode
        result['worker_stderr'] = completed.stderr
        code = completed.returncode if completed.returncode != 0 else (0 if result.get('status') == 'checks_passed_pending_review' else 4)
    except subprocess.TimeoutExpired as exc:
        result = {'project': 'thermal-rom', 'status': 'incomplete_timeout', 'worker_exit_code': None,
                  'error': str(exc), 'timeout_seconds': 45}
        code = 124
    result['run_timestamp_utc'] = stamp
    result['supervised_wall_seconds'] = time.perf_counter()-started
    result['exit_code'] = code
    result['exit_code_semantics'] = 'Actual worker return code recorded separately; supervisor requests this exit code. Confirm outer process exit in Moonshine tool evidence.'
    result['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (script, script.with_name('thermal_solver.py'))}
    destination = output_dir / '01_model.json'
    if destination.exists():
        backup = output_dir / ('01_model.before_' + stamp + '.json')
        backup.write_bytes(destination.read_bytes())
        result['previous_result_backup'] = str(backup.relative_to(project))
    serialized = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
    destination.write_text(serialized + '\n', encoding='utf-8')
    (output_dir / ('01_model.run_' + stamp + '.json')).write_text(serialized + '\n', encoding='utf-8')
    print(serialized)
    return code


if __name__ == '__main__':
    if '--worker' in sys.argv:
        payload, exit_code = worker()
        print(json.dumps(payload, ensure_ascii=True, allow_nan=False))
        raise SystemExit(exit_code)
    raise SystemExit(supervise())
