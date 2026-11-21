# A sign-separated spatial residual certificate

Status: local finding with an executed exact-arithmetic checker; intermediate verification requested separately. No novelty or timing improvement is claimed.

## Model and assumptions

Let n be a positive integer, N=n^2, and Delta=1/n. Number cells in row-major order. The four boundary parameters h=(h_left,h_right,h_top,h_bottom) lie independently in [1/5,5]. For each face-neighbor pair the matrix entry is -1. Each diagonal equals the number of face neighbors plus beta_s=Delta/(1/h_s+Delta/2) for each incident boundary face. In particular, the single cell when n=1 has four boundary faces and no neighbors. Assume, as supplied, that every A_h is invertible with entrywise nonnegative inverse. Let A_0 denote the matrix with all four parameters equal to 1/5. Since beta_s increases with h_s, D=A_h-A_0 is a nonnegative diagonal matrix.

For an arbitrary real residual vector r, the discrete error satisfies A_h e=r exactly. The certificate concerns this discrete algebraic error, not continuum discretization error. A floating-point residual used in place of r requires a separate enclosure of its uncertainty.

Fix a partition B_1,...,B_K of the N cells into nonempty disjoint blocks before online evaluation. Write b_k for the indicator vector of B_k. Precompute offline

    w_k = A_0^{-1} b_k,    z = sum_k w_k = A_0^{-1} 1.

These are full cellwise response vectors. Define r_i^+=max(r_i,0), r_i^-=max(-r_i,0), and

    a_k^+ = max_{j in B_k} r_j^+,
    a_k^- = max_{j in B_k} r_j^-,
    c_k = max_{j in B_k} |r_j| = max(a_k^+,a_k^-),
    p = sum_k a_k^+ w_k,
    q = sum_k a_k^- w_k,
    t = sum_k c_k w_k.

The zero residual is included: all coefficients and bounds then vanish.

## Certificate and proof

For every allowed h and every r, componentwise

    -q <= e <= p.

Consequently, with the infinity norm denoting the maximum absolute entry,

    ||e||_infinity <= C(r) := max(||p||_infinity, ||q||_infinity)
                  <= U(r) := ||t||_infinity
                  <= B(r) := ||r||_infinity ||z||_infinity.

Here B is precisely the supplied uniform residual-norm baseline.

Proof. The resolvent identity gives

    A_0^{-1} - A_h^{-1} = A_0^{-1} D A_h^{-1} >= 0

entrywise, because each factor on the right is nonnegative. Therefore 0 <= A_h^{-1} <= A_0^{-1}. Define the nonnegative block envelopes g^+=sum_k a_k^+ b_k and g^-=sum_k a_k^- b_k. By construction 0 <= r^+ <= g^+ and 0 <= r^- <= g^-. Thus

    0 <= u := A_h^{-1} r^+ <= A_0^{-1} g^+ = p,
    0 <= v := A_h^{-1} r^- <= A_0^{-1} g^- = q.

Since e=u-v, it follows that -q <= e <= p. Hence |e_i| <= max(p_i,q_i) and the asserted norm certificate follows. Every w_k is nonnegative, a_k^+ <= c_k and a_k^- <= c_k, so p <= t and q <= t. Finally c_k <= ||r||_infinity and the indicators partition the grid, giving t <= ||r||_infinity z. Taking maxima proves both comparisons. This argument covers the entire continuous parameter box and every positive integer n; finite tests are not used to infer that coverage.

## Position, sign, and cancellation

The responses w_k encode block position, while the two coefficient sets preserve positive and negative residual envelopes separately. Moving a residual within one block without changing its extrema cannot change C. Symmetry can also make different blocks have the same scalar bound. The method therefore resolves location only at the chosen block scale and need not distinguish every pair of source locations.

The estimate uses |u_i-v_i| <= max(u_i,v_i), followed by separate upper bounds. It does not infer |u_i-v_i| <= |p_i-q_i|. The latter implication is false for upper bounds alone: u=1, v=0 and p=q=1 satisfy the upper-bound conditions but would give a false zero estimate. In the executed 4-by-4 checkerboard case, p=q=z for the coarse partition, yet e is nonzero, giving a counterexample to this subtraction rule within the supplied model itself.

If both residual signs are present, the connected-grid irreducible M-matrix has a strictly positive inverse, so both propagated parts are positive at every cell and actual cancellation occurs there. Nevertheless, sign presence and separate upper envelopes do not certify a particular positive amount of cancellation to subtract: no lower bound on either propagated part was computed. A negative part can be arbitrarily small while still having negative entries. The identity |u_i-v_i|=u_i+v_i-2 min(u_i,v_i) shows exactly what additional information would be needed. Certified lower bounds on u and v, or certified responses for the actual parameter and residual, can justify stronger cancellation estimates; subtracting upper bounds cannot. No such stronger estimate is claimed or implemented here.

## Strict gain with an explicit calculation

Take n=2, all h_s=1/5, singleton blocks, and r=(1,1,-1,-1), with the positive cells in the top row. Here beta=2/21 and A_0=L+(4/21)I, where L is the four-cell face-neighbor graph Laplacian. We have L1=0 and Lr=2r. Therefore

    z=(21/4)1,    e=(21/46)r.

Since r^+=(1+r)/2 and r^-=(1-r)/2,

    p=(z+e)/2,    q=(z-e)/2.

It follows that

    actual error = 21/46 = 0.45652173913043476,
    C = (21/4+21/46)/2 = 525/184 = 2.8532608695652173,
    U = B = 21/4 = 5.25,
    C/B = 25/46 = 0.5434782608695652 < 1.

Thus sign separation strictly improves even on the unsigned spatial envelope in this example. C is valid for this same residual throughout the allowed parameter box; the displayed actual error is specifically at h_min.

## Equality and coarse-block limitations

For any grid and partition, let r=c1 with c any real constant. Then C=B=|c| ||z||_infinity. At h=h_min, e=cz, so actual error=C=B. This is an attained equality case, not merely an asymptotic limit. For fixed nonzero c, actual error approaches this equality as h approaches h_min by continuity of the matrix inverse. For n=1 and c=1 at h_min, the common value is 11/8.

For n=4, partition into the four 2-by-2 quadrants and take r_{x,y}=(-1)^(x+y). Every block contains both +1 and -1, hence a_k^+=a_k^-=c_k=1 and p=q=t=z. The certificate equals the baseline, 3569/168 = 21.24404761904762. The executed reference solve at h_min gives actual error 2583/7304 = 0.3536418400876232. Thus block extrema can discard substantial cancellation information, and mixed signs alone do not force a strict gain in this estimator.

## Constructive execution evidence

The self-contained standard-library script is experiments/moonshine_bound.py relative to this workspace. It was actually executed through run_python_script using the project-relative path workspace/experiments/moonshine_bound.py. The tool returned status ok, returncode 0, empty stderr, and JSON results.

All matrices, solves, envelopes, and assertions use fractions.Fraction. Displayed decimals are conversions only; the assertion tolerance is zero. Grid sizes are n=1,2,3,4. Blocks are formed by splitting each coordinate at ceil(n/2), omitting empty blocks. The test set uses all 81 independent parameter combinations in {1/5,1,5}^4 and eight named residual vectors on each grid: zero, constant positive, constant negative, row sign split, checkerboard, corner spike, center spike, and a fixed modular mixed pattern. Some named vectors coincide on the smallest grids, so counts describe tested cases, not necessarily distinct vectors.

Observed output:

- 2,592 tested parameter/residual cases; 648 per grid.
- 1,053 cases with C < B.
- All componentwise and norm coverage assertions passed.
- All C <= U <= B assertions passed.
- Offline response equations and all reference equations passed exactly.
- Partition coverage and the four-face n=1 assembly check passed.
- Strict-gain and equality examples passed their exact fraction assertions.
- Minimum C minus actual error was 0; maximum C/B over nonzero residuals was 1.
- Four offline solve batches and 324 reference solve batches; online_bound contains no solve.

For the n=4 corner and center spikes at h_min, C=6.212967574205299 and B=21.24404761904762 in both cases; actual errors were respectively 1.8898066970856064 and 1.657769009685773. The identical candidate values illustrate the coarse symmetric partition's limited spatial resolution.

## Offline/online separation and numerical limitations

The function offline_precompute solves A_0 W=H for the fixed block indicators and verifies this identity exactly. The function online_bound only computes residual block maxima, weighted sums of stored responses, and maxima over cells. It performs no matrix assembly, factorization, or direct solve. Direct solutions of A_h E=R in main are reference checks only. Solve-count JSON fields describe this code structure, rather than independent runtime instrumentation.

The proof assumes exact responses and an exact residual. This checker meets that assumption for its rational data. Ordinary floating-point precomputation alone is not a rigorous outward certificate: an implementation would need verified response enclosures and outward arithmetic. Certified nonnegative supersolutions Wbar_k satisfying A_0 Wbar_k >= b_k would give a valid upper certificate, but their inflation need not preserve comparison with the exact baseline; that comparison requires separate accounting. If the true residual differs from a computed residual by at most epsilon componentwise, a valid additional uncertainty allowance is epsilon ||z||_infinity, by the same inverse comparison and the triangle inequality.

The checks establish reproducible finite examples, while the algebra establishes continuous-parameter validity. No continuum error bound, novelty result, or timing improvement is asserted. The supplied task file was not edited.
