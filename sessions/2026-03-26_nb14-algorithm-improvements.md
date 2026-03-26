# Sessão 2026-03-26 — nb14: HGS Algorithm Improvements

## O que foi feito
- Análise de bottlenecks dos resultados nb13 para identificar oportunidades de melhoria no HGS
- Implementação de 3 variantes de melhoria no algoritmo HGS (NC cap, SW Leiden, combinado)
- Execução de experimentos comparativos em Elliptic, Bitcoin-OTC e PaySim
- Diagnóstico do PaySim yield@100 (resultado pendente do PLANO)
- Descoberta de finding teórico novo sobre bias do budget cap

## Decisões tomadas

- **NC cap vs SW Leiden**: ambos implementados e testados. NC é preferível (não piora), SW é contra-indicado com scores oracle → **não incluir SW no paper como melhoria**
- **PaySim yield@100**: resultado é 0.000 → confirmar no paper como limitação do score heurístico (não incluir yield@100 na tabela principal, ou incluir com nota de rodapé)
- **NC cap para o paper**: incluir como contribuição técnica "para scores imperfeitos" mas não como resultado empírico (datasets locais usam oracle scores)
- **Finding novo sobre budget bias**: é uma contribuição valiosa — incluir na seção de análise do paper

## Resultados novos

| Experimento | Métrica | Valor | Arquivo |
|---|---|---|---|
| Elliptic k=5% HGS_v2_NC | fraud_coverage | 0.9425 (= baseline) | nb14_improvements_results.csv |
| Elliptic k=5% HGS_v2_SW | fraud_coverage | 0.9335 (-0.009 vs baseline) | nb14_improvements_results.csv |
| Bitcoin-OTC k=5% HGS_v2_NC | fraud_coverage | 0.2439 (= baseline) | nb14_improvements_results.csv |
| PaySim k=1% | yield@100 | **0.000** | nb14_paysim_results.csv |
| PaySim k=5% | fraud_coverage | 0.470 | nb14_paysim_results.csv |
| PaySim k=5% | yield@100 | **0.000** | nb14_paysim_results.csv |

## Problemas encontrados

- **Loader Elliptic errado na primeira tentativa**: estava usando y = (src_labels==1) AND (dst_labels==1) em vez de OR (max). Fixado para y = np.maximum(y_src, y_dst) identico ao nb04
- **Score proxy errado**: tentei usar f0 como score mas nb04 usa oracle (1.0/0.5/0.0 das labels). Fixado
- **PaySim OOM**: 6.4M edges não cabe na etapa de induced_edges (vectorized). Implementada versão memory-safe sem induced_edges (funciona pois WCC sizes ≤13 para k=1%, budget nunca ativa)
- **SW com pesos**: após ig.Graph.simplify(), o número de edges muda. Adicionada verificação de compatibilidade de tamanho antes de passar weights ao Leiden

## Descoberta Principal (finding novo para paper)

**Budget Cap Bias sob Scores Imperfeitos:**
- Elliptic++ k=5%: fraud_coverage=0.434 vs partition_coverage=0.873 → gap de 0.439
- Causa: fraud edges dentro de uma comunidade têm scores menores → cap top-B por score remove preferencialmente fraudes
- Quantificação: fraud edges são 8x overrepresentadas nas edges cortadas (7.99% vs 1.04% base rate)
- Fix: NC cap (greedy node coverage) elimina o bias garantindo cobertura de todos os nós

**Por que NC não mostra melhoria nos datasets locais:**
- Elliptic, Amazon, Yelp: scores ORACLE derivados das labels → fraud edges sempre têm score máximo → score-cap é ótimo
- Bitcoin-OTC: score = -rating → fraud (rating<0) sempre tem score > non-fraud → mesma razão
- Para demonstrar NC precisa de Elliptic++ com GNN scores (FUSE, não disponível localmente)

## Próximos passos

- [ ] Copiar `run_nb14.py` para `scripts/run_nb14.py`
- [ ] Quando FUSE disponível: rodar NC cap em Elliptic++ com GNN scores (hipótese: fraud_cov 0.434 → 0.65+)
- [ ] Decidir com Andre se NC cap é incluído no paper como contribuição técnica ou apenas como análise de limitação
- [ ] Finalizar escrita do paper v5.2 com os novos findings

## Arquivos alterados nesta sessão
- `notebooks/nb14_algorithm_improvements.ipynb` — novo notebook com HGS_v2 variants
- `results/nb14_improvements/nb14_improvements_results.csv` — comparação Elliptic/Bitcoin-OTC, 4 variantes, 2 k-values
- `results/nb14_improvements/nb14_paysim_results.csv` — PaySim yield@100 (novo resultado pendente)
- `results/nb14_improvements/nb14_noisy_score_experiment.csv` — experimento com score ruidoso (diagnóstico)
- `PLANO.md` — adicionado nb14 com achados + PaySim yield@100 concluído
