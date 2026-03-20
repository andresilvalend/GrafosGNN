# BCCS Theory v4 — Corrected Formulation

## 1. Problem Definition

**Definition 1 (BCCS: Budgeted Connected Case Segmentation).**
Let G = (V, E) be an undirected graph with edge-level fraud labels y: E → {0,1}.
Let F = {e ∈ E : y(e) = 1} be the set of fraud edges.
Let s: E → [0,1] be a risk scorer, and k ∈ (0,1] a selection fraction.
Define the **top-k subgraph** G_k = (V_k, E_k), where E_k contains the
⌈k·|E|⌉ highest-scored edges and V_k their endpoints.

A **case assignment** is a partition P = {C_1, ..., C_m} of V_k.
For each case C_i, the **induced edge set** is E(C_i) = {(u,v) ∈ E : u,v ∈ C_i}.
The **presented edge set** is P(C_i) = top-B edges of E(C_i) by score
(the analyst reviews at most B edges per case).

**Fraud coverage**: Cov(P) = |{e ∈ F : e ∈ P(C_i) for some i}|

**Objective**: max_P Cov(P) subject to |P(C_i)| ≤ B for all i.

**Remark.** The budget constrains the *presented* edges, not the induced subgraph.
This models the operational constraint: an analyst can review at most B edges per case.

---

## 2. NP-Completeness

**Theorem 1.** BCCS is NP-complete.

**Proof.** [Same reduction from MIS — unchanged, correct as is.]

**Corollary 1.** Unless P = NP, BCCS cannot be approximated within |V|^{1-ε}
for any ε > 0 (via Zuckerman 2007).

---

## 3. Instance-Specific Gap Analysis (REPLACES old Theorems 2-5)

We do NOT claim approximation to OPT in the complexity-theoretic sense.
Instead, we provide computable diagnostic quantities that bound the gap
between HGS and any feasible solution on a given instance.

### 3.1 WCC Coverage as Diagnostic Upper Bound

**Observation 1 (WCC-COV).** Define:
WCC-COV(G, G_k, F) = |{e ∈ F : both endpoints in the same WCC of G_k}|

Any algorithm that partitions V_k and respects WCC boundaries (i.e., never
merges nodes from different WCCs) covers at most WCC-COV fraud edges.
HGS is such an algorithm, so HGS ≤ WCC-COV.

**This is NOT a bound on OPT.** OPT may merge nodes from different WCCs
(using edges outside G_k) to cover additional fraud edges.

### 3.2 Gap Characterization

**Theorem 2 (Instance-Specific Gap Bound).**
For any instance (G, F, k, B), define:
- cross = |{e ∈ F : endpoints in different WCCs of G_k}|
- L_cut = |{e ∈ F : endpoints in same WCC of G_k, but split by HGS's Leiden step}|

Then: OPT - HGS ≤ cross + L_cut

**Proof.** Fraud edges not covered by HGS are either:
(a) cross-WCC: endpoints in different WCCs of G_k → count ≤ cross
(b) intra-WCC but Leiden-split: endpoints in same WCC but placed in different
    Leiden subcases → count = L_cut
These sets are disjoint. OPT covers at most cross additional edges from (a)
and L_cut from (b). ∎

**Definition (Gap fraction).** δ = (cross + L_cut) / |F|

**Interpretation**: δ is a computable per-instance diagnostic.
On instances where δ is small, HGS is provably close to any feasible solution.
On instances where δ is large, HGS may be far from optimal — and the theory
tells us WHY (cross-WCC structure or Leiden fragmentation).

This is NOT an approximation ratio. It is an instance diagnostic.

### 3.3 Budget-Feasibility Rate

**Definition 2.** An instance is budget-feasible if all WCCs of G_k have
|E(WCC_j)| ≤ B (no Leiden splitting needed).

**Proposition 1.** On budget-feasible instances, L_cut = 0 and HGS covers
exactly WCC-COV fraud edges. The gap reduces to cross alone.

BFR = fraction of WCCs that are budget-feasible.

### 3.4 Removed Claims

The following claims from v3 are REMOVED because they were either
trivial, incorrect, or misleading:

- "WCC-COV is an upper bound for the theoretical optimum" — FALSE in general
  (OPT can merge WCCs)
- "BTCS dominates WCC-CAP by factor q(C)" — FALSE
  (counterexample: m=150, B=100, l=50 → WCC-CAP covers 50, but l/q=25)
- "BTCS achieves 96-99% of theoretical optimum" — MISLEADING
  (δ is a gap vs OPT, but calling it "approximation ratio" is wrong in the
   complexity-theoretic sense)
- O(K log K) complexity — INCORRECT in general
  (line graph construction can be O(d²_max·K))

---

## 4. Empirical Validation of Gap Bound

| Dataset | k | δ | cross | L_cut | BFR | WCC-COV/|F| |
|---------|---|---|-------|-------|-----|-------------|
| Elliptic | 1% | 0.711 | 5794 | 0 | 1.000 | 0.289 |
| Elliptic | 5% | 0.012 | 0 | 95 | 0.997 | 1.000 |
| Elliptic++ | 1% | 0.248 | 4429 | 4737 | 0.987 | 0.880 |
| Elliptic++ | 5% | 0.127 | 0 | 4685 | 0.997 | 1.000 |
| Bitcoin-OTC | 1% | 0.938 | 3026 | 315 | 0.944 | 0.151 |
| Bitcoin-OTC | 5% | 0.731 | 1136 | 1467 | 0.986 | 0.681 |
| Amazon Fraud | 1% | 0.997 | 8519 | 202606 | 0.000 | 0.960 |
| Amazon Fraud | 5% | 0.973 | 0 | 206102 | 0.000 | 1.000 |
| Libra | 1% | 0.065 | 16 | 13 | 0.999 | 0.964 |
| Libra | 5% | 0.034 | 0 | 15 | 1.000 | 1.000 |

**Key findings:**
- AML graphs (Elliptic k=5%, Libra): δ < 0.07, HGS is near-optimal for the instance
- Non-AML (Amazon): δ ≈ 0.97, theory correctly predicts HGS failure (1 giant WCC)
- k=1% generally has high δ because few fraud edges land in top-k (coverage ceiling)
- The gap is dominated by cross at k=1% and by L_cut at k=5%
