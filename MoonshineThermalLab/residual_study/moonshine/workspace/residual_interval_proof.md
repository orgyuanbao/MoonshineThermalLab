# Two-sided residual interval: independent check of the team-supplied strengthening

Status: derived and tested with exact rational arithmetic; one intermediate verification is requested separately. The proposed interval was explicitly supplied by the external project team. No autonomous discovery, novelty, or timing improvement is claimed.

## Prior evidence and preserved files

The existing workspace/residual_proof.md and workspace/experiments/moonshine_bound.py are preserved. The first-round execution reported 2592 cases and, for n=2 with singleton blocks and r=(1,1,-1,-1), actual error 21/46, sign-separated bound 525/184, and uniform baseline 21/4 at the weak endpoint. Retrieved session evidence includes the successful three-dimensional intermediate review moonshine-a44344345b584ef4afcd95f256463173. An earlier research-log summary preceded that successful review.

## Model and envelopes

Let n>=1 be an integer, N=n^2, Delta=1/n, and h=(h_left,h_right,h_top,h_bottom) belong to [1/5,5]^4. Number cells in row-major order. A_h has off-diagonal -1 for face neighbors and zero for other distinct cells. Each diagonal is its face-neighbor count plus beta_s=Delta/(1/h_s+Delta/2) for each incident boundary face. All four faces are counted when n=1. Assume every A_h is invertible with entrywise nonnegative inverse, as supplied. Increasing h adds a nonnegative diagonal. Write A_W=A_(1/5,1/5,1/5,1/5), A_S=A_(5,5,5,5), G_h=A_h^{-1}, GW=A_W^{-1}, and GS=A_S^{-1}. The exact discrete error is e=G_h r for any real residual vector r.

Fix a partition into nonempty disjoint blocks B_k covering all cells. Define r_pos=max(r,0) and r_neg=max(-r,0) componentwise. Canonical blockwise envelopes take the minimum and maximum of each part over each block: l_pos, u_pos, l_neg, u_neg. Zeros must be included in those extrema. The required conditions are

    0 <= l_pos <= r_pos <= u_pos,
    0 <= l_neg <= r_neg <= u_neg.

The interval proof also applies to arbitrary envelopes satisfying these conditions, without requiring exact block extrema. Nonnegativity of the lower envelopes matters: if supplied lower bounds are negative, replace them componentwise by their maximum with zero before using GS. The comparison with the canonical unsigned spatial bound below uses the canonical upper block maxima, not arbitrarily inflated upper envelopes.

## Interval and scalar certificate

Set p=GW u_pos, q=GW u_neg, a=GS l_pos, and b=GS l_neg. The team-supplied interval is

    L=a-q,    U=p-b.

Then, for every admissible h,

    L <= e <= U,
    ||e||_infinity <= C_interval := max_i max(-L_i,U_i)
                    = max(||L||_infinity,||U||_infinity)
                    <= C_one := max_i max(p_i,q_i).

For canonical upper envelopes, put c_k=max_{j in B_k}|r_j|, t=GW sum_k c_k 1_Bk, and z=GW 1. The complete comparison is

    ||e||_infinity <= C_interval <= C_one <= ||t||_infinity
                    <= ||r||_infinity ||z||_infinity.

C_one is the first-round sign-separated certificate, formed from upper bounds on the two nonnegative propagated parts. The unsigned spatial block maximum certificate is ||t||_infinity. Both comparisons are included to distinguish these meanings of a one-sided block bound.

Proof. The identities

    GW-G_h = GW (A_h-A_W) G_h >= 0,
    G_h-GS = G_h (A_S-A_h) GS >= 0

prove 0<=GS<=G_h<=GW entrywise. Both parameter endpoints are used. For each sign, positivity and envelope domination imply GS l_sign <= G_h r_sign <= GW u_sign. Subtracting the negative interval from the positive interval gives L<=e<=U. In particular, 0<=a<=p, 0<=b<=q, and -q<=L<=U<=p. For any real interval [L_i,U_i], the largest absolute value is max(-L_i,U_i); because L_i<=U_i, this also equals max(|L_i|,|U_i|). Taking the maximum over cells proves the scalar formula. Since U_i=p_i-b_i<=p_i and -L_i=q_i-a_i<=q_i, C_interval<=C_one. Finally the canonical positive and negative block maxima are each at most c_k, which is at most ||r||_infinity. Positivity of GW gives p,q<=t<=||r||_infinity z. This proves the entire chain over the continuous parameter box, independently of finite tests.

## Strictness and its limits

Let C=C_one. Since every p_i,q_i is at most C and a_i,b_i are nonnegative, the exact equality criterion is

    C_interval=C if and only if there exists i with
    (p_i=C and b_i=0) or (q_i=C and a_i=0).

Indeed, the finite maximum of p_i-b_i and q_i-a_i equals C exactly when one of these terms equals C; a nonnegative subtraction can attain C only under the displayed conditions. This includes r=0. Interval shrinkage alone therefore does not imply a smaller scalar certificate.

For canonical extrema, a same-sign residual gives C_interval=C_one: when r>=0, q=b=0 and U=p; when r<=0, p=a=0 and -L=q. Lower information can narrow the other interval endpoint but cannot lower the maximum absolute endpoint. This says nothing against an improvement of C_one over the uniform baseline due to spatial localization. If both lower envelopes vanish, the entire interval equals the old interval [-q,p]. A block containing both signs has both canonical lower coefficients zero; so does a block containing a zero when considering either part.

On the connected grid GS is strictly positive. To see this, a column x=GS e_j is nonnegative. If x_i=0, the equation at i contradicts its positive right-hand side when i=j; otherwise its nonpositive neighbor sum must be zero, forcing all neighbors to zero. Connectedness propagates to j and gives a contradiction. Thus any nonzero nonnegative lower envelope has a strictly positive propagated response at every cell. If both l_pos and l_neg are nonzero, both a and b are strictly positive, so C_interval<C_one. With only one nonzero lower envelope the exact equality criterion determines whether the unchanged side still attains the old maximum. Mixed signs alone are insufficient.

For u=G_h r_pos and v=G_h r_neg, actual cancellation satisfies u_i+v_i-|u_i-v_i|=2 min(u_i,v_i)>=2 min(a_i,b_i). This is a justified quantitative cancellation allowance when both lower responses are positive. The interval uses lower information on the opposing sign; it never subtracts two upper bounds. Its endpoints may be conservative because upper and lower responses use different parameter endpoints and need not be simultaneously attained.

## Executed exact examples

The new independent standard-library script workspace/experiments/moonshine_interval.py was written and actually executed using run_python_script(path='workspace/experiments/moonshine_interval.py', timeout_seconds=60). Tool call moonshine-7b35ed8dc5084ba0974a2164ca9222bd returned status ok, returncode 0, empty stderr, and JSON stdout. The script also saves workspace/experiments/moonshine_interval.json. All assertions use fractions.Fraction with zero tolerance; decimals are display only.

For n=2, singleton blocks, r=(1,1,-1,-1), write H for the four-cell graph Laplacian. At the weak endpoint A_W=H+(4/21)I, and at the strong endpoint A_S=H+(20/9)I. Since H1=0 and Hr=2r, GW1=(21/4)1, GWr=(21/46)r, GS1=(9/20)1, and GSr=(9/38)r. Therefore p has entries 525/184 in the positive row and 441/184 in the negative row, while b has entries 81/760 and 261/760 respectively. Consequently

    C_interval=525/184-81/760=12003/4370=2.7466819221967964,
    C_one=525/184=2.8532608695652173,
    unsigned spatial bound=uniform baseline=21/4.

The exact interval vectors are L=(-8973,-8973,-12003,-12003)/4370 and U=(12003,12003,8973,8973)/4370. At h=(1/5,1/5,1/5,1/5), actual error=21/46. At the asymmetric strict interior point h=(1/2,1,2,3), the exact error vector is (114777/316801,110495/316801,-95718/316801,-278180/950403), with norm 114777/316801=0.3622999927399219. The same certificates cover both cases.

For n=2, r=(1,1,1,1), and weak h, L=(9/20)1, U=(21/4)1, and actual=C_interval=C_one=21/4. No bound valid at this attained equality case can be strictly smaller than the actual error. For n=2, a single block containing all cells, r=(1,-1,-1,1), and weak h, both lower envelopes vanish. Actual error is 21/88, while C_interval=C_one=baseline=21/4.

## Counterexample to applying GW directly to a signed residual

Let n=2, x=(1,-1,1,-1), r=A_W x=(46/21)x, and h=(1/5,5,1/5,1/5). Then GW r=x has norm 1. The actual error is e=(437,-69,437,-69)/269, with norm 437/269=1.6245353159851301>1. Row symmetry reduces its equations to

    (25/21)e_left-e_right=46/21,
    -e_left+(139/63)e_right=-46/21.

The displayed solution satisfies both equations exactly. Thus both |G_h r|<=|GW r| componentwise and ||G_h r||_infinity<=||GW r||_infinity are false. Inverse entrywise ordering cannot be applied directly to signed input. The valid interval still covers this example: its bound is 4001/665, the one-sided bound is 25/4, and the uniform baseline is 23/2. This counterexample refutes the unsafe shortcut, not the team-supplied interval.

## Test scope and implementation limits

The test set uses n=1,2 and 82 parameter tuples per grid: all 81 combinations in {1/5,1,5}^4 plus (1/2,1,2,3). At n=1 the single partition and residuals 0,1,-1 give 246 cases. At n=2, three partitions (singletons, two rows, and the whole grid) and seven residuals (zero, constant positive, constant negative, row split, checkerboard, corner spike, and (2,-1,0,-3)) give 1722 cases. Total: 1968. All coverage, comparison, reference-equation, inverse-ordering, partition, equality-criterion, and n=1 four-face checks passed. There were 328 strict interval improvements: 82 parameter tuples times three qualifying singleton residuals (row split, checkerboard, irregular) and one qualifying two-row residual (row split). The constructed signed-GW counterexample was an additional check outside that count.

Offline, store GW 1_Bk and GS 1_Bk for each block. Online, compute block extrema, linear combinations of stored responses, and maxima. The script's online() contains no assembly or solve. Its printed zero online solve count describes code structure, not independent runtime instrumentation. Exact residuals and responses are assumed. Floating-point deployment needs certified response and residual enclosures and outward arithmetic, using lower response enclosures for subtracted lower contributions and upper response enclosures for upper contributions. For residual uncertainty ||r-r_computed||_infinity<=epsilon, one safe extra scalar allowance is epsilon||GW1||_infinity. This concerns discrete algebraic error only, not continuum discretization error. The finite tests corroborate the proof and do not establish continuous-parameter coverage by sampling.

The task file and first-round artifacts were not changed. The intermediate review outcome will be archived separately in workspace/residual_interval_verification.md, including any inconclusive result.
