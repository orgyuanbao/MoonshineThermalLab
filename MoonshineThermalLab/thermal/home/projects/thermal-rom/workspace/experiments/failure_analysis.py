"""Development diagnostics using saved fixed POD; no final tests or basis updates."""
import sys, json, time, traceback, itertools, hashlib
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction as Q
import numpy as np
import scipy
import pod_baseline as pb
from thermal_solver import assemble, solve

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'workspace'
OUT = WORK / 'results'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
COUNTS = {'new_fom_calls':0, 'new_rom_calls':0, 'reused_tuning_fom':0, 'reused_tuning_rom':0}
pb.np = np
pb.assemble = assemble
pb.solve = solve

def z_vector(n):
    d = 1.0/n
    x = (np.arange(n)+0.5)*d
    f = x*(1-x)
    return ((5.0+f[:,None]+f[None,:])/(4*d*d)).ravel()

def exact_barrier_checks():
    records = []
    for n in [1,2,3,4]:
        d = Q(1,n)
        x = [(Q(i)+Q(1,2))*d for i in range(n)]
        z = [(Q(5)+x[i]*(1-x[i])+x[j]*(1-x[j]))/(4*d*d) for j in range(n) for i in range(n)]
        for hs in itertools.product([Q(1,5),Q(5)],repeat=4):
            g = [d/(d/2+1/h) for h in hs]
            az = []
            for j in range(n):
                for i in range(n):
                    p = j*n+i
                    value = Q(0)
                    for di,dj,side in [(-1,0,0),(1,0,1),(0,-1,2),(0,1,3)]:
                        ii,jj = i+di,j+dj
                        if 0 <= ii < n and 0 <= jj < n:
                            value += z[p]-z[jj*n+ii]
                        else:
                            value += g[side]*z[p]
                    az.append(value)
            records.append({'n':n,'h':[str(h) for h in hs], 'min_Az':str(min(az)),
                            'passed':all(v >= 1 for v in az), 'cells_checked':n*n})
    return records

def main():
    start = time.perf_counter()
    with (OUT/'02_baseline.json').open(encoding='utf-8') as f:
        base = json.load(f)
    assert base['project']=='thermal-rom' and base['exit_code']==0
    assert all(c['passed'] for c in base['checks'])
    assert base['config']['n']==24 and not base['config']['final_test_generated']
    solver_path = Path(__file__).with_name('thermal_solver.py')
    assert pb.digest(solver_path)==base['config']['solver_sha256']
    basis_path = ROOT/base['basis_path']
    with np.load(basis_path,allow_pickle=False) as saved:
        rank = int(saved['diagnostic_rank'])
        V = saved['V_diagnostic'].copy()
        tuning = saved['tune_parameters'].copy()
        tune_fom = saved['tune_fom'].copy()
        tune_rom = saved['rom_tune_r'+str(rank)].copy()
    assert rank==base['diagnostic_rank'] and V.shape==(576,rank)
    selected = base['selected_rank']
    tau = base['config']['tau']
    run_dir = OUT/('03_run_'+STAMP)
    run_dir.mkdir(exist_ok=False)
    checks = []
    def check(name,value,tol):
        value = float(value)
        checks.append({'name':name,'value':value,'tolerance':tol,'passed':bool(np.isfinite(value) and value<=tol)})
    tz = time.perf_counter()
    z = z_vector(24)
    zmax = float(z.max())
    z_seconds = time.perf_counter()-tz
    check('zmax_against_791_875',abs(zmax-791.875),1e-10)
    check('basis_orthogonality_inf',np.linalg.norm(V.T@V-np.eye(rank),ord=np.inf),1e-12)
    tq = time.perf_counter()
    fractions = exact_barrier_checks()
    fraction_seconds = time.perf_counter()-tq
    check('exact_fraction_failed_cases',sum(not r['passed'] for r in fractions),0)
    corners = np.array(list(itertools.product([0.2,5.0],repeat=4)))
    rows, full_fields, rom_fields = [], [], []
    for label, parameters in [('tune_development',tuning),('corner_development',corners)]:
        for index,h in enumerate(parameters):
            timing = {}
            if label=='tune_development':
                ref = tune_fom[:,index]
                u = tune_rom[:,index]
                COUNTS['reused_tuning_fom'] += 1
                COUNTS['reused_tuning_rom'] += 1
                timing['new_fom_seconds'] = 0.0
                timing['new_rom_seconds'] = 0.0
                timing['reference_cost_location'] = '02_baseline.json; reuse does not erase original cost'
            else:
                COUNTS['new_fom_calls'] += 1
                ref,_,_,_,tf = solve(24,h)
                timing['fom'] = tf
                COUNTS['new_rom_calls'] += 1
                u,rm,tr = pb.rom(h,V)
                timing['rom'] = tr
                check('corner_projected_residual_'+str(index),rm['projected_relative_residual'],1e-10)
                check('corner_projected_shape_'+str(index),int(rm['projected_shape']!=[rank,rank]),0)
            t = time.perf_counter()
            A,b,_ = assemble(24,h)
            timing['diagnostic_reassembly_seconds'] = time.perf_counter()-t
            t = time.perf_counter()
            residual = b-A@u
            rinf = float(np.max(np.abs(residual)))
            rtwo = float(np.linalg.norm(residual))
            relative_residual = pb.ratio(rtwo,np.linalg.norm(b))
            eta = rinf*zmax
            timing['residual_norm_eta_seconds'] = time.perf_counter()-t
            t = time.perf_counter()
            az = A@z
            min_az = float(az.min())
            timing['barrier_float_validation_seconds'] = time.perf_counter()-t
            t = time.perf_counter()
            error = pb.errors(u,ref)
            ref_r = b-A@ref
            ref_eta = float(np.max(np.abs(ref_r))*zmax)
            ref_relative = pb.ratio(np.linalg.norm(ref_r),np.linalg.norm(b))
            effectivity = pb.ratio(eta,error['field_linf_error'])
            timing['reference_error_and_residual_seconds'] = time.perf_counter()-t
            check(label+'_Az_'+str(index),max(0.0,1-min_az),1e-10)
            check(label+'_fom_residual_'+str(index),ref_relative,1e-10)
            check(label+'_fields_finite_'+str(index),np.count_nonzero(~np.isfinite(u))+np.count_nonzero(~np.isfinite(ref)),0)
            check(label+'_hotspot_le_field_'+str(index),max(0.0,error['hotspot_error']-error['field_linf_error']),1e-12)
            # Empirical consistency only: rounded residuals are NOT certified bounds.
            check(label+'_error_vs_eta_plus_reference_'+str(index),max(0.0,error['field_linf_error']-eta-ref_eta),1e-10)
            row = {'dataset':label,'index':index,'h':h.tolist(),'selected_rank':selected,'diagnostic_rank':rank,
                   **error,'residual_linf':rinf,'residual_l2':rtwo,'relative_residual_l2':relative_residual,
                   'eta_float':eta,'eta_over_observed_field_error':effectivity,
                   'fom_residual_eta_float':ref_eta,'fom_relative_residual':ref_relative,'min_Az_float':min_az,
                   'field_target_exceeded':bool(error['field_linf_error']>tau),
                   'eta_trigger_candidate':bool(eta>tau),'timing':timing}
            rows.append(row)
            full_fields.append(ref)
            rom_fields.append(u)
    # An independent algebraic family, explicitly unrelated to this PDE operator.
    algebra = []
    for eps in [1e-1,1e-3,1e-6,1e-9]:
        A = np.diag([eps,1.0])
        b = np.array([eps,0.5])
        exact = np.array([1.0,0.5])
        approximate = np.array([0.0,0.5])
        r = b-A@approximate
        rec = {'epsilon':eps,'A':A.tolist(),'b':b.tolist(),'exact_solution':exact.tolist(),
               'approximate_solution':approximate.tolist(),**pb.errors(approximate,exact),
               'raw_residual_linf':float(np.max(np.abs(r))),
               'relative_residual_l2':pb.ratio(np.linalg.norm(r),np.linalg.norm(b)),
               'is_project_PDE_matrix':False}
        check('algebra_exact_equation_'+str(eps),np.max(np.abs(A@exact-b)),1e-15)
        check('algebra_field_error_'+str(eps),abs(rec['field_linf_error']-1),0)
        check('algebra_hotspot_error_'+str(eps),abs(rec['hotspot_error']-0.5),0)
        check('algebra_residual_'+str(eps),abs(rec['raw_residual_linf']-eps),0)
        algebra.append(rec)
    check('new_fom_count',abs(COUNTS['new_fom_calls']-16),0)
    check('new_rom_count',abs(COUNTS['new_rom_calls']-16),0)
    check('development_point_count',abs(len(rows)-28),0)
    np.savez_compressed(run_dir/'development_fields.npz',parameters=np.vstack([tuning,corners]),
                        fom=np.column_stack(full_fields),rom=np.column_stack(rom_fields),z=z,V=V)
    nonzero_ratios = [r['eta_over_observed_field_error'] for r in rows if r['eta_over_observed_field_error'] is not None]
    summary = {'selected_rank':selected,'diagnostic_rank':rank,'tau':tau,'zmax':zmax,
               'development_points':len(rows),'field_failures':sum(r['field_target_exceeded'] for r in rows),
               'tuning_field_failures':sum(r['field_target_exceeded'] for r in rows if r['dataset']=='tune_development'),
               'corner_field_failures':sum(r['field_target_exceeded'] for r in rows if r['dataset']=='corner_development'),
               'eta_trigger_count':sum(r['eta_trigger_candidate'] for r in rows),
               'eta_trigger_without_observed_failure':sum(r['eta_trigger_candidate'] and not r['field_target_exceeded'] for r in rows),
               'worst_field':max(rows,key=lambda r:r['field_linf_error']),
               'worst_hotspot':max(rows,key=lambda r:r['hotspot_error']),
               'effectivity_min':min(nonzero_ratios),'effectivity_median':float(np.median(nonzero_ratios)),
               'effectivity_max':max(nonzero_ratios),
               'min_Az_float':min(r['min_Az_float'] for r in rows),
               'max_fom_relative_residual':max(r['fom_relative_residual'] for r in rows),
               'fraction_cases':len(fractions),'fraction_cells':sum(r['cells_checked'] for r in fractions),
               'fraction_all_passed':all(r['passed'] for r in fractions),
               'no_failure_statement':'No field error above tau found in these development points' if not any(r['field_target_exceeded'] for r in rows) else 'Field error above tau found only as documented in development rows'}
    costs = {'barrier_vector_construction_seconds':z_seconds,'fraction_validation_seconds':fraction_seconds,
             'new_corner_fom_assembly_solve_seconds':sum(r['timing']['fom']['assembly_and_solve_seconds'] for r in rows if r['dataset']=='corner_development'),
             'new_corner_rom_online_seconds':sum(r['timing']['rom']['online_total_seconds'] for r in rows if r['dataset']=='corner_development'),
             'diagnostic_reassembly_seconds':sum(r['timing']['diagnostic_reassembly_seconds'] for r in rows),
             'residual_norm_eta_seconds':sum(r['timing']['residual_norm_eta_seconds'] for r in rows),
             'float_Az_validation_seconds':sum(r['timing']['barrier_float_validation_seconds'] for r in rows),
             'reference_evaluation_seconds':sum(r['timing']['reference_error_and_residual_seconds'] for r in rows),
             'basis_update_seconds':0.0,'basis_update_count':0}
    proof = 'For integer n>=1, Delta=1/n, cell centers x_i=(i+1/2)Delta and y_j=(j+1/2)Delta, let A be the integrated FV matrix with unit interior edge conductances and Robin diagonal face coefficients g_s=Delta/(Delta/2+1/h_s), each h_s in [0.2,5]. Set F=5+x(1-x)+y(1-y), z=F/(4Delta^2). The complete four-neighbor polynomial stencil gives 4Delta^2. At a missing exterior neighbor, F_P-F_ghost=Delta, including n=1. On any boundary center the two quadratic terms have sum at least Delta-Delta^2/2, hence F_P>=5+Delta/2>=1/h_s+Delta/2. Thus g_s F_P>=Delta. Each missing neighbor is compensated independently, so Az>=1. In particular n=1 has F=11/2, z=11/8, g_s>=2/11, and Az>=4*(2/11)*(11/8)=1. The energy identity gives SPD. For any nonnegative RHS, a negative minimum of the solution contradicts its boundary equation or propagates along connected interior edges to a boundary contradiction. Therefore A inverse is entrywise nonnegative. For any real approximate vector u and exact discrete solution T=A inverse b, r=b-Au, we have |T-u|<=A inverse |r|<=||r||inf A inverse 1<=||r||inf z, since A inverse(Az-1)>=0. The maximum functional is 1-Lipschitz in the infinity norm, proving hotspot error<=field error<=eta. For n=24 the nearest centers to one half are 23/48 and 25/48, so max z=144*(5+2*575/2304)=6335/8=791.875. For a floating FOM reference with residual r_F, exact arithmetic additionally gives ||u-T_F||inf<=(||r||inf+||r_F||inf)*max z; rounded program evaluations are only consistency checks, not interval-certified bounds.'
    algebra_proof = 'For every epsilon>0, diag(epsilon,1) is SPD. With b=(epsilon,1/2), the exact solution is (1,1/2); approximation (0,1/2) has field infinity error 1 and maximum-value error 1/2. Its raw infinity residual is epsilon and relative Euclidean residual is epsilon/sqrt(epsilon^2+1/4), both tending to zero. This is an arbitrary algebraic family, not a matrix derived from the thermal PDE.'
    passed = all(c['passed'] for c in checks)
    report = {'project':'thermal-rom','run_timestamp_utc':STAMP,'exit_code':0 if passed else 1,
              'status':'checks_passed_pending_review' if passed else 'checks_failed', 'verification_status':'pending',
              'baseline_run':base['run_timestamp_utc'],'baseline_json_sha256':pb.digest(OUT/'02_baseline.json'),
              'basis_path':base['basis_path'],'basis_sha256':pb.digest(basis_path),'script_sha256':pb.digest(__file__),
              'solver_sha256':pb.digest(solver_path),'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__},
              'counts':dict(COUNTS),'summary':summary,'costs':costs,'checks':checks,'rows':rows,
              'fraction_checks':fractions,'algebraic_counterexample':algebra,'proof':proof,'algebraic_proof':algebra_proof,
              'data_role':'All 28 points are development data; tuning values reused, corners do not change rank',
              'final_test_generated':False,'artifact_directory':run_dir.relative_to(ROOT).as_posix(),
              'source_attribution':'Barrier construction and bibliography supplied by coordinator and external reviewer; independently derived and checked here. External Fraction checks not counted. Literature not independently retrieved.',
              'reference_supplied':'Minamihata, Sekine, Ogita, Oishi (2013), Fast Verified Solutions of Sparse Linear Systems with H-matrices, Reliable Computing 19,127-141; https://interval.louisiana.edu/reliable-computing-journal/volume-19/reliable-computing-19-pp-127-141.pdf',
              'wall_seconds_before_final_reports':time.perf_counter()-start,
              'limitations':['Floating eta is not roundoff-certified.','Errors are against floating discrete FOM, not continuous PDE truth.',
                             'Finite development search is not global worst-case optimization.','Single timing observations are not performance guarantees.']}
    pb.write_json(run_dir/'03_failure.json',report)
    pb.write_json(OUT/'03_failure.json',report)
    # Real newline characters in this new note; no rewrite of historical files.
    paragraphs = ['# thermal-rom 开发失效分析',
                  '本文件由本轮原生实验生成；局部审核pending。读取基线JSON及NPZ，固定先前所选秩，仅使用12个调参点和16个边界角点。调参FOM与ROM复用，新增16次FOM与16次ROM；旧计算成本仍在02_baseline.json中，不能称作本轮再次执行。未生成最终测试，未更新基。',
                  '理论来源：屏障构造、经典比较原理方向及文献书目信息由协调者与外部复核提供，不是Moonshine自主发现。此处给出原生推导和实际Fraction小规模检查；外部已有检查不计入本轮次数。未联网独立查阅所给论文，不声称新定理。',
                  proof,algebra_proof,
                  '原生Fraction检查覆盖n=1,2,3,4及各16个角点；它精确核对有限有理数算例，不替代上面的任意网格证明。n=24实际算子Az检查及eta计算使用双精度，未包含区间舍入误差认证。eta无需额外FOM预解；程序为验证误差额外做的16次FOM及全部重组装、检查、向量和范数成本均单列。',
                  '误差定义及零分母约定沿用基线：热点为两个离散最大值差的绝对值，场为逐点误差绝对值最大值，相对L2除以FOM欧氏范数；相对残差除以b的欧氏范数。比值分母为零时，零分子记0，否则null。效应比eta/场误差仅描述当前开发样本保守程度。',
                  '若出现tau以上误差，只能称当前开发样本失效；若未出现则明确未找到。角点不参与改选秩。阶段1初审inconclusive和补充审核通过均保留；原求解器未改。没有预设失败或加速，硬件计时只是单次观测。下一步提交本轮局部审核，之后才另轮设计并冻结自适应方案及最终未见测试协议。',
                  json.dumps({'summary':summary,'counts':COUNTS,'costs':costs,'checks_passed':passed},ensure_ascii=False,indent=2,allow_nan=False)]
    pb.preserve(WORK/'03_failure_notes.md')
    (WORK/'03_failure_notes.md').write_text(chr(10).join(paragraphs)+chr(10),encoding='utf-8')
    # Compact, readable evidence for the model verifier; full per-point arrays are saved.
    print(json.dumps({'run_timestamp_utc':STAMP,'exit_code':report['exit_code'],'counts':COUNTS,
                      'summary':summary,'costs':costs,'checks':checks, 'algebra':algebra,
                      'artifact_directory':report['artifact_directory'],
                      'baseline_protocol_files_found':base['config']['protocol_files_found']},ensure_ascii=True,allow_nan=False))
    return report['exit_code']

if __name__=='__main__':
    try:
        code = main()
    except Exception:
        failure = {'status':'failed_incomplete','exit_code':1,'counts':COUNTS,'traceback':traceback.format_exc()}
        pb.write_json(OUT/('03_failure_attempt_'+STAMP+'.json'),failure)
        print(json.dumps(failure,ensure_ascii=True))
        code = 1
    sys.exit(code)
