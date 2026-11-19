"""Recompute frozen numerical experiments in a new copy, without model calls.

Default: one n=24 repetition. --full: all nine frozen repetitions.
The original artifacts are preserved; timing values are not expected to match.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / 'thermal/home/projects/thermal-rom/workspace'
FINAL = WORKSPACE / 'results/04_final_v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_hashes():
    return {p.relative_to(WORKSPACE).as_posix(): digest(p)
            for p in WORKSPACE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def compare(original, replay):
    checks, largest = 0, 0.0
    for method, source in original['methods'].items():
        candidate = replay['methods'][method]
        if len(source['cases']) != len(candidate['cases']):
            raise ValueError('Query count mismatch: ' + method)
        for expected, actual in zip(source['cases'], candidate['cases']):
            if expected['h'] != actual['h'] or expected['index'] != actual['index']:
                raise ValueError('Parameter/order mismatch')
            for key in ('field_linf', 'hotspot', 'relative_l2'):
                difference = abs(expected['error'][key] - actual['error'][key])
                largest = max(largest, difference)
                checks += 1
                if difference > 1e-9:
                    raise ValueError('Numerical discrepancy above 1e-9: ' + method + '/' + key)
            if method == 'adaptive':
                for key in ('trigger', 'rank_before', 'rank_after', 'status', 'false_alarm', 'missed_failure'):
                    checks += 1
                    if expected[key] != actual[key]:
                        raise ValueError('Adaptive trajectory mismatch: ' + key)
    if original['counts_actual_executed'] != replay['counts_actual_executed']:
        raise ValueError('Actual solve counts mismatch')
    return {'checks': checks, 'largest_error_statistic_difference': largest,
            'timing_compared_for_equality': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if not (FINAL / 'summary.json').is_file():
        raise RuntimeError('Complete frozen reference results are missing.')
    original_summary = json.loads((FINAL / 'summary.json').read_text(encoding='utf-8'))
    if original_summary['status'] != 'complete':
        raise RuntimeError('Reference experiment is not complete.')
    before = original_hashes()
    destination = ROOT / 'thermal/reproductions' / (datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    copied = destination / 'project/workspace'
    shutil.copytree(WORKSPACE, copied, ignore=shutil.ignore_patterns('__pycache__', '04_final_v1'))
    replay_final = copied / 'results/04_final_v1'
    replay_final.mkdir()
    for name in ('frozen_configuration.json', 'freeze_completed.json', 'test_parameters.npy', 'test_parameters.json'):
        shutil.copy2(FINAL / name, replay_final / name)
    shutil.copytree(FINAL / 'sources', replay_final / 'sources')
    driver = copied / 'experiments/final_benchmark_driver.py'
    tasks = [(n, rep) for n in (24, 48, 96) for rep in (1, 2, 3)] if args.full else [(24, 1)]
    report = {'origin': 'External offline reproduction, not a new Moonshine research turn',
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'model_calls': 0,
              'full': args.full, 'new_test_parameters_generated': False,
              'parameter_array_sha256': json.loads((FINAL/'freeze_completed.json').read_text())['parameter_array_sha256'],
              'runs': [], 'status': 'running'}
    try:
        for n, rep in tasks:
            print(f'Recomputing n={n}, repetition={rep}; no model request.', flush=True)
            command = [sys.executable, '-u', '-B', '-X', 'utf8', str(driver), 'run', '--n', str(n), '--repeat', str(rep)]
            result = subprocess.run(command, cwd=destination/'project', capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=180)
            prefix = destination / f'n{n}-repeat{rep}'
            prefix.with_suffix('.stdout.txt').write_text(result.stdout, encoding='utf-8')
            prefix.with_suffix('.stderr.txt').write_text(result.stderr, encoding='utf-8')
            if result.returncode:
                raise RuntimeError(f'Reproduction failed with code {result.returncode}; logs: {destination}')
            path = Path(f'n{n}/repeat{rep:02d}/result.json')
            expected = json.loads((FINAL/path).read_text(encoding='utf-8'))
            actual = json.loads((replay_final/path).read_text(encoding='utf-8'))
            if not actual['execution_complete'] or not actual['validation_passed']:
                raise RuntimeError('Recomputed quality checks did not pass.')
            report['runs'].append({'n':n, 'repeat':rep, 'returncode':result.returncode,
                                   **compare(expected, actual)})
        if args.full:
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(driver), 'summarize'],
                                    cwd=destination/'project', capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=60)
            (destination/'summary.stdout.txt').write_text(result.stdout, encoding='utf-8')
            (destination/'summary.stderr.txt').write_text(result.stderr, encoding='utf-8')
            if result.returncode:
                raise RuntimeError('Reproduction summary failed.')
        report['status'] = 'passed'
    except BaseException as exc:
        report['status'], report['error'] = 'failed', repr(exc)
        raise
    finally:
        report['original_workspace_unchanged'] = before == original_hashes()
        report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        (destination/'reproduction_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if not report['original_workspace_unchanged']:
            raise RuntimeError('Original workspace changed while reproducing; inspect the saved report.')
    print(json.dumps({'status':report['status'], 'model_calls':0, 'runs':len(tasks),
                      'report':str(destination/'reproduction_report.json')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
