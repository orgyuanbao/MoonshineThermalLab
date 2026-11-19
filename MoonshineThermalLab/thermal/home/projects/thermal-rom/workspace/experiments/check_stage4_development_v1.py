"""Development-only checks. Does not freeze or generate final parameters."""
import os
THREAD_KEYS = ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')
for key in THREAD_KEYS:
    os.environ[key] = '1'
import sys,json,time,hashlib,itertools,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT = Path(__file__).resolve().parents[2]
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = ROOT/'workspace/results'/('04_development_'+STAMP)
OUT.mkdir(parents=True,exist_ok=False)
COUNTS = {'raw_fom':0,'fast_fom':0,'adaptive_fom':0,'fixed_rom':0,'adaptive_rom':0}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(name,obj):
    path = OUT/name
    with path.open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
    with path.open(encoding='utf-8') as f:
        json.load(f)

def main():
    import numpy as np
    import scipy
    from stage4_kernels_v1 import Geometry,Reduced,full_solve,diagnostics,errors,TAU
    from thermal_solver import assemble
    started = time.perf_counter()
    solver = Path(__file__).with_name('thermal_solver.py')
    assert sha(solver) == '67f3b1bd3adfd34b28c6c449a782438be2e1104a444c08c46e8fb66589b63ab6'
    with (ROOT/'workspace/results/02_baseline.json').open(encoding='utf-8') as f:
        baseline = json.load(f)
    assert baseline['project'] == 'thermal-rom' and baseline['exit_code'] == 0
    assert baseline['selected_rank'] == 8 and all(c['passed'] for c in baseline['checks'])
    with (ROOT/'workspace/results/03_failure.json').open(encoding='utf-8') as f:
        stage3 = json.load(f)
    assert stage3['project'] == 'thermal-rom' and stage3['exit_code'] == 0
    followup = ROOT/'workspace/02_03_review_followup.md'
    assert 'overall_verdict=correct' in followup.read_text(encoding='utf-8')
    basis = ROOT/baseline['basis_path']
    with np.load(basis,allow_pickle=False) as saved:
        V = saved['V'].copy()
        train = saved['train_parameters'].copy()
        tune = saved['tune_parameters'].copy()
        archived_train = saved['train_fom'].copy()
        archived_tune = saved['tune_fom'].copy()
    assert V.shape == (576,8) and train.shape == (24,4) and tune.shape == (12,4)
    corners = np.array(list(itertools.product((0.2,5.0),repeat=4)))
    parameters = np.vstack((train,tune,corners))
    checks,records,adaptive_records = [],[],[]
    def check(name,value,tolerance):
        value = float(value)
        checks.append({'name':name,'value':value,'tolerance':tolerance,'passed':bool(np.isfinite(value) and value <= tolerance)})
    def maxabs(x):
        return float(np.max(np.abs(x)))
    g = Geometry(24)
    fixed = Reduced(g,V)
    check('initial_orthogonality',np.linalg.norm(V.T@V-np.eye(8),ord=np.inf),1e-12)
    check('zmax_expected_791_875',abs(g.zmax-791.875),1e-12)
    references,raw_predictions,fast_predictions = [],[],[]
    for i,h in enumerate(parameters):
        A,b,_ = assemble(24,h)
        B = g.matrix(h)
        diff = A-B
        check('matrix_'+str(i),maxabs(diff.data) if diff.nnz else 0.0,1e-13)
        check('source_'+str(i),maxabs(b-g.b),0)
        check('barrier_'+str(i),max(0.0,1-float(np.min(B@g.z))),1e-9)
        COUNTS['raw_fom'] += 1
        ref,rt = full_solve(g,h,False)
        COUNTS['fast_fom'] += 1
        fast,ft = full_solve(g,h,True)
        check('fom_equivalence_'+str(i),maxabs(fast-ref),1e-10)
        check('fast_fom_residual_'+str(i),diagnostics(g,h,fast)['relative_residual_l2'],1e-10)
        if i < 36:
            archived = archived_train[:,i] if i < 24 else archived_tune[:,i-24]
            check('archived_fom_'+str(i),maxabs(ref-archived),1e-10)
        ur,tr = fixed.predict(h,False)
        uf,tf = fixed.predict(h,True)
        COUNTS['fixed_rom'] += 2
        check('rom_equivalence_'+str(i),maxabs(ur-uf),1e-10)
        check('action_'+str(i),maxabs(g.action(h,uf)-A@uf),1e-12)
        Ar = V.T@(A@V)
        check('projected_shape_'+str(i),int(Ar.shape != (8,8)),0)
        check('galerkin_'+str(i),np.linalg.norm(V.T@(b-A@uf))/np.linalg.norm(V.T@b),1e-10)
        references.append(ref)
        raw_predictions.append(ur)
        fast_predictions.append(uf)
        records.append({'index':i,'role':'train' if i<24 else ('tune' if i<36 else 'corner_development'),'h':h.tolist(),'raw_fom_timing':rt,'fast_fom_timing':ft,'raw_rom_timing':tr,'fast_rom_timing':tf,'fast_rom_error':errors(uf,ref)})
    adaptive = Reduced(g,V)
    returned,pre_fields = [],[]
    for j,h in enumerate(parameters[24:]):
        before_hash = hashlib.sha256(adaptive.V.tobytes()).hexdigest()
        out,pre,info = adaptive.adaptive(h)
        COUNTS['adaptive_rom'] = adaptive.rom_calls
        COUNTS['adaptive_fom'] = adaptive.fom_calls
        ref = references[24+j]
        er,ep = errors(out,ref),errors(pre,ref)
        check('adaptive_orthogonality_'+str(j),np.linalg.norm(adaptive.V.T@adaptive.V-np.eye(adaptive.V.shape[1]),ord=np.inf),1e-10)
        check('adaptive_cap_'+str(j),max(0,adaptive.V.shape[1]-32),0)
        check('trigger_rule_'+str(j),int(info['trigger'] != (info['eta']>TAU)),0)
        check('returned_fom_flag_'+str(j),int(info['trigger'] != info['returned_fom']),0)
        if info['trigger']:
            check('fallback_equivalence_'+str(j),er['field_linf'],1e-10)
        else:
            check('accepted_error_vs_float_indicator_'+str(j),max(0.0,er['field_linf']-info['eta']),1e-10)
        adaptive_records.append({'index':j,'development_index':24+j,'h':h.tolist(),'basis_before_sha256':before_hash,**info,'returned_error':er,'pre_error':ep,'false_trigger':bool(info['trigger'] and ep['field_linf']<=TAU)})
        returned.append(out)
        pre_fields.append(pre)
    boundary = Reduced(g,V)
    correlated = boundary.augment(V[:,0])
    zero = boundary.augment(np.zeros(576))
    check('correlated_rejected',int(correlated['status']!='correlated'),0)
    check('zero_rejected',int(zero['status']!='zero_solution'),0)
    rejected = 0
    for h in ([0.1,1,1,1],[6,1,1,1],[float('nan'),1,1,1]):
        try:
            boundary.adaptive(h)
        except ValueError:
            rejected += 1
    check('invalid_parameters_rejected',abs(rejected-3),0)
    rejected = False
    try:
        boundary.augment(np.full(576,np.nan))
    except ValueError:
        rejected = True
    check('nonfinite_augmentation_rejected',int(not rejected),0)
    small = Geometry(1)
    cap = Reduced(small,np.ones((1,1)))
    capped = cap.augment(np.ones(1))
    check('space_rank_cap',int(capped['status']!='rank_cap'),0)
    check('single_cell_matrix_expected_4',abs(float(small.matrix([2,2,2,2])[0,0])-4),1e-14)
    check('single_cell_source_expected_012',abs(float(small.b[0])-0.12),1e-13)
    np.savez_compressed(OUT/'development_fields.npz',parameters=parameters,V_initial=V,V_final=adaptive.V,reference=np.array(references),raw_rom=np.array(raw_predictions),fast_rom=np.array(fast_predictions),adaptive_returned=np.array(returned),adaptive_pre=np.array(pre_fields))
    passed = all(c['passed'] for c in checks)
    summary = {'checks_count':len(checks),'all_passed':passed,'failed_checks':[c for c in checks if not c['passed']],'counts':COUNTS,'adaptive_triggers':adaptive.fom_calls,'adaptive_updates':adaptive.updates,'adaptive_final_rank':adaptive.V.shape[1],'false_triggers':sum(r['false_trigger'] for r in adaptive_records),'max_fast_fom_difference':max(c['value'] for c in checks if c['name'].startswith('fom_equivalence_')),'max_fast_rom_difference':max(c['value'] for c in checks if c['name'].startswith('rom_equivalence_')),'max_adaptive_field_error':max(r['returned_error']['field_linf'] for r in adaptive_records),'correlated_case':correlated,'zero_case':zero,'rank_cap_case':capped}
    report = {'project':'thermal-rom','status':'development_checks_passed_pending_review' if passed else 'development_checks_failed','exit_code':0 if passed else 1,'timestamp_utc':STAMP,'final_test_generated':False,'frozen':False,'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'requested_thread_environment':{k:os.environ[k] for k in THREAD_KEYS},'thread_policy':'Set before importing numerical libraries; actual native thread counts not independently inspected'},'hashes':{'solver':sha(solver),'kernels':sha(Path(__file__).with_name('stage4_kernels_v1.py')),'checker':sha(__file__),'baseline':sha(ROOT/'workspace/results/02_baseline.json'),'basis':sha(basis),'historical_review_followup':sha(followup)},'summary':summary,'checks':checks,'records':records,'adaptive_records':adaptive_records,'geometry_seconds':g.geometry_seconds,'barrier_seconds':g.barrier_seconds,'fixed_cache_seconds':fixed.initialization_seconds,'adaptive_cache_seconds':adaptive.initialization_seconds,'development_wall_seconds':time.perf_counter()-started,'limitations':['Development data only; stored rank8 basis reused without rebuilding training.','No deployment total-cost or speedup conclusion; final experiment runner and cost ledger are not yet implemented.','Ordinary floating-point indicator is not interval certification.','Reference arrays are used only by checker after adaptive call; adaptive API receives only h.','Historical review followup read; original verifier event not retrieved in this execution.']}
    write('04_development.json',report)
    print(json.dumps({'artifact_directory':OUT.relative_to(ROOT).as_posix(),**summary},ensure_ascii=True,allow_nan=False))
    return report['exit_code']

if __name__ == '__main__':
    try:
        code = main()
    except Exception:
        report = {'project':'thermal-rom','status':'failed_incomplete','exit_code':1,'counts':COUNTS,'traceback':traceback.format_exc(),'final_test_generated':False}
        write('failure.json',report)
        print(json.dumps(report,ensure_ascii=True))
        code = 1
    sys.exit(code)
