# Round-two intermediate verification archive

Status: PASSED. This records the completed review of the interval strengthening explicitly supplied by the external project team. No autonomous discovery, novelty, or timing improvement is claimed.

## Review provenance

Tool: verify_overall. Call identifier: moonshine-5726bb2d91bf49e484cdeec3df3217c1. Project: residual-sign-location. Scope: intermediate. Review count: 1 per dimension. Reviewed at: 2026-11-21T14:02:02Z. Blueprint: workspace/residual_interval_proof.md. Returned status: completed; passed: true; overall_verdict: correct; repair_targets: empty. This was the sole round-two formal review attempt.

The tool's aggregate summary was: Overall verification passed: assumption use, calculation correctness, and logical correctness all passed.

## Dimension outcomes

Assumptions: passed, assumption_correct, reviewer assumption-usage-reviewer, confidence 0.97, zero errors and no failed reviewers. The reviewer identified uses for the grid construction, parameter endpoints, inverse positivity, diagonal monotonicity, connectivity, nonnegative envelopes, partition conditions, canonical extrema, and exact arithmetic.

Computation: passed, calculation_correct, reviewer calculation-consistency-reviewer, confidence 0.99, zero errors and no failed reviewers. The reviewer checked the inverse identities, interval subtraction, absolute-endpoint formula, comparison and equality criteria, exact example fractions, all four equations for the asymmetric interior example, the signed-GW counterexample, numerical routines, and counts 1968 and 328. The reviewer explicitly used the supplied source and execution report without claiming an independent execution.

Logic: passed, logic_correct, reviewer logical-chain-reviewer, confidence 0.98, zero errors and no failed reviewers. The reviewer confirmed the inverse-order argument applies to nonnegative vectors, the interval and scalar implications, necessary-and-sufficient equality criterion including zero residuals, connectivity argument for strict positivity, strict-improvement condition, and distinction between finite corroboration and the general proof.

## Reviewed finding

For every integer n>=1 and h in [1/5,5]^4, use the supplied finite-volume matrix with mesh spacing 1/n, face-neighbor entries -1, and diagonal equal to neighbor count plus Delta/(1/h_s+Delta/2) for each incident boundary face. Count all four boundary faces for n=1. Assume invertibility, entrywise nonnegative inverses, and nonnegative diagonal increments as h increases. Let GW and GS be the inverses at the all-1/5 and all-5 parameter endpoints. For a fixed nonempty disjoint exhaustive block partition, require 0<=l_pos<=r_pos<=u_pos and 0<=l_neg<=r_neg<=u_neg.

Writing p=GW u_pos, q=GW u_neg, a=GS l_pos and b=GS l_neg, the interval L=a-q, U=p-b contains e=A_h^{-1}r. Its unsigned certificate is C_interval=max_i max(-L_i,U_i)=max(||L||_infinity,||U||_infinity)<=C_one=max_i max(p_i,q_i). With canonical upper block maxima, C_one is no greater than the unsigned spatial bound or the uniform baseline. Equality C_interval=C_one holds exactly when some cell satisfies p_i=C_one and b_i=0, or q_i=C_one and a_i=0. Canonical same-sign residuals and two vanishing lower envelopes cannot improve this scalar bound. Two nonzero nonnegative lower envelopes imply strict improvement on the connected grid.

The proof uses GS<=A_h^{-1}<=GW separately on each nonnegative residual part. The subtraction is supported by lower information about the opposing sign. It does not subtract two upper bounds or apply inverse ordering directly to signed input.

## Actual execution evidence supplied to the review

The independent checker workspace/experiments/moonshine_interval.py was executed through run_python_script(path='workspace/experiments/moonshine_interval.py', timeout_seconds=60), call moonshine-7b35ed8dc5084ba0974a2164ca9222bd. The tool returned status ok, returncode 0, empty stderr, and JSON stdout. Output is also saved as workspace/experiments/moonshine_interval.json.

All calculations and assertions used Fraction arithmetic with zero tolerance. All 1968 parameter/residual/partition cases passed, including 328 strict improvements. The 82 parameter tuples per grid comprise {1/5,1,5}^4 and the asymmetric strict interior tuple (1/2,1,2,3). Grid n=1 has three residual cases and one partition; n=2 has seven residual cases and three partitions. Thus 82*(3+7*3)=1968. Four residual/partition combinations improve strictly, giving 4*82=328. The constructed counterexample is additional to this count. All 13 reported check flags were true.

For n=2, singleton blocks, and r=(1,1,-1,-1), C_interval=12003/4370, C_one=525/184, and uniform baseline=21/4. At weak h the actual error is 21/46; at h=(1/2,1,2,3) it is 114777/316801. For constant positive residual at weak h, actual=C_interval=C_one=21/4. For one whole-grid block and r=(1,-1,-1,1), both lower envelopes vanish, actual=21/88 at weak h, and both certificates equal 21/4.

The unsafe signed-inverse shortcut is refuted by r=(46/21)(1,-1,1,-1) and h=(1/5,5,1/5,1/5): GW r=(1,-1,1,-1) has norm 1, whereas the actual error is (437,-69,437,-69)/269 with norm 437/269>1. This refutes both componentwise absolute domination by |GW r| and scalar domination by ||GW r||_infinity.

## Evidence boundaries and preserved artifacts

This is a passed local intermediate finding, not a final project-level review. The proof establishes coverage over the continuous parameter box; the finite execution corroborates it. Online evaluation uses stored block responses and arithmetic only; reference and offline solves are permitted. The zero online solve field describes source structure, not runtime instrumentation. Floating-point deployment requires certified response/residual enclosures and outward arithmetic. The certificate concerns discrete algebraic error.

The first-round workspace/residual_proof.md and workspace/experiments/moonshine_bound.py remain preserved. The first-round exact example, 21/46 actual error and 525/184 certificate, was reproduced in the new check. The task file was not edited. The complete round-two mathematical argument and limitations are in workspace/residual_interval_proof.md.
