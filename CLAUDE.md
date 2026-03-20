# CLAUDE.md — Instruções de Sessão para GrafosGNN

> **Leia este arquivo inteiro antes de fazer qualquer coisa.**
> Depois leia `PLANO.md` para o estado atual do projeto.

---

## Regra Fundamental

**Nunca invente resultados, métricas, tabelas ou conclusões.**

Todo número que aparecer em resposta, código ou paper deve ter uma dessas origens:
1. Um arquivo CSV em `results/` que você leu diretamente
2. Um notebook `.ipynb` em `notebooks/` que você executou ou leu
3. Um script em `scripts/` que você rodou e cujo output você viu

Se não tiver certeza de onde um número vem, **pergunte antes de escrever**.

---

## Como Validar Antes de Afirmar

Antes de escrever qualquer resultado no paper ou responder uma pergunta sobre experimentos:

```
1. Identifique qual CSV/notebook contém os dados
2. Leia o arquivo com Read ou rode com Bash
3. Só então escreva o número
```

Exemplo correto:
- Pergunta: "Qual o yield@100 do HGS no Elliptic k=5%?"
- Ação: `Read results/nb04_multi_dataset/multi_dataset_results.csv` → filtrar → responder
- **Nunca**: responder de memória ou "aproximadamente"

---

## Estado do Projeto (resumo rápido)

**Para detalhes completos → leia `PLANO.md`**

| Item | Estado |
|---|---|
| Algoritmo | **HGS** (ex-BTCS v3): WCC → Leiden → Capping (B=100) |
| Problema | **BCCS-P**: partição de V_k, budget sobre presented edges |
| Paper atual | `BCCS_paper_v5.1.docx` ← versão mais recente |
| Experimentos | nb04–nb13 todos concluídos (ver PLANO.md) |
| Próximo passo | Finalizar paper v5 e submeter ICDM 2026 |

---

## Mapa de Arquivos de Resultados

| Notebook | CSV de referência | O que contém |
|---|---|---|
| nb04 | `results/nb04_multi_dataset/multi_dataset_results.csv` | 12 datasets × 5 métodos × 3 k-values |
| nb04 | `results/nb04_multi_dataset/purity_curves_metrics.csv` | AUC purity + yield@100 por dataset |
| nb06 | `results/nb06_libra/libra_results.csv` | Libra Bank (score com leakage) |
| nb07 | `results/nb07_ablation/ablation_results.csv` | Ablation WCC/Leiden/HGS |
| nb08 | `results/nb08_seeds/seeds_results.csv` | 5 seeds, estabilidade |
| nb09 | `results/nb09_elliptic_plus_fix/elliptic_plus_vs_elliptic.csv` | Elliptic++ loader corrigido |
| nb10 | `results/nb10_libra_leakfree/libra_leakfree_results.csv` | Libra Bank leak-free |
| nb11 | `results/nb11_new_baselines/new_baselines_results.csv` | Baselines B4_TempWCC, B5_HubWCC |
| nb12 | `results/nb12_theory_validation/theory_validation.csv` | δ, BFR, approx_ratio_lb, cross |
| nb13 | `results/nb13_v4_metrics/v4_all_results.csv` | FraudCoverage vs PartitionCoverage (BCCS-P) |

---

## Métricas — Definições Exatas

Usar sempre essas definições. Não improvise variações.

| Métrica | Definição | Arquivo de referência |
|---|---|---|
| `fraud_coverage` | \|{e ∈ F : e ∈ ∪P(Cᵢ)}\| / \|F\| — fraud edges que o analista VÊ | nb13 / BCCS-P |
| `partition_coverage` | \|{e ∈ F : endpoints no mesmo caso}\| / \|F\| — fraud edges no mesmo caso | nb13 |
| `yield_b100` | \|P(C₁) ∩ F\| / B — yield do caso de maior score | nb04+ |
| `auc_purity` | Área sob curva de pureza acumulada (casos ranqueados) | nb04+ |
| `purity` | \|presented edges que são fraude\| / \|presented edges\| | nb04+ |
| `BFR` | Fração de WCCs com \|E(Cᵢ)\| ≤ B (sem precisar Leiden) | nb12 |
| `delta` (δ) | Fração de fraud edges cortadas pelo budget | nb12 |

**Nota importante sobre Libra Bank:**
- Score com leakage: AUC-ROC=1.0 (usa nr_alerts pós-investigação) → yield@100=0.86 k=5%
- Score leak-free: AUC-ROC=0.997 → yield@100=0.12 k=1% — reportar **ambos** no paper

---

## Baselines — Nomes Exatos

| ID | Nome | Descrição |
|---|---|---|
| B0 | `B0_Random` | Partição aleatória |
| B1 | `B1_WCC` | Componentes conexas puras |
| B2 | `B2_Louvain` | Louvain flat sem WCC |
| B3 | `B3_Greedy` | Greedy temporal (lento: 716s Libra) |
| B4 | `B4_TempWCC` | WCC sobre grafo temporal (janela) |
| B5 | `B5_HubWCC` | WCC com peso por grau |
| HGS | `HGS` | Nosso algoritmo (ex-BTCS_v3) |

---

## Datasets — Localização e Cuidados

| Dataset | Localização | Cuidado |
|---|---|---|
| Elliptic | `data/elliptic/` | 8,145 fraud edges |
| Elliptic++ | `data/elliptic_plus/` ou FUSE | **Usar grafo AddrAddr (wallet→wallet)**, não tx→tx |
| PaySim | `data/paysim/` | yield@100 ainda pendente |
| Bitcoin-Alpha | `data/bitcoin_alpha/` | — |
| Bitcoin-OTC | `data/bitcoin_otc/` | — |
| Amazon Fraud | `data/amazon_fraud/Amazon.mat` | k=1% (k=5% → OOM) |
| Yelp Fraud | `data/yelp_fraud/YelpChi.mat` | k=1% |
| T-Finance | FUSE (Google Drive) | Não incluído no ablation |
| DGraph-Fin | FUSE (Google Drive) | B3 Greedy domina cobertura aqui |
| IBM HI/LI Small | `data/ibm_aml/` | Score heurístico cego, pureza ≈ 0 para todos |
| Libra Bank | FUSE (Google Drive) | **Dataset real AML** — ver nb10 para versão leak-free |

---

## Teoria — O Que Está Provado vs O Que É Empírico

**Ver `docs/bccs_theory_v5.md` para provas formais completas**

| Claim | Status | Onde está |
|---|---|---|
| BCCS-P é NP-completo | ✅ Provado (redução MIS) | `docs/bccs_theory_v5.md` |
| Inaproximável em \|V\|^{1-ε} | ✅ Provado (herança MIS) | `docs/bccs_theory_v5.md` |
| HGS ≥ WCC em cobertura | ✅ Empírico (nb04–nb13) | `multi_dataset_results.csv` |
| HGS é determinístico na prática | ✅ Empírico (std≤0.020) | `seeds_results.csv` |
| Scalability: O(n log n) | ⚠️ Informal — não usar como claim | — |

**Nunca afirmar garantias teóricas sem citar `docs/bccs_theory_v5.md` como fonte.**

---

## Workflow Padrão para Novas Tarefas

### Se for escrever/editar o paper:
1. Leia o paper atual: `Read BCCS_paper_v5.1.docx` (use skill `docx`)
2. Verifique os números: leia os CSVs relevantes antes de escrever
3. Salve como versão nova (ex: `BCCS_paper_v5.2.docx`), **nunca sobrescreva**

### Se for rodar um novo experimento:
1. Veja se já existe em `results/` antes de rodar de novo
2. Se rodar, salve o CSV em `results/nbXX_nome/nome_results.csv`
3. Atualize `PLANO.md` com os resultados

### Se for commitar:
1. `git status` para ver o que mudou
2. `git add` apenas os arquivos relevantes
3. Mensagem de commit descritiva com o que foi feito
4. `git push origin main`

### Ao salvar log de sessão (obrigatório — ver seção abaixo):
1. Escreva `sessions/YYYY-MM-DD_tema.md` com o resumo da sessão
2. `git add sessions/YYYY-MM-DD_tema.md` + qualquer outro arquivo alterado
3. `git push origin main`

---

## Registro de Sessões — Regra Obrigatória

**Ao final de cada análise significativa, ou a cada ~1h de trabalho, salve um log de sessão.**

O objetivo é que a próxima sessão possa reconstruir o raciocínio sem depender da memória do Claude.

### Quando salvar:
- Ao concluir qualquer experimento (rodou código, gerou CSV)
- Ao tomar uma decisão importante (mudança de métrica, reformulação, escolha de baseline)
- Ao editar o paper com novos resultados
- Antes de encerrar a sessão

### Formato do arquivo: `sessions/YYYY-MM-DD_tema-curto.md`

Exemplos: `sessions/2026-03-20_elliptic-plus-fix.md`, `sessions/2026-03-20_paper-v5.md`

### Template obrigatório:

```markdown
# Sessão YYYY-MM-DD — [Tema]

## O que foi feito
- [lista do que foi executado/alterado]

## Decisões tomadas
- [decisão]: [motivo] — isso é crítico para não repetir discussões

## Resultados novos
| Experimento | Métrica | Valor | Arquivo |
|---|---|---|---|
| ... | ... | ... | results/... |

## Problemas encontrados
- [problema]: [como foi resolvido ou status]

## Próximos passos
- [ ] [tarefa concreta com arquivo/notebook alvo]

## Arquivos alterados nesta sessão
- `arquivo.py` — [o que mudou]
- `results/nbXX/...csv` — [novo resultado]
```

### Regra de commit do log:
Sempre commitar o log junto com os arquivos da sessão num único commit:
```
git add sessions/YYYY-MM-DD_tema.md results/... notebooks/...
git commit -m "session YYYY-MM-DD: [tema] — [resumo de 1 linha]"
git push origin main
```

---

## O Que Não Fazer

- ❌ Inventar ou estimar métricas sem ler o CSV
- ❌ Sobrescrever versões anteriores do paper (sempre criar nova versão)
- ❌ Afirmar que um experimento "deve dar X" sem rodar
- ❌ Usar resultados do nb04 para o Elliptic++ (loader estava bugado — usar nb09)
- ❌ Citar Libra Bank yield@100=0.86 sem mencionar que é com score com leakage
- ❌ Commitar arquivos `data/` (datasets grandes, no .gitignore)
