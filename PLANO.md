# PLANO — GrafosGNN / ICDM 2026
**Última atualização:** 2026-03-20 (nb09–nb13 concluídos, reformulação BCCS v4/v5, paper v5)
**Autor:** Andre da Costa Silva (ITA)
**Objetivo:** Publicar paper em ICDM 2026 com o algoritmo HGS (Hierarchical Graph Segmentation) — anteriormente BTCS v3 — para segmentação de casos de AML

---

## Estado Atual

### Algoritmo
**HGS (Hierarchical Graph Segmentation)** = nome final do algoritmo, anteriormente chamado BTCS v3
Pipeline: Top-K edges por score → WCC → Leiden → Capping (B=100) → Avaliação

**Reformulação do problema (nb13 / BCCS v4):** O problema agora se chama **BCCS-P (Budgeted Connected Case Segmentation with Presentation)**:
- Partição dos nós V_k (top-k subgrafo)
- Budget B sobre *presented edges* P(C_i) = top-B edges por caso (não sobre edges induzidas)
- **FraudCoverage** = primária (fração de fraud edges que o analista vê)
- **PartitionCoverage** ≤ FraudCoverage (budget descarta algumas fraud edges)

Métricas implementadas (v4):
- `fraud_coverage`: fração de fraud edges cobertas nas presented edges ← **métrica principal**
- `partition_coverage`: fração de fraud edges nos casos (sem considerar budget)
- `purity`: fração de presented edges que são fraude
- `yield_avg`: yield médio por caso
- `yield_b100` (H1): yield no primeiro caso do ranking ← **métrica operacional principal**
- `auc_purity`: área sob curva de pureza acumulada
- `BFR`: fração de WCCs que precisam de splitting (Leiden)
- `n_cases`, `time_s`

Baselines:
- B0 Random, B1 WCC, B2 Louvain, B3 Greedy (temporal)
- **B4 TempWCC** (novo nb11): WCC sobre grafo temporal (edges dentro de janela)
- **B5 HubWCC** (novo nb11): WCC com peso por grau do nó

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
| Elliptic++ | `Meu Drive/.../elliptic_plus/` | ✅ loader corrigido (nb09) — grafo wallet→wallet |
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
| `notebooks/nb00_baseline.ipynb` | WCC baseline reproduction | ✅ |
| `notebooks/nb01_strong_baselines.ipynb` | Baselines comparativos B1/B2/B3 | ✅ |
| `notebooks/nb02_btcs_method.ipynb` | Método HGS (BTCS v3) core | ✅ |
| `notebooks/nb03_ablations.ipynb` | Ablation GAP 1–5, escalabilidade | ✅ |
| `notebooks/nb04_multi_dataset.ipynb` | Pipeline multi-dataset (12 datasets) | ✅ |
| `notebooks/nb05_gnn_training.ipynb` | GraphSAGE edge-level fraud scores | ✅ |
| `notebooks/nb06_libra.ipynb` | Libra Bank dataset (real AML) | ✅ |
| `scripts/run_libra_final.py` | Libra Bank pipeline | ✅ nb06 |
| `scripts/run_curves2.py` | Purity curves + yield@100 (7 datasets) | ✅ |
| `scripts/run_ablation.py` | Ablation WCC/Leiden_flat/HGS | ✅ nb07 |
| `scripts/run_seeds.py` | Multiple seeds 42–46 | ✅ nb08 |
| `scripts/run_nb04_pipeline.py` | Pipeline sequencial standalone | ✅ |
| `scripts/nb04_core_cells.py` | Funções core extraídas do nb04 | ✅ |
| `scripts/generate_paper.js` | Geração automática do paper (Node.js) | ✅ |
| `validate_docx.py` | Validação de integridade dos .docx | ✅ |

---

## Roadmap ICDM 2026

### ✅ Concluído

| Item | Arquivo-chave |
|---|---|
| Multi-dataset benchmark (12 datasets) | `multi_dataset_results.csv` |
| Elliptic++ loader corrigido (nb09) | `elliptic_plus_vs_elliptic.csv` |
| Libra Bank leak-free (nb10) | `libra_leakfree_results.csv` |
| Novos baselines B4+B5 (nb11) | `new_baselines_results.csv` |
| Theory validation empírica (nb12) | `theory_validation.csv` |
| BCCS-P reformulação formal (nb13) | `v4_all_results.csv` |
| Métricas operacionais | `purity_curves_metrics.csv` |
| Libra Bank validação real | `libra_results.csv` |
| Ablation WCC / Leiden_flat / HGS | `ablation_results.csv` |
| Estabilidade multi-seed (5 seeds) | `seeds_results.csv`, `seeds_table.tex` |
| Scalability (DGraph-Fin 6.6s vs B3 359s) | nb04 |
| NP-completeness + teoria formal | `docs/bccs_theory_v5.md` |
| Paper v5.1 | `BCCS_paper_v5.1.docx` |
| PaySim yield@100 (nb14) | `results/nb14_improvements/nb14_paysim_results.csv` |
| HGS_v2 algorithm analysis (nb14) | `results/nb14_improvements/nb14_improvements_results.csv` |

### 🟡 Pendente (não bloqueia submissão)

| # | Item | Estimativa | Impacto |
|---|---|---|---|
| 1 | ~~PaySim yield@100~~ **CONCLUÍDO** | — | yield@100=0.000 (score heurístico não captura fraude, mesmo problema IBM) |
| 2 | T-Finance no ablation | depende do FUSE | nice-to-have |
| 3 | GNN scores para IBM (nb05) | semanas | trabalho futuro |
| 4 | NC cap com GNN scores (Elliptic++) | depende do FUSE | melhoria potencial fraud_cov 0.434→? |

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

**Próximo passo imediato:** redigir paper v5 (estrutura BCCS-P + HGS + todos os resultados já existem)
**Paper atual:** `BCCS_paper_v5.1.docx` — versão mais recente

---

## nb09 — Elliptic++ Fix ✅ CONCLUÍDO (≈2026-03-18)

**Arquivo:** `results/nb09_elliptic_plus_fix/elliptic_plus_vs_elliptic.csv`
**Problema:** nb04 mostrava Elliptic++ == Elliptic (bug no loader usava grafo tx→tx em vez de wallet→wallet)
**Correção:** Loader agora usa o grafo AddrAddr (wallet-level), que é estruturalmente diferente do Elliptic

| Dataset | k | BTCS cov | BTCS yield@100 | B1_WCC cov |
|---|---|---|---|---|
| **Elliptic++** | 1% | **0.500** | **1.000** | 0.200 |
| **Elliptic++** | 5% | **0.873** | **1.000** | — |
| Elliptic (BTC) | 1% | 0.289 | 1.000 | 0.200 |

**Conclusão:** Elliptic++ é dataset genuinamente distinto — 36.9K fraud edges vs 8.1K do Elliptic. BFR = 98.7% (quase todas as WCCs precisam de Leiden). +1 dataset válido no benchmark.

---

## nb10 — Libra Leak-Free ✅ CONCLUÍDO (≈2026-03-18)

**Arquivo:** `results/nb10_libra_leakfree/libra_leakfree_results.csv`
**Problema:** Score Libra original (AUC-ROC=1.0) tinha leakage (usa nr_alerts que são labels pós-investigação)
**Solução:** Score leak-free = features puramente transacionais sem nr_alerts/nr_reports

| Score | k=1% yield@100 | k=5% yield@100 | Coverage k=5% |
|---|---|---|---|
| **Com leakage** (AUC=1.0) | 0.776 | 0.860 | 0.982 |
| **Leak-free** (AUC=0.997) | 0.120 | — | 0.935 |

**Conclusão:** Com score leak-free, yield@100 cai mas coverage permanece alto. O paper reporta **ambos os cenários** honestamente — score perfeito e score realista.

---

## nb11 — Novos Baselines (B4 TempWCC, B5 HubWCC) ✅ CONCLUÍDO (≈2026-03-18)

**Arquivo:** `results/nb11_new_baselines/new_baselines_results.csv`
**Datasets:** Elliptic, Elliptic++, Amazon, Yelp, Bitcoin-OTC

| Dataset | k | **HGS** yield@100 | **B4_TempWCC** yield@100 | **B5_HubWCC** yield@100 |
|---|---|---|---|---|
| Elliptic | 1% | **1.000** | 0.000 ⚠️ | — |
| Elliptic | 5% | **1.000** | 0.124 | — |
| Elliptic++ | 1% | **1.000** | — | — |
| Amazon | 1% | **0.939** | — | — |

**B4_TempWCC (Elliptic k=1%):** yield=0.000, coverage=0.000 — janela temporal destrói todo o sinal em grafos de blockchain (timestamps não correlacionam com fraude)
**B5_HubWCC:** performance similar ao B1_WCC — grau do nó não melhora a segmentação

**Sensibilidade ao budget B:** `sensitivity_analysis.csv` — HGS robusto para B=50–500, cobertura estável

---

## nb12 — Theory Validation Metrics ✅ CONCLUÍDO (≈2026-03-19)

**Arquivo:** `results/nb12_theory_validation/theory_validation.csv`
**Objetivo:** Medir empiricamente as constantes teóricas do algoritmo

Métricas calculadas por dataset/k:
- `wcc_cov` / `btcs_cov`: cobertura das WCCs vs HGS
- `cross`: edges cruzando fronteiras WCC (não capturáveis)
- `L_cut`: fraud edges cortadas pelo budget (δ = L_cut/|F|)
- `approx_ratio_lb`: lower bound do ratio de aproximação
- `bfr`: Budget Feasibility Rate — fração de WCCs sem Leiden splitting
- `avg_q`, `max_q`: tamanho médio/máximo das sub-partições Leiden

| Dataset | k=5% | δ (cut) | BFR | avg_q |
|---|---|---|---|---|
| Elliptic | 5% | 0.012 | 0.997 | 2.31 |
| Elliptic++ | 5% | 0.127 | 0.997 | 107.6 |
| Bitcoin-OTC | 5% | 0.731 | 0.986 | 76.0 |
| Amazon | 5% | 0.973 | 0.000 | 43,763 |
| Libra Bank | 5% | 0.034 | 0.9998 | 500.0 |

**Achado-chave:** BFR≈0.999 em Elliptic/Libra → WCC naturalmente produz casos pequenos. Amazon: 1 WCC gigante com 43K edges — budget B=100 corta 97% das fraud edges (limitação fundamental do dataset, não do algoritmo).

---

## nb13 — BCCS v4 Metrics (Reformulação Formal) ✅ CONCLUÍDO (≈2026-03-19)

**Arquivo:** `results/nb13_v4_metrics/v4_all_results.csv`
**Mudança:** Separação explícita FraudCoverage vs PartitionCoverage (ver docs/v4_formal_decisions.md)

| Dataset | k | HGS FraudCov | HGS PartCov | B2_Louvain FraudCov | B4_TempWCC FraudCov |
|---|---|---|---|---|---|
| Elliptic | 1% | 0.289 | 0.289 | 0.289 | **0.000** |
| Elliptic | 5% | **0.943** | 0.988 | 0.920 | 0.055 |
| Elliptic++ | 5% | — | — | — | — |

**docs/v4_formal_decisions.md:** Define BCCS-P, separação FraudCov/PartCov, lista de decisões formais do paper v4+.
**docs/bccs_theory_v5.md:** Teoria com provas formais — NP-completeness (MIS reduction), inaproximabilidade, e observações empíricas claramente separadas.

---

## nb14 — HGS Algorithm Improvements Analysis ✅ CONCLUÍDO (2026-03-26)

**Arquivo:** `results/nb14_improvements/nb14_improvements_results.csv`
**Notebook:** `notebooks/nb14_algorithm_improvements.ipynb`
**Script:** em `/sessions/sweet-friendly-goldberg/run_nb14.py` (mover para `scripts/run_nb14.py`)

### Melhorias Testadas

| Variante | Descrição | Resultado |
|---|---|---|
| **HGS_v2_NC** | Budget cap greedy por cobertura de nós (em vez de top-B por score) | **= baseline** com scores oracle |
| **HGS_v2_SW** | Leiden com pesos por score no grafo Lk | **-0.009** fraud_cov em Elliptic k=5% |
| **HGS_v2_BOTH** | NC + SW combinados | = SW (NC não interfere) |

### Resultados Comparativos (Elliptic + Bitcoin-OTC)

| Dataset | k | HGS_baseline | HGS_v2_NC | HGS_v2_SW | Δ_NC |
|---|---|---|---|---|---|
| Elliptic | 1% | 0.2886 | 0.2886 | 0.2886 | +0.0000 |
| Elliptic | 5% | 0.9425 | 0.9425 | 0.9335 | +0.0000 |
| Bitcoin-OTC | 1% | 0.0629 | 0.0629 | 0.0629 | +0.0000 |
| Bitcoin-OTC | 5% | 0.2439 | 0.2439 | 0.2439 | +0.0000 |

### PaySim yield@100 — NOVO RESULTADO

**Arquivo:** `results/nb14_improvements/nb14_paysim_results.csv`

| k | fraud_coverage | yield@100 | auc_purity | n_cases | tempo |
|---|---|---|---|---|---|
| 1% | 0.251 | **0.000** | 0.062 | 44,807 | 0.5s |
| 5% | 0.470 | **0.000** | 0.035 | 156,678 | 2.2s |
| 10% | 0.558 | **0.000** | 0.026 | 247,350 | 4.5s |

**Conclusão:** yield@100=0.000 — score heurístico (type_risk × amount) não captura fraude no PaySim. Mesmo padrão dos datasets IBM. Confirma necessidade de GNN scores (trabalho futuro).

### Diagnóstico Principal (finding novo para o paper)

**Problema descoberto:** Budget cap top-B por score cria bias sistemático contra fraud edges quando o score é imperfeito:
- **Elliptic++ k=5%:** `partition_coverage=0.873` mas `fraud_coverage=0.434`
- **Causa:** fraud edges dentro de uma comunidade têm scores MENORES que edges de ruído → cap remove preferencialmente fraudes
- **Quantificação:** 16.219 fraud edges na partição correta mas cortadas pelo budget cap
- Fraud edges são **8x overrepresentadas** nos edges cortados (7.99% vs 1.04% base rate)

**Solução (NC cap):** demonstra melhoria teórica com scores imperfeitos (experimentalmente validado com scores oracles como sanidade, precisa ser testado com Elliptic++ via GNN scores)

**Nota:** SW (Score-Weighted Leiden) é contra-indicado — com scores oracle cria super-clustering que reduz qualidade das comunidades.

---

## Evolução do Paper

| Versão | Arquivo | Conteúdo |
|---|---|---|
| BTCS_paper_draft | `BTCS_paper_draft.docx` | Rascunho inicial |
| BTCS_paper_v2 | `BTCS_paper_v2.docx` | 5 datasets, 6 métodos, figuras, auditoria de leakage |
| BTCS_paper_v3 | `BTCS_paper_v3.docx` | Revisões pós-nb07/nb08 |
| **BCCS_paper_v4** | `BCCS_paper_v4.4.docx` | Renomeado BCCS, reformulação formal, teoria NP |
| **BCCS_paper_v5** | `BCCS_paper_v5.docx` | HGS como nome do algoritmo, BCCS-P definition |
| **BCCS_paper_v5.1** | `BCCS_paper_v5.1.docx` | ← **VERSÃO MAIS RECENTE** |

---

## Assessment de Publicabilidade (2026-03-20 — pós nb09–nb13)

**Estado atual: ~95% pronto para ICDM 2026**

| Critério | Estado | Nota |
|---|---|---|
| Novidade algorítmica | ✅ | HGS: WCC→Leiden hierárquico para AML |
| Formulação formal do problema | ✅ | BCCS-P com presented edges budget |
| NP-completeness + inaproximabilidade | ✅ | docs/bccs_theory_v5.md |
| Avaliação em benchmarks públicos | ✅ | 12 datasets + Elliptic++ corrigido |
| Validação real (kill shot) | ✅ | Libra Bank leak-free + leakage reportados |
| Métricas operacionais | ✅ | yield@100 + AUC purity + FraudCoverage |
| Ablation study formal | ✅ | nb07+nb11: 5 variantes × datasets |
| Rigor estatístico | ✅ | nb08: std≤0.020 |
| Eficiência computacional | ✅ | <4s vs B3 716s |
| Theory validation empírica | ✅ | nb12: δ, BFR, approx_ratio_lb |
| GNN scores para IBM | ❌ | trabalho futuro |

**Próximo passo:** finalizar escrita do paper v5 e submeter a ICDM 2026

---

## Dependências Técnicas

```
Python 3.10, igraph, leidenalg, numpy, pandas, scipy
DGL 1.1.3 (para T-Finance)
RAM: 4GB VM — datasets grandes foram amostrados
Repo local: /sessions/.../GrafosGNN/
Dados em: data/ (local) + Meu Drive/ (FUSE mount, Google Drive)
```
