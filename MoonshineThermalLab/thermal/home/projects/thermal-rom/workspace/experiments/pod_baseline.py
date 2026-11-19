"""Fixed POD development baseline. No final test data; no dependency installation."""
import sys, json, time, hashlib, shutil, traceback
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'workspace'
RESULTS = WORK / 'results'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
COUNTS = {'fom_calls': 0, 'rom_calls': 0}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def preserve(path):
    path = Path(path)
    if path.exists():
        shutil.copy2(path, path.with_name(path.stem + '.before_' + STAMP + path.suffix))

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    preserve(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    with path.open(encoding='utf-8') as stream:
        json.load(stream)

def ratio(a, b):
    # A null value means undefined positive/zero, never a hidden infinity.
    return float(a / b) if b > 0 else (0.0 if a == 0 else None)

def residual_metrics(A, b, u):
    r = b - A @ u
    return {'residual_linf': float(np.max(np.abs(r))),
            'residual_l2': float(np.linalg.norm(r)),
            'relative_residual_l2': ratio(np.linalg.norm(r), np.linalg.norm(b))}

def errors(u, ref):
    difference = u - ref
    return {'hotspot_error': float(abs(np.max(u) - np.max(ref))),
            'field_linf_error': float(np.max(np.abs(difference))),
            'relative_l2_error': ratio(np.linalg.norm(difference), np.linalg.norm(ref))}

def fom(h):
    COUNTS['fom_calls'] += 1
    u, A, b, meta, timing = solve(24, h)
    t = time.perf_counter()
    metrics = residual_metrics(A, b, u)
    timing['residual_evaluation_seconds'] = time.perf_counter() - t
    return u, metrics, timing

def rom(h, V):
    COUNTS['rom_calls'] += 1
    timing = {}
    t0 = time.perf_counter()
    A, b, _ = assemble(24, h)
    t1 = time.perf_counter()
    Ar = V.T @ (A @ V)
    br = V.T @ b
    t2 = time.perf_counter()
    a = np.linalg.solve(Ar, br)
    t3 = time.perf_counter()
    u = V @ a
    t4 = time.perf_counter()
    metrics = residual_metrics(A, b, u)
    t5 = time.perf_counter()
    timing.update(assembly_seconds=t1-t0, projection_seconds=t2-t1,
                  reduced_solve_seconds=t3-t2, reconstruction_seconds=t4-t3,
                  residual_evaluation_seconds=t5-t4, online_total_seconds=t5-t0)
    tc = time.perf_counter()
    metrics['projected_relative_residual'] = ratio(np.linalg.norm(Ar @ a-br), np.linalg.norm(br))
    metrics['galerkin_relative_residual'] = ratio(np.linalg.norm(V.T @ (b-A @ u)), np.linalg.norm(br))
    metrics['projected_symmetry_maxabs'] = float(np.max(np.abs(Ar-Ar.T)))
    metrics['projected_shape'] = list(Ar.shape)
    timing['verification_seconds'] = time.perf_counter()-tc
    return u, metrics, timing

def main():
    global np, assemble, solve
    started = time.perf_counter()
    import numpy as np
    import scipy
    from thermal_solver import assemble, solve
    RESULTS.mkdir(parents=True, exist_ok=True)
    run_dir = RESULTS / ('02_run_' + STAMP)
    run_dir.mkdir(exist_ok=False)
    solver = Path(__file__).with_name('thermal_solver.py')
    expected_hash = '67f3b1bd3adfd34b28c6c449a782438be2e1104a444c08c46e8fb66589b63ab6'
    assert digest(solver) == expected_hash, 'Solver differs from reviewed version'
    with (RESULTS / '01_model.json').open(encoding='utf-8') as stream:
        prior = json.load(stream)
    assert len(prior['checks']) == 34 and all(c['passed'] for c in prior['checks'])
    prior_notes = (WORK / '01_model_notes.md').read_text(encoding='utf-8')
    followup = (WORK / '01_review_followup.md').read_text(encoding='utf-8')
    assert 'overall_verdict=correct' in followup and '07:17:32' in followup
    protocol_files = sorted(ROOT.rglob('stage2_protocol.txt'))
    protocol_sources = []
    for p in protocol_files:
        protocol_sources.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(p), 'text': p.read_text(encoding='utf-8-sig')})
    config = {'project': 'thermal-rom', 'n': 24, 'h_order': ['left','right','bottom','top'],
              'h_bounds': [0.2,5.0], 'source_rule': 'rectangle-cell overlap area integration',
              'sources': [{'bounds':[0.2,0.4,0.2,0.4],'strength':1}, {'bounds':[0.6,0.8,0.6,0.8],'strength':2}],
              'ambient': 0, 'k': 1, 'sampling': 'exp(default_rng(seed).uniform(log(0.2),log(5),size=(count,4)))',
              'train_seed': 20261025, 'tune_seed': 20261026, 'train_count':24, 'tune_count':12,
              'candidate_ranks':[1,2,4,8,12,24], 'tau':0.001, 'center_snapshots':False,
              'rank_tolerance':'max(S.shape)*float64_eps*s[0]',
              'selection':'smallest legal candidate with maximum tuning field Linf error <= tau',
              'no_qualifying_rank':'selected_rank=null; use largest legal rank only for development diagnosis',
              'protocol_authority':'coordinator user message before experiment', 'protocol_files_found':protocol_sources,
              'final_test_generated':False, 'solver_sha256':expected_hash,
              'timing_policy':'Single pass perf_counter; FOM references reused across ranks, each ROM independently assembles; no online matrix cache; no basis updates. Timers include full-dimensional assembly, projection, reconstruction and residual. Verification, evaluation and persistence are separate development overhead.'}
    write_json(run_dir / 'config.json', config)
    train = np.exp(np.random.default_rng(20261025).uniform(np.log(0.2), np.log(5.0), size=(24,4)))
    tune = np.exp(np.random.default_rng(20261026).uniform(np.log(0.2), np.log(5.0), size=(12,4)))
    assert not any(np.array_equal(a,b) for a in train for b in tune)
    for label, mu in [('train',train),('tune',tune)]:
        write_json(run_dir / (label+'_parameters.json'), {'role':label+'_development', 'seed':config[label+'_seed'],
                   'parameters':mu.tolist(), 'component_min':mu.min(axis=0).tolist(),
                   'component_max':mu.max(axis=0).tolist(), 'array_sha256':hashlib.sha256(mu.tobytes()).hexdigest()})
    checks = []
    def check(name, value, tolerance):
        value = float(value)
        checks.append({'name':name,'value':value,'tolerance':tolerance,
                       'passed':bool(np.isfinite(value) and value <= tolerance)})
    foms, fom_records = {}, []
    snapshot_started = time.perf_counter()
    for label, parameters in [('train',train),('tune',tune)]:
        values = []
        for index, h in enumerate(parameters):
            u, metrics, timing = fom(h)
            check(label+'_fom_residual_'+str(index), metrics['relative_residual_l2'], 1e-10)
            check(label+'_fom_nonfinite_'+str(index), np.count_nonzero(~np.isfinite(u)), 0)
            values.append(u)
            fom_records.append({'dataset':label, 'index':index, 'h':h.tolist(), **metrics, 'timing':timing})
        foms[label] = np.column_stack(values)
        if label == 'train':
            snapshot_seconds = time.perf_counter()-snapshot_started
    t = time.perf_counter()
    U, singular, Wt = np.linalg.svd(foms['train'], full_matrices=False)
    svd_seconds = time.perf_counter()-t
    rank_tol = max(foms['train'].shape)*np.finfo(float).eps*singular[0]
    numerical_rank = int(np.count_nonzero(singular > rank_tol))
    candidates = [r for r in config['candidate_ranks'] if r <= numerical_rank]
    assert candidates, 'No legal candidate ranks'
    check('snapshot_svd_relative_reconstruction', np.linalg.norm((U*singular) @ Wt-foms['train'])/np.linalg.norm(foms['train']), 1e-12)
    check('training_tuning_overlap_count', sum(np.array_equal(a,b) for a in train for b in tune), 0)
    rows, curves, arrays = [], [], {}
    for rank in candidates:
        V = U[:,:rank]
        orth = float(np.linalg.norm(V.T @ V-np.eye(rank), ord=np.inf))
        check('orthogonality_rank_'+str(rank), orth, 1e-12)
        check('rank_limit_'+str(rank), max(0,rank-min(24,576,numerical_rank)), 0)
        rank_rows = []
        for label, parameters in [('train',train),('tune',tune)]:
            predictions = []
            for index, h in enumerate(parameters):
                u, metrics, timing = rom(h,V)
                tc = time.perf_counter()
                err = errors(u,foms[label][:,index])
                timing['reference_error_evaluation_seconds'] = time.perf_counter()-tc
                row = {'dataset':label,'index':index,'h':h.tolist(),'rank':rank, **metrics, **err, 'timing':timing}
                rank_rows.append(row)
                predictions.append(u)
            arrays['rom_'+label+'_r'+str(rank)] = np.column_stack(predictions)
        rows.extend(rank_rows)
        for label in ['train','tune']:
            subset = [r for r in rank_rows if r['dataset']==label]
            curves.append({'dataset':label,'rank':rank,'orthogonality_inf':orth,
                           **{'max_'+key:max(r[key] for r in subset) for key in ['hotspot_error','field_linf_error','relative_l2_error','relative_residual_l2']},
                           'online_total_seconds':sum(r['timing']['online_total_seconds'] for r in subset)})
        check('projected_shape_rank_'+str(rank), sum(r['projected_shape'] != [rank,rank] for r in rank_rows), 0)
        check('projected_residual_rank_'+str(rank), max(r['projected_relative_residual'] for r in rank_rows), 1e-10)
        check('galerkin_residual_rank_'+str(rank), max(r['galerkin_relative_residual'] for r in rank_rows), 1e-10)
        check('projected_symmetry_rank_'+str(rank), max(r['projected_symmetry_maxabs'] for r in rank_rows), 1e-12)
        check('rom_nonfinite_rank_'+str(rank), sum(np.count_nonzero(~np.isfinite(arrays['rom_'+label+'_r'+str(rank)])) for label in ['train','tune']), 0)
    acceptable = [c['rank'] for c in curves if c['dataset']=='tune' and c['max_field_linf_error'] <= config['tau']]
    selected = min(acceptable) if acceptable else None
    diagnosis_rank = selected if selected is not None else max(candidates)
    arrays.update(train_parameters=train,tune_parameters=tune,train_fom=foms['train'],tune_fom=foms['tune'],
                  U=U,singular_values=singular,V=U[:,:selected] if selected is not None else np.empty((576,0)),
                  V_diagnostic=U[:,:diagnosis_rank],candidate_ranks=np.array(candidates),
                  selected_rank=np.array(-1 if selected is None else selected),diagnostic_rank=np.array(diagnosis_rank))
    tp = time.perf_counter()
    np.savez_compressed(run_dir / 'basis.npz', **arrays)
    persistence_seconds = time.perf_counter()-tp
    with np.load(run_dir / 'basis.npz',allow_pickle=False) as saved:
        check('saved_training_exact_match', np.max(np.abs(saved['train_fom']-foms['train'])), 0)
        check('saved_basis_exact_match', np.max(np.abs(saved['U']-U)), 0)
    check('fom_call_count', abs(COUNTS['fom_calls']-36), 0)
    check('rom_call_count', abs(COUNTS['rom_calls']-36*len(candidates)), 0)
    passed = all(c['passed'] for c in checks)
    costs = {'offline_snapshot_wall_seconds':snapshot_seconds, 'offline_svd_seconds':svd_seconds,
             'npz_persistence_seconds':persistence_seconds, 'basis_update_seconds':0.0, 'basis_update_count':0,
             'fom_assembly_seconds':sum(r['timing']['assembly_seconds'] for r in fom_records),
             'fom_solve_seconds':sum(r['timing']['linear_solve_seconds'] for r in fom_records),
             'fom_residual_seconds':sum(r['timing']['residual_evaluation_seconds'] for r in fom_records),
             'all_candidates_online_seconds':sum(r['timing']['online_total_seconds'] for r in rows)}
    tune_fom_cost = sum(r['timing']['assembly_and_solve_seconds'] for r in fom_records if r['dataset']=='tune')
    diagnostic_online_cost = sum(r['timing']['online_total_seconds'] for r in rows if r['dataset']=='tune' and r['rank']==diagnosis_rank)
    costs.update(tuning_fom_assembly_solve_seconds=tune_fom_cost, diagnostic_tuning_online_seconds=diagnostic_online_cost,
                 observed_fom_over_rom_online_ratio=ratio(tune_fom_cost,diagnostic_online_cost),
                 offline_plus_diagnostic_tuning_seconds=snapshot_seconds+svd_seconds+diagnostic_online_cost)
    report = {'project':'thermal-rom','run_timestamp_utc':STAMP,'status':'checks_passed_pending_review' if passed else 'checks_failed',
              'exit_code':0 if passed else 1,'verification_status':'pending','config':config,
              'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__},
              'prerequisites':{'prior_checks':34,'solver_sha256':digest(solver),'stage1_notes_read':bool(prior_notes),
                               'followup_sha256':digest(WORK/'01_review_followup.md')},
              'script_sha256':digest(__file__),'artifact_directory':str(run_dir.relative_to(ROOT)).replace('\\','/'),
              'basis_path':(run_dir/'basis.npz').relative_to(ROOT).as_posix(),
              'numeric_rank':numerical_rank,'rank_tolerance':float(rank_tol),'singular_values':singular.tolist(),
              'legal_candidates':candidates,'selected_rank':selected,'diagnostic_rank':diagnosis_rank,
              'tuning_target_met':selected is not None,'counts':dict(COUNTS),'costs':costs,
              'definitions':{'hotspot':'abs(max(ROM)-max(FOM))','field_linf':'max(abs(ROM-FOM))',
                             'relative_l2':'Euclidean norm(ROM-FOM)/norm(FOM); uniform area weights cancel',
                             'relative_residual':'norm(b-Au,2)/norm(b,2)',
                             'zero_denominator':'0 if numerator is 0, otherwise null (undefined); absolute quantities retained'},
              'checks':checks,'rank_curves':curves,'fom_records':fom_records,'rom_records':rows,
              'wall_seconds_before_final_reports':time.perf_counter()-started,
              'limitations':['Development data only; no final test generated.','FOM is a floating-point discrete reference, not continuous truth.',
                             'Single pass timing is noisy; no general speedup claim.','Target met on tuning points does not guarantee the parameter domain.']}
    write_json(run_dir/'02_baseline.json',report)
    write_json(RESULTS/'02_baseline.json',report)
    summary = {k:report[k] for k in ['run_timestamp_utc','status','exit_code','basis_path','numeric_rank','rank_tolerance','selected_rank','diagnostic_rank','counts','costs','checks','rank_curves']}
    note = '# thermal-rom 固定POD基线\n\n本文件由原生实验脚本按实际运行记录生成，局部审核状态pending。协议来自协调者事先给定的用户消息；若stage2_protocol.txt被找到，其原文及哈希保存在config中，否则不声称已读取该文件。使用阶段1原始算子，执行前json.load解析01_model.json并核对34项通过及源码哈希，读取阶段1说明与审核补记，不重跑旧实验。\n\n训练24点、调参12点，独立种子20261025、20261026，对数均匀采样；没有最终测试集。未中心化训练快照SVD，数值秩阈值max(S.shape)*eps*s[0]，合法候选1、2、4、8、12、24。只用调参最大场Linf误差和预设tau=1e-3选择最小达标秩；若不达标selected_rank为空，最大合法秩仅用于诊断。\n\n精确算术：A为阶段1已论证的SPD矩阵，V满列秩则c.T@(V.T@A@V)@c=(V@c).T@A@(V@c)>0，因此约化系统唯一可解。实际核心为Ar=V.T@(A@V), br=V.T@b, a=np.linalg.solve(Ar,br), u=V@a。正交性采用||V.T@V-I||inf；检查投影尺寸、投影残差、Galerkin残差、有限值和存盘一致性。\n\n误差均相对同一浮点FOM：热点abs(max(u)-max(ref))；场误差max(abs(u-ref))；相对L2为欧氏误差范数除以参照范数，均匀面积权重抵消；相对残差||b-Au||2/||b||2。零分母且零分子记0，否则null表示未定义。\n\n训练与调参FOM只各求解一次并跨秩复用；每个ROM重新装配，同步记录装配、投影、小矩阵求解、重构、残差与开发检查耗时。没有基更新。离线快照、SVD及调参参照代价均保留；在线比值不包含离线成本，另列离线加指定线上总成本。全部记录见02_baseline.json，参数、全部候选ROM/FOM解、奇异值与基见独立运行目录。计时仅单次观测，不支持稳定加速结论。最终报告写盘时间不在wall_seconds_before_final_reports内，工具进程耗时另见原版返回。\n\n本轮未修改原求解器；旧结果自动备份。阶段1初审证据不足及后续通过记录保持不变。下一步依赖本存档开展16角点与调参数据的开发失效分析，之后提交自包含局部审核。\n\n实际运行摘要：\n\n' + json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False) + '\n'
    preserve(WORK/'02_baseline_notes.md')
    (WORK/'02_baseline_notes.md').write_text(note,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True,allow_nan=False))
    return report['exit_code']

if __name__ == '__main__':
    try:
        code = main()
    except Exception:
        failure = {'project':'thermal-rom','status':'failed_incomplete','exit_code':1,'run_timestamp_utc':STAMP,
                   'counts':dict(COUNTS),'traceback':traceback.format_exc()}
        write_json(RESULTS/('02_failure_'+STAMP+'.json'),failure)
        print(json.dumps(failure,ensure_ascii=True))
        code = 1
    sys.exit(code)
