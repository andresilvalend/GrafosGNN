# PLANO — GrafosGNN / ICDM 2026
**Última atualização:** 2026-03-17
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
- `ocr_b100`: ⚠️ **SEMPRE ZERO** — bug/design a discutir
- `n_cases`, `time_s`

Baselines:
- B0 Random, B1 WCC, B2 Louvain, B3 Greedy (temporal)

---

## Resultados Multi-Dataset (nb04) — CONCLUÍDO ✅

**Arquivo:** `results/nb04_multi_dataset/multi_dataset_results.csv`
**180 linhas** | 12 datasets × 5 métodos × 3 k-values (1%, 5%, 10%)

### BTCS v3 @ k=5% — Tabela Resumo

| Dataset | \|E\| | BTCS cov | BTCS pur | Melhor rival (cov) |
|---|---|---|---|---|
| Elliptic (BTC) | 234K | **0.943** | 0.677 | B3 Greedy 0.958 (pur=0.06!) |
| Elliptic++ | 234K | **0.943** | 0.677 | B3 Greedy 0.958 (pur=0.06!) |
| PaySim | 6.4M | **0.470** | 0.012 | B1/B2 empate |
| BTC-Alpha | 24K | **0.388** | 0.562 | B2 Louvain 0.411 |
| BTC-OTC | 36K | **0.244** | 0.701 | B3 Greedy 0.279 |
| Amazon (500K*) | 500K | **0.190** | 0.770 | B3 Greedy 0.114 |
| Yelp (500K*) | 500K | **0.159** | 0.796 | B3 Greedy 0.291 |
| T-Finance (2M*) | 2M | 0.053 | 0.618 | B3 Greedy 0.081 |
| DGraph-Fin | 4.3M | 0.047 | 0.678 | **B3 Greedy 0.634** ⚠️ |
| IBM-HI Small | 5M | 0.044 | ~0 | todos ~0 pur |
| IBM-LI Small | 7M | 0.040 | ~0 | todos ~0 pur |
| IBM-AML | 1.3M | 0.005 | ~0 | B3 Greedy cov=0.216 |

\* Amostrados por RAM constraint (4GB VM). Amazon/Yelp: 500K de ~4M. T-Finance: 2M de 42M.

### Observações Críticas
1. **DGraph-Fin**: B3 Greedy domina cobertura (0.634 vs 0.047). BTCS ganha em velocidade (6.6s vs 359s). Argumento: tradeoff eficiência × cobertura.
2. **IBM datasets**: pureza ≈ 0 para TODOS os métodos. Grafos sintéticos de laundering não formam clusters temporais locais. Limitação do domínio, não do algoritmo.
3. **Elliptic == Elliptic++**: resultados idênticos → possível bug no loader do Elliptic++. Investigar.
4. **OCR = 0 em todos os 180 resultados**: bug ou design issue. **Discutir antes de corrigir.**

### Outputs Gerados
- `results/nb04_multi_dataset/multi_dataset_results.csv` — dados brutos
- `results/nb04_multi_dataset/multi_dataset_results_partial.csv` — checkpoint
- `results/nb04_multi_dataset/table_results_k5.tex` — tabela LaTeX para paper
- `results/nb04_multi_dataset/figures/fig1_cov_pur_scatter.png`
- `results/nb04_multi_dataset/figures/fig2_coverage_bar.png`
- `results/nb04_multi_dataset/figures/fig3_purity_bar.png`
- `results/nb04_multi_dataset/figures/fig4_coverage_vs_k.png`

---

## Datasets Disponíveis

| Dataset | Localização | Status |
|---|---|---|
| Elliptic (BTC) | `data/elliptic/` | ✅ usado |
| Elliptic++ | `Meu Drive/.../elliptic_plus/Elliptic++ Dataset/` | ✅ usado |
| PaySim | `data/paysim/` | ✅ usado |
| BTC-Alpha | `data/bitcoin_alpha/` | ✅ usado |
| BTC-OTC | `data/bitcoin_otc/` | ✅ usado |
| Amazon Fraud | `data/amazon_fraud/Amazon.mat` | ✅ amostrado |
| Yelp Fraud | `data/yelp_fraud/YelpChi.mat` | ✅ amostrado |
| T-Finance | `Meu Drive/.../t_finance/tfinance` (DGL binary) | ✅ amostrado |
| DGraph-Fin | `Meu Drive/.../dgraph_fin/raw/dgraphfin.npz` | ✅ usado |
| IBM HI/LI Small | `data/ibm_aml/HI-Small_Trans.csv` etc. | ✅ usado |
| IBM HI/LI Medium/Large | `data/ibm_aml/` | ⛔ OOM (>32M edges) |
| ETH-Phishing | `data/ethereum_phishing/MulDiGraph.pkl` (1.2GB) | ⛔ OOM (6GB+ NetworkX) |
| T-Social | não encontrado | ❓ pendente |
| Bitcoin-Heist | não encontrado | ❓ pendente |
| **Libra Bank** | `Meu Drive/.../libra/Libra_bank_3months_graph.csv` | 🔄 **PRÓXIMO** |

### Schema Libra Bank
```
597,166 edges (3 meses)
Colunas: id_source, id_destination, cum_amount, nr_transactions, nr_alerts, nr_reports
Sinal de fraude: nr_alerts > 0 e/ou nr_reports > 0
Sem timestamps explícitos (grafo agregado por par de contas)
```

---

## Scripts e Notebooks

| Arquivo | Descrição | Status |
|---|---|---|
| `notebooks/nb04_multi_dataset.ipynb` | Pipeline multi-dataset | ✅ loaders atualizados (commit 1a5f318) |
| `notebooks/nb06_libra.ipynb` | Libra Bank analysis | 🔄 em andamento (9 cells parciais) |
| `scripts/run_nb04_pipeline.py` | Pipeline sequencial standalone | ✅ completo |
| `scripts/nb04_core_cells.py` | Funções extraídas do nb04 | ✅ |
| `scripts/download_datasets.py` | Download automático | ✅ |

---

## Roadmap ICDM 2026

### 🔴 Bloqueadores (sem esses, paper não vai)

#### 1. nb06 — Libra Bank (próximo passo)
- Carregar `Libra_bank_3months_graph.csv`
- Score por `nr_alerts / (nr_transactions + 1)` ou similar
- Rodar BTCS v3 + baselines
- **Argumento chave**: BTCS identifica casos investigáveis vs. baselines que explodem em número de casos ou perdem cobertura

#### 2. OCR — discutir e corrigir
- **Problema**: `ocr_b100` = 0 em todos os resultados
- **Hipótese A**: métrica espera que casos tenham ≥ B=100 edges suspeitas — mas a maioria dos casos é pequena (median ≈ 0 edges)
- **Hipótese B**: a métrica calcula quantos casos "fecham" dentro do budget B mas o denominador está errado
- **Hipótese C**: OCR não faz sentido com edge-level labels (foi projetado para node-level)
- **Próximo passo**: discutir com Andre antes de implementar correção

### 🟡 Importante (enfraquece mas não bloqueia)

#### 3. Elliptic++ vs Elliptic — investigar
- Resultados idênticos: 0.943/0.677/4712 cases em ambos
- Verificar se o loader está pegando o mesmo subconjunto de arestas
- Pode ser que Elliptic++ tem o mesmo grafo de transações + info de atores (que não usamos)

#### 4. Ablation study (GAP 5 — parcialmente feito em nb03)
- WCC isolado vs Leiden isolado vs BTCS (WCC+Leiden)
- Já tem curvas de scalability no nb03

#### 5. DGraph-Fin — argumento de eficiência
- Criar figura: cobertura × tempo para BTCS vs B3 Greedy
- BTCS: 6.6s, cov=0.047. B3 Greedy: 359s, cov=0.634
- Em produção bancária: 6.6s é viável em batch diário. 359s não escala.

#### 6. Multiple seeds / error bars
- Rodar BTCS com seeds 42/43/44 em 3-4 datasets principais
- Reportar mean ± std

### 🟢 Pronto / Quase pronto

- ✅ Seção 4 (garantias de aproximação) em LaTeX
- ✅ GAP 3 (ablation Louvain) em nb03
- ✅ GAP 5 (scalability) em nb03
- ✅ Tabela multi-dataset em LaTeX (`table_results_k5.tex`)
- ✅ 4 figuras de análise

---

## Assessment de Publicabilidade (2026-03-17)

**Estado atual: ~65% pronto para ICDM**

| Critério | Estado | Nota |
|---|---|---|
| Novidade algorítmica | ✅ BTCS v3 é novo | Hierarquia WCC→Leiden para AML |
| Avaliação em benchmarks públicos | ✅ 12 datasets | Cobertura boa |
| Validação real (kill shot) | ❌ nb06 pendente | Libra Bank é o diferencial |
| Métricas corretas | ⚠️ OCR=0 | Discutir correção |
| Eficiência | ✅ parcial | DGraph-Fin mostra argumento |
| Ablation | ⚠️ parcial | nb03 tem parte |
| Statistical rigor | ❌ single seed | Fácil de adicionar |

**Sem nb06 + OCR fix:** aceito em conferência B (ECML Applied Track, etc.)
**Com nb06 + OCR fix:** candidato real a ICDM (mas competitivo)

---

## Dependências Técnicas

```
Python 3.10, igraph, leidenalg, numpy, pandas, scipy
DGL 1.1.3 (para T-Finance)
RAM: 4GB VM — datasets grandes foram amostrados
Dados em: /Meu Drive/GrafosGNN/data/ (Google Drive)
```
