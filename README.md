# GrafosGNN — BTCS AML Benchmark

**Budgeted Temporal Case Segmentation for AML Transaction Monitoring**

Andre da Costa Silva | ITA | 2026

## Estrutura

```
notebooks/       → Notebooks do projeto BTCS (novos)
  nb00_baseline.ipynb       → Etapa 0: Baseline WCC reproduzido
  nb01_strong_baselines.ipynb → Etapa 1: B1/B2/B3
  nb02_btcs_method.ipynb    → Etapa 2: Método BTCS (grafo Lk + Leiden)
  nb03_ablations.ipynb      → Etapa 3: Ablações
  nb04_multidataset.ipynb   → Etapa 4: AMLworld + Libra Bank

legacy/          → Notebooks originais da dissertação (ICEIS 2026)
results/         → CSVs e tabelas de resultados
```

## Datasets

- AMLSim AML100k / AML1M (IBM sintético)
- IBM AMLworld HI/LI-Small (NeurIPS 2023)
- Libra Bank (IEEE Access 2022)

## Paper alvo: ICDM 2026 (~junho 2026)
