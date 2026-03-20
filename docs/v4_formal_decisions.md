# Paper v4 — Formal Decisions Document

## Decision 1: Problem Formulation

**BCCS stays as node partition**, but with explicit "presentation budget" refinement.

**Definition (BCCS-P: Budgeted Connected Case Segmentation with Presentation).**
- Input: Graph G=(V,E), fraud edges F ⊆ E, scorer s: E→[0,1], fraction k, budget B
- A **case assignment** is a partition P = {C_1,...,C_m} of V_k (nodes in top-k subgraph)
- For each case C_i, the **induced edge set** E(C_i) = {(u,v) ∈ E : u,v ∈ C_i}
- The **presented edges** P(C_i) = top-B edges of E(C_i) by score (analyst workload)
- **Fraud coverage**: Cov(P) = |{e ∈ F : e ∈ P(C_i) for some i}|
- **Objective**: max_P Cov(P) s.t. |P(C_i)| ≤ B for all i

**Rationale**: This matches what HGS actually does — partition nodes, then present top-B edges per case. The budget constrains what the analyst sees, not the mathematical partition.

**Key consequence**: Two coverage metrics naturally arise:
- **Partition coverage** = |{e ∈ F : both endpoints in same case}| / |F|
- **Presented coverage** = |{e ∈ F : e in some P(C_i)}| / |F|
- Presented ≤ Partition (budget cap drops some fraud edges)
- The paper reports **presented coverage** as the primary metric (operational)

## Decision 2: What is L (target set)?

**L = F = fraud edges** (ground truth labels y=1).

NOT top-k edges. The top-k edges define the working subgraph G_k; the fraud edges F define the optimization target.

Rationale: This is what evaluate_cases_generic() measures, what the theory validation computes, and what matters operationally.

## Decision 3: Metrics (clean separation)

| Metric | Definition | Measures |
|--------|-----------|----------|
| **FraudCoverage** | \|{e ∈ F : e ∈ ∪P(C_i)}\| / \|F\| | How many fraud edges the analyst will see |
| **Purity** | \|{e ∈ ∪P(C_i) : e ∈ F}\| / \|∪P(C_i)\| | Fraction of presented edges that are fraud |
| **Yield@B** | For each case, \|P(C_i) ∩ F\| / B | Fraud density per case (analyst efficiency) |
| **BFR** | Fraction of WCCs with \|E(C_i)\| ≤ B | How often Leiden splitting is needed |

## Decision 4: Theoretical claims (reduced ambition)

### KEEP:
- **Theorem 1**: NP-completeness via MIS reduction ✓ (correct)
- **Theorem 4** (renumber as Theorem 2): Gap characterization
  - BTCS-gap ≤ cross + L_cut (correct, proved)
  - Present as "instance-specific gap bound", NOT "approximation ratio"
  - δ = (cross + L_cut)/|F| is a diagnostic, not an approx ratio
- **Proposition**: BFR empirical observation

### REMOVE:
- **Theorem 2** (WCC-COV upper bound): demote to Observation (trivial)
- **Theorem 3** (multiplicative gain over WCC-CAP): REMOVE (counterexample kills it)
- **Theorem 5** (optimality on budget-feasible): simplify to Corollary of gap bound

### NEW framing:
- "We prove NP-completeness and strong inapproximability (|V|^{1-ε})"
- "Despite worst-case hardness, we provide an instance-specific computable gap bound"
- "On real AML graphs, the gap is empirically small (δ < 0.07)"
- NO claims about "X% of theoretical optimum"

## Decision 5: Libra Bank protocol

- **Main table**: ALL Libra results use leakage-free score
- **Case study** (separate subsection): side-by-side leaked vs leak-free
- **Explicit**: score construction formula in paper
- **Key finding**: High FraudCoverage (0.935) + Low Purity (0.064) = score quality matters

## Decision 6: Complexity

- Drop O(K log K) claim
- Report: O(K log K) for sort + WCC, plus O(|E_L|) for line graph construction
  where |E_L| can be O(d²_max · K) in worst case
- Empirical timing table shows linear scaling in practice

## Decision 7: Baselines in main table

ALL 6 methods in main table: B0_Random, B1_WCC, B2_Louvain, B4_TempWCC, B5_HubWCC, HGS
Explicit discussion of:
- Bitcoin-OTC: Louvain beats HGS at k=5% (explain why)
- Elliptic: TempWCC = WCC (temporal doesn't help — edges already well-clustered)
- Amazon: everything fails (giant component, theory predicts this)
