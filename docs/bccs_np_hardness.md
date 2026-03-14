# BCCS: Formal Definition and NP-Hardness Proof

## 1. Problem Definition

**Definition 1 (Budgeted Connected Case Segmentation — BCCS).**
Let $G = (V, E)$ be an undirected graph, $L \subseteq E$ a set of *target edges*,
and $B \in \mathbb{Z}^+$ a *budget*.
A **case assignment** is a partition $\mathcal{P} = \{C_1, \dots, C_m\}$ of $V$ into
pairwise-disjoint, non-empty subsets (called *cases*).

For each case $C_i$, define the **induced edge set**:

$$E(C_i) = \{(u,v) \in E : u \in C_i \text{ and } v \in C_i\}$$

The **coverage** of $\mathcal{P}$ is:

$$\text{Cov}(\mathcal{P}) = \left|\{(u,v) \in L : \exists\, C_i \in \mathcal{P} \text{ with } u, v \in C_i\}\right|$$

The **BCCS optimization problem** is:

$$\max_{\mathcal{P}} \quad \text{Cov}(\mathcal{P}) \qquad \text{s.t.} \quad |E(C_i)| \leq B \quad \forall\, C_i \in \mathcal{P}$$

The **BCCS decision problem** asks: given $(G, L, B, \tau)$, does there exist a partition $\mathcal{P}$ with $|E(C_i)| \leq B$ for all $i$ and $\text{Cov}(\mathcal{P}) \geq \tau$?

---

**Interpretation in AML transaction monitoring.**
In anti-money laundering (AML) systems, $G$ represents the full transaction graph, $L$ is the set of top-$k$ highest-risk edges identified by a GNN scorer, and $B$ limits the number of edges an analyst can review in a single investigation case. BCCS asks how to group transactions into bounded investigation cases to maximize the number of flagged edges that are actually reviewable.

---

## 2. NP-Completeness

**Theorem 1.** *BCCS is NP-complete.*

**Proof.**

### Membership in NP

Given a partition $\mathcal{P} = \{C_1, \dots, C_m\}$, we verify in $O(|V| + |E|)$ time:

1. Build a node-to-case lookup table in $O(|V|)$.
2. Scan all edges to compute $|E(C_i)|$ per case and count covered target edges.
3. Verify $|E(C_i)| \leq B$ for all $i$ and $\text{Cov}(\mathcal{P}) \geq \tau$.

Hence BCCS $\in$ NP.

### NP-Hardness (Reduction from Maximum Independent Set)

We reduce from **Maximum Independent Set (MIS)**, which is NP-hard (Karp, 1972):

> **MIS.** Given a graph $H = (V_H, E_H)$ and integer $k$, does $H$ contain an independent set of size $\geq k$?

**Construction.** Given a MIS instance $(H, k)$, construct the following BCCS instance $(G, L, B, \tau)$:

1. **Add a goal node.** Let $g$ be a new node not in $V_H$. Set $V = V_H \cup \{g\}$.

2. **Edges.** $E = E_H \cup \{(v, g) : v \in V_H\}$. That is, keep all original edges and connect every node in $V_H$ to $g$.

3. **Target edges.** $L = \{(v, g) : v \in V_H\}$. Only the edges to $g$ are targets.

4. **Budget.** $B = k$.

5. **Threshold.** $\tau = k$.

The construction runs in $O(|V_H| + |E_H|)$ time.

**Intuition.** Covering a target edge $(v, g)$ requires $v$ and $g$ in the same case. Since $g$ is in a single case, all "covered" nodes share that case with $g$. The non-target edges $E_H$ between these nodes consume budget, so only independent sets fit within budget $k$.

**Forward direction ($\Rightarrow$):** Suppose $H$ has an independent set $S \subseteq V_H$ with $|S| = k$.

Define the partition: $C_1 = S \cup \{g\}$, and each remaining node in $V_H \setminus S$ forms a singleton case.

- **Budget of $C_1$:** The induced edges are $E_H(S) \cup \{(v,g) : v \in S\}$. Since $S$ is independent, $E_H(S) = \emptyset$. So $|E(C_1)| = |S| = k = B$. ✓
- **Budget of singletons:** $0$ edges each. ✓
- **Coverage:** Each $v \in S$ is co-located with $g$, so all $k$ target edges $(v,g)$ are covered. $\text{Cov}(\mathcal{P}) = k = \tau$. ✓

**Backward direction ($\Leftarrow$):** Suppose a partition $\mathcal{P}$ achieves $\text{Cov}(\mathcal{P}) \geq k$.

Let $C_g$ be the case containing $g$. Let $S = C_g \cap V_H$ (the non-goal nodes in $g$'s case). A target edge $(v,g)$ is covered if and only if $v \in S$, so $\text{Cov}(\mathcal{P}) = |S| \geq k$.

The induced edges of $C_g$ are:

$$E(C_g) = E_H(S) \cup \{(v,g) : v \in S\}$$

so $|E(C_g)| = |E_H(S)| + |S|$. The budget constraint gives:

$$|E_H(S)| + |S| \leq B = k$$

Since $|S| \geq k$, we get $|E_H(S)| \leq k - |S| \leq 0$. Therefore $|E_H(S)| = 0$ (no edges of $H$ among $S$) and $|S| = k$. The set $S$ is an independent set of size $k$ in $H$. ✓

This completes the reduction. $\blacksquare$

---

## 3. Consequences

### 3.1 Inapproximability

The reduction from MIS preserves the objective value exactly ($\text{Cov} = |S|$). Therefore, any $\alpha$-approximation for BCCS yields an $\alpha$-approximation for MIS. By the celebrated result of Zuckerman (2007), MIS cannot be approximated within a factor of $|V|^{1-\varepsilon}$ for any $\varepsilon > 0$ unless P = NP.

**Corollary 1.** *Unless P = NP, BCCS cannot be approximated within $|V|^{1-\varepsilon}$ for any $\varepsilon > 0$.*

This worst-case bound is very strong, but applies to adversarial instances. Real-world AML graphs exhibit structure (temporal locality, natural communities) that makes the problem far more tractable in practice.

### 3.2 Connection to Maximum Coverage

BCCS also relates to the **Maximum Coverage Problem** (MCP). In settings where each case can be viewed as a "set" of edges it covers, the BCCS optimizer must select which target edges to cover within the budget, analogous to selecting sets in MCP. Feige (1998) showed that MCP cannot be approximated beyond a ratio of $1 - 1/e \approx 0.632$ unless P = NP.

### 3.3 Practical Implications

Despite worst-case NP-hardness, our experimental results show that the hierarchical WCC + Leiden heuristic (BTCS) achieves **94–97% of the upper bound** (NoBudget WCC coverage) at $k = 1\%$ on the AML100k and AML1M datasets. This suggests that real-world AML transaction graphs possess structure (e.g., natural community boundaries that align with the budget) that makes the problem tractable in practice, even though worst-case instances are intractable.

---

## 4. References

- Karp, R. M. (1972). Reducibility among combinatorial problems. In *Complexity of Computer Computations* (pp. 85–103). Plenum Press.
- Feige, U. (1998). A threshold of ln n for approximating set cover. *Journal of the ACM*, 45(4), 634–652.
- Zuckerman, D. (2007). Linear degree extractors and the inapproximability of max clique and chromatic number. *Theory of Computing*, 3(1), 103–128.
- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports*, 9(1), 5233.
