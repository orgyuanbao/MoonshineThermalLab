"""Plot already completed frozen experiments; no models or new numerical solves."""
from pathlib import Path
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'home/projects/thermal-rom/workspace/results/04_final_v1'
OUT = ROOT / 'figures'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 14,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'savefig.facecolor': 'white'})
grids = [24, 48, 96]
records = {}
inputs = {}
for n in grids:
    records[n] = []
    for rep in [1, 2, 3]:
        path = DATA / f'n{n}/repeat{rep:02d}/result.json'
        result = json.loads(path.read_text(encoding='utf-8'))
        marker = json.loads(path.with_name('completed.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert marker['result_sha256'] == digest
        assert result['execution_complete'] and result['validation_passed']
        assert result['n'] == n and result['repeat'] == rep
        records[n].append(result)
        inputs[str(path.relative_to(ROOT.parent))] = digest

colors = {'fast_pod': '#277c9d', 'adaptive': '#df7a32'}
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout='constrained')
ax = axes[0]
x = np.arange(3)
width = .18
for offset, method, count, alpha in [(-1.5,'fast_pod',24,.45),(-.5,'adaptive',24,.45),
                                     (.5,'fast_pod',256,1),(1.5,'adaptive',256,1)]:
    values = np.array([[r['methods'][method]['prefixes'][str(count)]['fast_fom_over_method_total_ratio']
                        for r in records[n]] for n in grids])
    med = np.median(values,axis=1)
    ax.bar(x + offset*width, med, width, color=colors[method],alpha=alpha,
           label=('Fixed POD' if method=='fast_pod' else 'Adaptive')+f', Q={count}',
           yerr=np.vstack([med-values.min(axis=1),values.max(axis=1)-med]),capsize=3)
ax.axhline(1,color='#53616d',linestyle='--',linewidth=1)
ax.set_xticks(x,[str(n) for n in grids])
ax.set_xlabel('Cells per side, n')
ax.set_ylabel('Fast FOM cost / method cost')
ax.set_title('(a) Total cost, including offline work')
ax.legend(fontsize=12,ncol=2,loc='upper left')
ax.set_ylim(0,14)
ax = axes[1]
for method,label,marker in [('fast_pod','Fixed POD, r=8','o'),('adaptive','Adaptive POD','s')]:
    values = np.array([[r['methods'][method]['prefixes']['256']['max_field_linf'] for r in records[n]] for n in grids])
    med = np.median(values,axis=1)
    ax.semilogy(grids,med,marker=marker,color=colors[method],label=label,linewidth=2)
    ax.fill_between(grids,values.min(axis=1),values.max(axis=1),color=colors[method],alpha=.18)
ax.axhline(1e-3,color='#53616d',linestyle='--',label='Target = 1e-3')
ax.set_xticks(grids)
ax.set_xlabel('Cells per side, n')
ax.set_ylabel('Maximum field error over 256 queries')
ax.set_title('(b) Accuracy on the frozen stream')
ax.legend(loc='center left',fontsize=12)
ax.set_ylim(5e-8,9e-3)
for n in grids:
    count=records[n][0]['methods']['fast_pod']['prefixes']['256']['field_exceedances']
    value=records[n][0]['methods']['fast_pod']['prefixes']['256']['max_field_linf']
    ax.annotate(f'{count}/256 exceed',xy=(n,value),xytext=(0,9),textcoords='offset points',
                ha='center',fontsize=12,color=colors['fast_pod'])
fig.savefig(OUT/'final_cost_accuracy.png',dpi=300)
plt.close(fig)

fig,axes=plt.subplots(2,3,figsize=(11,6.2),sharex='col',layout='constrained')
q=np.arange(1,257)
for j,n in enumerate(grids):
    ax=axes[0,j]
    ratios=[]
    for r in records[n]:
        methods=r['methods']
        total={m: sum(methods[m]['offline_components_seconds'].values())+
                  np.cumsum([c['timing']['service_seconds'] for c in methods[m]['cases']])
               for m in ['fast_fom','adaptive']}
        ratios.append(total['fast_fom']/total['adaptive'])
    values=np.array(ratios)
    ax.plot(q,np.median(values,axis=0),color=colors['adaptive'],linewidth=2,label='Median')
    ax.fill_between(q,values.min(axis=0),values.max(axis=0),color=colors['adaptive'],alpha=.2,label='3-run range')
    ax.axhline(1,color='#53616d',linestyle='--',linewidth=1)
    ax.axvline(24,color='#a9b0b5',linestyle=':',linewidth=1)
    ax.set_title(f'n = {n}')
    ax.set_ylim(0,6.2)
    if j==0:
        ax.set_ylabel('Cumulative total cost ratio\nFast FOM / adaptive')
        ax.legend(fontsize=11,loc='upper left')
    ax=axes[1,j]
    cases=records[n][0]['methods']['adaptive']['cases']
    ranks=np.array([c['rank_after'] for c in cases])
    triggered=np.array([c['trigger'] for c in cases])
    # Accuracy/state traces agree across repeats; equality is explicitly checked.
    for other in records[n][1:]:
        assert [c['rank_after'] for c in other['methods']['adaptive']['cases']] == ranks.tolist()
        assert [c['trigger'] for c in other['methods']['adaptive']['cases']] == triggered.tolist()
    ax.step(np.r_[0,q],np.r_[8,ranks],where='post',color=colors['fast_pod'],linewidth=1.8,label='Basis rank')
    ax.scatter(q[triggered],ranks[triggered],s=22,color=colors['adaptive'],zorder=3,label='FOM + update')
    ax.axvline(24,color='#a9b0b5',linestyle=':',linewidth=1)
    ax.set_ylim(7,27)
    ax.set_yticks([8,12,16,20,24,26])
    ax.set_xticks([1,128,256])
    ax.set_xlabel('Queries already served, Q')
    if j==0:
        ax.set_ylabel('Adaptive basis rank')
        ax.legend(fontsize=11,loc='center right')
fig.savefig(OUT/'final_online_trace.png',dpi=300)
plt.close(fig)
manifest={'origin':'External plotting of native-executed frozen evaluation results',
          'new_models_or_scientific_solves':0,'input_sha256':inputs,
          'figures':['final_cost_accuracy.png','final_online_trace.png'],
          'note':'Timing bands are min/max of three repetitions of the same frozen parameter stream.'}
(OUT/'final_figure_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'figures':manifest['figures'],'input_runs':9,'new_solves':0}))
