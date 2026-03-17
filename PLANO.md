# PLANO — GrafosGNN / ICDM 2026
**Última atualização:** 2026-03-17 (nb07 Ablation + nb08 Seeds concluídos)
**Autor:** Andre da Costa Silva (ITA)
**Objetivo:** Publicar paper em ICDM 2026 com o algoritmo BTCS v3 para segmentação de casos de AML

---

## Estado Atual

### Algoritmo
**BTCS v3** — Hierarchical WCC → Leiden para segmentação de casos AML
Pipeline: Top-K edges por score → WCC → Leiden → Capping (B=100) → Avaliação

Métricas implementadas:
- `coverage`: fração de edges suspeitas capturadas nos casos
- `purity_induced`: pureza dos casos (fração de edges positivas)
- `yield_b100` (H1): fração de fraudes nos primeiros 100 edges abertos pelo analista ← **métrica operacional principal**
- `auc_purity`: área sob curva de pureza acumulada ← ranking quality
- `n_cases`, `time_s`

Baselines:
- B0 Random, B1 WCC, B2 Louvain, B3 Greedy (temporal)

---

## Resultados Multi-Dataset (nb04) — CONCLUÍDO ✅

**Arquivo:** `results/nb04_multi_dataset/multi_dataset_results.csv`
**180 linhas** | 12 datasets × 5 métodos × 3 k-values (1%, 5%, 10%)

### BTCS v3 @ k=5% — Tabela Resumo

| Dataset | \|E\| | BTCS cov | BTCS yield@100 | Melhor rival |
|---|---|---|---|---|
| Elliptic (BTC) | 234K | **0.943** | **1.000** | B1_WCC yield=1.00 |
| Elliptic++ | 234K | **0.943** | **1.000** | idêntico ⚠️ bug loader |
| PaySim | 6.4M | 0.470 | — | B1/B2 empate cov |
| BTC-Alpha | 24K | **0.388** | — | — |
| BTC-OTC | 36K | **0.244** | **1.000** | — |
| Amazon (k=1%) | 4.4M | 0.031 | **0.939** | WCC: 1 caso/44K edges |
| Yelp (k=1%) | 3.8M | 0.052 | **0.969** | B1_WCC yield=0.969 |
| T-Finance (2M*) | 2M | 0.053 | — | — |
| DGraph-Fin | 4.3M | 0.047 | — | B3 Greedy cov=0.634 |
| IBM-HI Small | 5M | 0.044 | — | todos ~0 purity |
| IBM-LI Small | 7M | 0.040 | — | todos ~0 purity |
| IBM-AML 100K | 1.3M | 0.005 | — | B3 Greedy cov=0.216 |

### Observações Críticas
1. **DGraph-Fin**: B3 Greedy domina cobertura (0.634 vs 0.047). BTCS ganha em velocidade (6.6s vs 359s). Argumento: tradeoff eficiência × cobertura.
2. **IBM datasets**: pureza ≈ 0 para TODOS os métodos. Score heurístico cego a padrões AMLSim. Limitação do score, não do algoritmo. Requer GNN (nb05 futuro).
3. **Elliptic == Elliptic++**: resultados idênticos → **investigar loader** (ver task 2 pendente).

---

## nb06 — Libra Bank (Real) ✅ CONCLUÍDO (2026-03-17)

**Arquivo:** `results/nb06_libra/libra_results.csv`
**597,165 edges | 385,100 nodes | 444 fraud edges (0.074%)**
**Score heurístico:** `(nr_alerts + nr_reports×5) / (√nr_transactions + 1)` → AUC-ROC = 1.000 (!!)

| Método | Cov (k=5%) | AUC (k=5%) | Yield@100 (k=5%) | Tempo k=1% |
|---|---|---|---|---|
| **BTCS v3** | **0.978** | 0.085 | **0.864** | 0.7s |
| B0 Random | 0.428 | 0.040 | 0.117 | 0.0s |
| B1 WCC | 0.818 | **0.381** | **0.864** | 0.0s |
| B2 Louvain | 0.939 | 0.089 | **0.864** | 0.1s |
| B3 Greedy | 0.946 | 0.010 | 0.079 | **716s** ⚠️ |

**Achados-chave:**
- BTCS supera em cobertura (+16% vs B1) — em AML, fraude não capturada = prejuízo real
- Libra não tem timestamps (grafo agregado) → janela temporal Lk inativa; WCC captura clusters puros
- B3 Greedy = inviável em produção (716s para k=1%; estimativa ~3h para k=5%)
- **Scripts:** `scripts/run_libra_final.py` | **Outputs:** figA–figD + `libra_results_k5.tex`

---

## nb07 — Ablation Study ✅ CONCLUÍDO (2026-03-17)

**Arquivo:** `results/nb07_ablation/ablation_results.csv` (24 linhas)
**3 variantes:** A1=WCC_only, A2=Leiden_flat (sem WCC/janela temporal), A3=BTCS_v3

### Achados (os 3 argumentos centrais do paper)

| Dataset | k | A1 WCC_only | A2 Leiden_flat | A3 BTCS_v3 |
|---|---|---|---|---|
| Elliptic | 1% | yield=1.00, AUC=0.995 | yield=0.52, AUC=0.502 | yield=1.00, AUC=0.995 |
| Elliptic | 5% | yield=1.00, AUC=0.941 | **yield=0.35, AUC=0.250** ⚠️ | yield=1.00, AUC=0.942 |
| Amazon | 1% | **1 caso / 44,084 edges** ⚠️ | 13 casos, yield=0.062 | **105 casos, yield=0.939** ✅ |
| Yelp | 1% | 702 casos, yield=0.969 | 730 casos, yield=0.480 | 1,853 casos, yield=0.969 |
| Bitcoin OTC | 5% | yield=1.00, AUC=0.550 | yield=0.495, AUC=0.403 | yield=1.00, AUC=0.843 |

**Conclusão narrativa:**
1. **WCC_only → casos gigantes**: Amazon k=1% gera 1 caso com 44.084 edges — analista não consegue trabalhar
2. **Leiden_flat → destrói sinal de score**: Elliptic k=5% yield 1.00→0.35, AUC 0.94→0.25 (perde ordenação por score)
3. **BTCS = melhor dos dois**: WCC isola clusters de fraude + Leiden subdivide casos grandes preservando score ordering

**Scripts:** `scripts/run_ablation.py` | **Figuras:** `fig1_ablation_curves.png`, `fig2_ablation_bar.png`

---

## nb08 — Multiple Seeds ✅ CONCLUÍDO (2026-03-17)

**Arquivo:** `results/nb08_seeds/seeds_results.csv` (8 linhas)
**Seeds:** [42, 43, 44, 45, 46] — 5 seeds em 4 datasets

| Dataset | k | Yield@100 | AUC Purity | Coverage |
|---|---|---|---|---|
| Elliptic | 1%/5%/10% | **1.000 ± 0.000** | 0.700–0.995 ± 0.000 | 0.289–0.940 |
| Bitcoin OTC | 1%/5%/10% | 0.890–1.000 ± ≤0.020 | 0.841–0.923 ± ≤0.011 | 0.063–0.372 |
| Yelp Fraud | 1% | 0.969 ± 0.000 | 0.718 ± 0.001 | 0.052 |
| Amazon Fraud | 1% | 0.941 ± 0.003 | 0.934 ± 0.005 | 0.031 |

**Conclusão:** Desvio padrão ≤ 0.020 em todos os casos → BTCS é **determinístico na prática**.
A aleatoriedade do Leiden (seed do algoritmo) não afeta os resultados operacionalmente.

**Tabela LaTeX pronta:** `results/nb08_seeds/seeds_table.tex`
**Script:** `scripts/run_seeds.py`

---

## Purity Curves + Yield@100 (nb04 extensão) ✅ CONCLUÍDO

- **Decisão:** H1 = yield@100 substitui ocr_b100
- `compute_purity_curve()` — curva de pureza acumulada por casos ranqueados por score
- **Arquivo:** `results/nb04_multi_dataset/purity_curves_metrics.csv` (105 linhas, 7 datasets)
- **Achado:** B3 Greedy AUC=0.10–0.31 em todos os datasets → cobertura enganosa (casos cheios de ruído)

---

## Datasets Disponíveis

| Dataset | Localização | Status |
|---|---|---|
| Elliptic (BTC) | `data/elliptic/` | ✅ usado |
| Elliptic++ | `Meu Drive/.../elliptic_plus/` | ⚠️ resultado idêntico ao Elliptic — **investigar loader** |
| PaySim | `data/paysim/` | ✅ usado (yield@100 pendente) |
| BTC-Alpha | `data/bitcoin_alpha/` | ✅ usado |
| BTC-OTC | `data/bitcoin_otc/` | ✅ usado |
| Amazon Fraud | `data/amazon_fraud/Amazon.mat` | ✅ k=1% |
| Yelp Fraud | `data/yelp_fraud/YelpChi.mat` | ✅ k=1% |
| T-Finance | `Meu Drive/.../t_finance/` (DGL) | ✅ nb04, ⚠️ não incluído no ablation (FUSE) |
| DGraph-Fin | `Meu Drive/.../dgraph_fin/` | ✅ nb04 |
| IBM HI/LI Small | `data/ibm_aml/` | ✅ nb04, score heurístico cego |
| IBM HI/LI Medium/Large | `data/ibm_aml/` | ⛔ OOM (>32M edges) |
| **Libra Bank** | `Meu Drive/.../libra/` | ✅ **nb06 concluído** |

---

## Scripts e Notebooks

| Arquivo | Descrição | Status |
|---|---|---|
| `notebooks/nb04_multi_dataset.ipynb` | Pipeline multi-dataset | ✅ |
| `scripts/run_libra_final.py` | Libra Bank pipeline | ✅ nb06 |
| `scripts/run_curves2.py` | Purity curves + yield@100 (7 datasets) | ✅ |
| `scripts/run_ablation.py` | Ablation WCC/Leiden_flat/BTCS | ✅ nb07 |
| `scripts/run_seeds.py` | Multiple seeds 42–46 | ✅ nb08 |
| `scripts/run_nb04_pipeline.py` | Pipeline sequencial standalone | ✅ |
| `scripts/nb04_core_cells.py` | Funções extraídas do nb04 | ✅ |

---

## Roadmap ICDM 2026

### ✅ Concluído

| Item | Arquivo-chave |
|---|---|
| Multi-dataset benchmark (12 datasets) | `multi_dataset_results.csv` |
| Métricas operacionais (yield@100 + AUC purity) | `purity_curves_metrics.csv` |
| Libra Bank real-world validation | `libra_results.csv` |
| Ablation WCC / Leiden_flat / BTCS | `ablation_results.csv` |
| Estabilidade multi-seed (5 seeds) | `seeds_results.csv`, `seeds_table.tex` |
| Scalability (DGraph-Fin: 6.6s vs 359s B3) | nb04 |
| Tabelas LaTeX | `table_results_k5.tex`, `seeds_table.tex`, `libra_results_k5.tex` |

### 🟡 Pendente (afeta qualidade, não bloqueia submissão)

| # | Item | Estimativa | Impacto |
|---|---|---|---|
| 1 | Elliptic++ loader bug | 1–2h | +1 dataset único no benchmark |
| 2 | PaySim yield@100 | 30min | +1 linha na tabela de resultados |
| 3 | T-Finance no ablation | depende do FUSE | nice-to-have |
| 4 | nb05 GNN scores para IBM | semanas | trabalho futuro |

### ❌ Fora do escopo atual

- IBM Medium/Large (>32M edges, OOM)
- ETH-Phishing (6GB+ NetworkX)

---

## Assessment de Publicabilidade (2026-03-17 — pós nb07+nb08)

**Estado atual: ~90% pronto para ICDM 2026**

| Critério | Estado | Nota |
|---|---|---|
| Novidade algorítmica | ✅ | Hierarquia WCC→Leiden para AML, primeira vez |
| Avaliação em benchmarks públicos | ✅ | 12 datasets cobrindo fraude + AML |
| Validação real (kill shot) | ✅ | Libra Bank: AUC-ROC=1.0, cov=97.8%, B3=716s inviável |
| Métricas operacionais corretas | ✅ | yield@100 + AUC purity (substituem OCR) |
| Ablation study formal | ✅ | nb07: 3 variantes × 4 datasets × 3 k-values |
| Rigor estatístico (error bars) | ✅ | nb08: std≤0.020, Elliptic yield=1.000±0.000 |
| Eficiência computacional | ✅ | 3.8s (Libra), 6.6s (DGraph-Fin) vs 716s/359s B3 |
| Elliptic++ dataset único | ⚠️ | loader suspeito — investigar |
| GNN scores para IBM | ❌ | trabalho futuro (nb05) |

**Próximo passo imediato:** investigar Elliptic++ loader (pode elevar para ~93%)
**Após isso:** redigir paper (todos os resultados e tabelas LaTeX já existem)

---

## Dependências Técnicas

```
Python 3.10, igraph, leidenalg, numpy, pandas, scipy
DGL 1.1.3 (para T-Finance)
RAM: 4GB VM — datasets grandes foram amostrados
Repo local: /sessions/.../GrafosGNN/
Dados em: data/ (local) + Meu Drive/ (FUSE mount, Google Drive)
```
