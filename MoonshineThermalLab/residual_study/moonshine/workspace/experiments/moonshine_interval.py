#!/usr/bin/env python3
# Independent exact checker for the interval supplied by the project team.
# Standard library only. Solves are offline or reference operations.
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import json

def matrix(n, h):
    d = F(1, n)
    beta = [d / (1 / v + d / 2) for v in h]
    A = [[F(0) for _ in range(n*n)] for _ in range(n*n)]
    for y in range(n):
        for x in range(n):
            i = y*n+x
            for yy, xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if 0 <= yy < n and 0 <= xx < n:
                    A[i][yy*n+xx] = F(-1)
                    A[i][i] += 1
            for incident, v in zip((x==0,x==n-1,y==0,y==n-1), beta):
                if incident:
                    A[i][i] += v
    return A

def mv(A, x):
    return [sum((v*w for v,w in zip(row,x)), F(0)) for row in A]

def solve(A, rhs):
    N = len(A)
    M = [list(row)+[F(v)] for row,v in zip(A,rhs)]
    for k in range(N):
        j = next(j for j in range(k,N) if M[j][k])
        M[k], M[j] = M[j], M[k]
        pivot = M[k][k]
        M[k] = [v/pivot for v in M[k]]
        for i in range(N):
            if i != k:
                c = M[i][k]
                M[i] = [v-c*w for v,w in zip(M[i],M[k])]
    answer = [row[-1] for row in M]
    assert mv(A,answer) == list(rhs)
    return answer

def inverse(A):
    N = len(A)
    cols = [solve(A,[F(i==j) for i in range(N)]) for j in range(N)]
    return [list(row) for row in zip(*cols)]

def norm(x):
    return max(abs(v) for v in x)

def offline(n, blocks):
    assert all(blocks) and sorted(i for b in blocks for i in b)==list(range(n*n))
    responses = []
    for h in ((F(1,5),)*4,(F(5),)*4):
        A = matrix(n,h)
        cols = [solve(A,[F(i in b) for i in range(n*n)]) for b in blocks]
        assert all(v > 0 for col in cols for v in col)
        responses.append([list(row) for row in zip(*cols)])
    return responses

def online(r, blocks, W, S):
    # Only extrema and stored-response arithmetic; no matrix assembly or solve.
    rp, rn = [max(v,F(0)) for v in r], [max(-v,F(0)) for v in r]
    lp = [min(rp[i] for i in b) for b in blocks]
    up = [max(rp[i] for i in b) for b in blocks]
    ln = [min(rn[i] for i in b) for b in blocks]
    un = [max(rn[i] for i in b) for b in blocks]
    p,q,a,b = mv(W,up),mv(W,un),mv(S,lp),mv(S,ln)
    L,U = [v-w for v,w in zip(a,q)],[v-w for v,w in zip(p,b)]
    C = max(max(U),max(-v for v in L))
    old = max(max(p),max(q))
    unsigned = max(mv(W,[max(v,w) for v,w in zip(up,un)]))
    baseline = norm(r)*max(sum(row,F(0)) for row in W)
    assert all(lo<=hi for lo,hi in zip(L,U))
    assert C == max(norm(L),norm(U))
    assert 0 <= C <= old <= unsigned <= baseline
    equality = any(v==old and w==0 for v,w in zip(p,b)) or any(v==old and w==0 for v,w in zip(q,a))
    assert (C==old) == equality
    if all(v>=0 for v in r) or all(v<=0 for v in r) or not any(lp+ln):
        assert C==old
    return {'L':L,'U':U,'interval_bound':C,'one_sided_bound':old,
            'unsigned_spatial_bound':unsigned,'uniform_baseline':baseline}

def num(v):
    return {'exact':str(v),'decimal':float(v)}

def record(n,h,r,blocks,est,e):
    return {'n':n,'h_left_right_top_bottom':list(map(str,h)),
            'r':list(map(str,r)),'blocks':blocks,'error_vector':list(map(str,e)),
            'L':list(map(str,est['L'])),'U':list(map(str,est['U'])),
            'actual_error':num(norm(e)),
            **{k:num(est[k]) for k in ('interval_bound','one_sided_bound','unsigned_spatial_bound','uniform_baseline')}}

def main():
    weak, strong = (F(1,5),)*4,(F(5),)*4
    interior = (F(1,2),F(1),F(2),F(3))
    hs = list(product((F(1,5),F(1),F(5)),repeat=4))+[interior]
    examples, total, strict = {},0,0
    for n in (1,2):
        N = n*n
        partitions = [[[0]]] if n==1 else [[[0],[1],[2],[3]],[[0,1],[2,3]],[[0,1,2,3]]]
        raw = {'zero':[0]*N,'positive':[1]*N,'negative':[-1]*N}
        if n==2:
            raw.update(mixed=[1,1,-1,-1],checker=[1,-1,-1,1],spike=[1,0,0,0],irregular=[2,-1,0,-3])
        cases = {name:list(map(F,r)) for name,r in raw.items()}
        caches = [offline(n,blocks) for blocks in partitions]
        estimates = [{name:online(r,blocks,*cache) for name,r in cases.items()} for blocks,cache in zip(partitions,caches)]
        GW,GS = inverse(matrix(n,weak)),inverse(matrix(n,strong))
        if n==1:
            assert matrix(n,weak)[0][0]==F(8,11)
        for h in hs:
            A = matrix(n,h)
            G = inverse(A)  # Reference only.
            assert all(GS[i][j]<=G[i][j]<=GW[i][j] for i in range(N) for j in range(N))
            for name,r in cases.items():
                e = mv(G,r)
                assert mv(A,e)==r
                for k,blocks in enumerate(partitions):
                    est = estimates[k][name]
                    assert all(lo<=v<=hi for lo,v,hi in zip(est['L'],e,est['U']))
                    assert norm(e)<=est['interval_bound']
                    total += 1
                    strict += int(est['interval_bound']<est['one_sided_bound'])
                    if n==2 and k==0 and ((h==weak and name in ('mixed','positive')) or (h==interior and name=='mixed')):
                        key = name+('_interior' if h==interior else '_weak')
                        examples[key] = record(n,h,r,blocks,est,e)
                    if n==2 and k==2 and h==weak and name=='checker':
                        examples['coarse_zero_lower_envelopes'] = record(n,h,r,blocks,est,e)
        if n==2:
            m = estimates[0]['mixed']
            assert m['one_sided_bound']==F(525,184)
            assert m['interval_bound']==F(525,184)-F(81,760)
            assert examples['mixed_weak']['actual_error']['exact']=='21/46'
            assert estimates[0]['positive']['interval_bound']==F(21,4)
    # Construct signed residual from a weak-boundary solution of norm one.
    # Increasing only the right boundary damps its negative cells and can
    # increase the positive response on the unchanged left boundary.
    n = 2
    x = list(map(F,[1,-1,1,-1]))
    AW = matrix(n,weak)
    r = mv(AW,x)
    h = (F(1,5),F(5),F(1,5),F(1,5))
    e = solve(matrix(n,h),r)
    weak_response = solve(AW,r)
    assert weak_response==x and norm(e)>norm(weak_response)
    assert any(abs(v)>abs(w) for v,w in zip(e,weak_response))
    blocks = [[0],[1],[2],[3]]
    est = online(r,blocks,*offline(n,blocks))
    assert all(lo<=v<=hi for lo,v,hi in zip(est['L'],e,est['U']))
    counter = record(n,h,r,blocks,est,e)
    counter.update(weak_signed_response=list(map(str,weak_response)),unsafe_bound=num(norm(weak_response)),
                   refutes='Both componentwise |G_h r| <= |GW r| and norm(G_h r) <= norm(GW r).')
    checks = {name:True for name in ('partition_coverage','offline_response_equations','reference_equations',
        'inverse_ordering','interval_coverage','scalar_coverage','bound_comparison','equality_criterion',
        'same_sign_no_improvement','strict_mixed_improvement','asymmetric_interior','signed_GW_counterexample','n1_four_faces')}
    output = {'attribution':'Interval strengthening supplied by the project team.',
              'arithmetic':'Exact Fraction; tolerance zero; decimals display only.',
              'parameter_cases_per_grid':len(hs),'tested_parameter_residual_partition_cases':total,
              'strict_interval_improvement_cases':strict,'checks':checks,'tests_passed':True,
              'examples':examples,'counterexample':counter,
              'online_solves':0,'online_solves_note':'Structural property of online(), not runtime instrumentation.',
              'scope':'Finite corroboration; continuous coverage requires the proof. No novelty or timing claim.'}
    text = json.dumps(output,indent=2,sort_keys=True)
    Path(__file__).with_suffix('.json').write_text(text+'\n',encoding='utf-8')
    print(text)

if __name__=='__main__':
    main()
