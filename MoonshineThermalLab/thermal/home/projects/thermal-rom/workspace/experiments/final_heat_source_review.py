"""External read-only integrity/heat-source check for Moonshine's follow-up review.

Uses only already frozen parameters and outputs; no FOM/ROM solves, no RNG,
and no alteration of frozen algorithms or results. The tool execution itself
must still be recorded by Moonshine before calling it a native execution.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import final_benchmark_driver as evaluation


def main():
    kernel, config, parameters, train = evaluation.verify_freeze()
    np = evaluation.np
    checks = []
    for n in (24,48,96):
        edges = np.arange(n+1,dtype=float)/n
        first = np.maximum(0.,np.minimum(edges[1:],.4)-np.maximum(edges[:-1],.2))
        second = np.maximum(0.,np.minimum(edges[1:],.8)-np.maximum(edges[:-1],.6))
        expected = (np.outer(first,first)+2*np.outer(second,second)).ravel()
        actual = kernel.source_integrals(n)
        g = kernel.Geometry(n)
        difference = float(np.max(np.abs(expected-actual)))
        heat = float(actual.sum())
        assert difference <= 1e-14 and abs(heat-.12) <= 1e-14
        assert np.array_equal(g.b,actual)
        checks.append({'n':n,'total_heat':heat,'explicit_formula_max_difference':difference,
                       'fast_geometry_uses_identical_source':True})
    final = evaluation.FINAL
    summary = evaluation.read(final/'summary.json')
    assert summary['status']=='complete' and summary['completed_valid_repetitions']==9
    for relative, expected in summary['source_result_sha256'].items():
        path = final/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
        result = evaluation.read(path)
        assert result['execution_complete'] and result['validation_passed']
        assert result['parameter_array_sha256']==evaluation.array_sha(parameters)
    concise=[]
    for row in summary['comparisons']:
        if row['method'] in ('fast_fom','fast_pod','adaptive'):
            item={k:row[k] for k in ('n','queries','method')}
            item.update(total_ratio=row['fast_fom_over_method_total_ratio'],
                        max_field_error=row['max_field_linf']['maximum'],
                        max_hotspot_error=row['max_hotspot_error']['maximum'],
                        field_exceedances=row['field_exceedances_per_repetition'])
            if row['method']=='adaptive':
                item.update({k:row[k] for k in ('triggers_per_repetition','updates_per_repetition',
                            'false_alarms_per_repetition','missed_failures_per_repetition','final_rank_per_repetition')})
            concise.append(item)
    report={'origin':'Externally provided integrity check; native execution attribution requires tool event',
            'checked_at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,
            'new_fom_solves':0,'new_rom_solves':0,'new_test_parameters_generated':False,
            'heat_source_formula':'b[j*n+i] = ell(i;0.2,0.4)*ell(j;0.2,0.4) + 2*ell(i;0.6,0.8)*ell(j;0.6,0.8), ell(i;a,b)=max(0,min((i+1)/n,b)-max(i/n,a)).',
            'model':'Omega=(0,1)^2; k=1; ambient rise=0; integrated cell-center FV; side order left/right/bottom/top; beta=delta/(delta/2+1/h).',
            'heat_checks':checks,'configuration_sha256':evaluation.sha(final/'frozen_configuration.json'),
            'source_sha256':config['source_sha256'],'complete_valid_repetitions':9,
            'actual_study_counts':summary['counts_actual_executed_complete_runs'],
            'limited_empirical_results':concise,
            'scope':'Unchanged frozen finite experiment; double precision. No universal/continuous/industrial/optimality guarantee.'}
    directory=evaluation.ROOT/'workspace/review'
    directory.mkdir(exist_ok=True)
    path=directory/('final_heat_source_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    evaluation.exclusive_json(path,report)
    print(json.dumps({'artifact':str(path.relative_to(evaluation.ROOT)),**report},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
