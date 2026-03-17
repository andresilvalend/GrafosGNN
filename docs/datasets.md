# Dataset Reference — BTCS ICDM 2026
*Maintainer: Andre da Costa Silva (ITA) | Last updated: 2026-03-17*

> **✅ Todos os datasets estão disponíveis no Google Drive (`GrafosGNN/data/`).**
> Downloads concluídos em 2026-03-17. Ver seções abaixo para paths e schemas exatos.

> **Propósito:** Referência persistente para que novas sessões Claude consigam
> retomar o trabalho sem perder contexto de quais datasets existem, seus paths
> exatos, schemas de colunas e semântica dos labels. Atualizar este arquivo ao
> adicionar novos datasets ou mudar estrutura de diretórios.

---

## Índice

| Dataset | Tipo | Arestas | Label | Notebook | Status |
|---------|------|---------|-------|----------|--------|
| [AML100k](#aml100k) | Sintético (AMLSim) | ~2.49M (test split) | edge IS_FRAUD | nb01/02/03 | ✅ |
| [AML1M](#aml1m) | Sintético (AMLSim) | ~24M (test split) | edge IS_FRAUD | nb01/02/03 | ✅ |
| [IBM HI-Small/Medium/Large](#ibm-hi-li) | Sintético | 5M / 32M / 180M | edge Is Laundering | nb04/05 | ✅ |
| [IBM LI-Small/Medium/Large](#ibm-hi-li) | Sintético | 7M / 31M / 176M | edge Is Laundering | nb04/05 | ✅ |
| [IBM AML Transactions](#ibm-aml-transactions) | Sintético | ~1.3M | edge IS_FRAUD | nb04/05 | ✅ |
| [Elliptic Bitcoin](#elliptic-bitcoin-dataset) | Real (Bitcoin) | 234,355 | node class→edge | nb04/05 | ✅ |
| [PaySim](#paysim) | Sintético (mobile money) | 6,362,620 | edge isFraud | nb04/05 | ✅ |
| [Bitcoin Alpha](#bitcoin-alphaotc) | Real (trust ratings) | 24,186 | rating < 0 | nb04 | ✅ |
| [Bitcoin OTC](#bitcoin-alphaotc) | Real (trust ratings) | 35,592 | rating < 0 | nb04 | ✅ |
| [Amazon Fraud](#amazon--yelp-fraud) | Real (.mat) | ~4.4M | node→edge | nb04/05 | ✅ |
| [Yelp Fraud](#amazon--yelp-fraud) | Real (.mat) | ~3.8M | node→edge | nb04/05 | ✅ |
| [**Libra Bank**](#libra-bank-real) | **Real (banco RO)** | **597,165** | **edge nr_alerts/nr_reports** | **nb06** | **✅** |
| [**DGraph-Fin**](#dgraph-fin) | Real (fintech CN) | 4,300,999 | node fraud→edge | nb04/05 | ✅ |
| [**T-Finance**](#t-finance) | Real (fintech CN) | 42,445,086 | node anomaly→edge | nb04/05 | ✅ |
| [**Elliptic++**](#elliptic-plus) | Real (Bitcoin) | ~234k+ tx+wallet | node illicit→edge | nb04/05 | ✅ |

---

## AML100k

**Paper:** IBM AMLSim — "Anti-Money Laundering in Bitcoin: Experimenting with Graph Convolutional Networks for Financial Forensics"
Weber et al., KDD 2019 / AMLSim NeurIPS 2023 challenge
**DOI/URL:** https://www.kaggle.com/competitions/aml-2023

**Descrição:** Dataset sintético gerado pelo IBM AMLSim, 100k clientes, padrões de laundering AML.

**Paths (Google Drive / Colab):**
```
DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k/
  artifacts/
    edge_data_v4_clean.pt         ← cache PyTorch com ei_all_cpu, te_idx, etc.
  results/probs_v4/
    SAGE_seed42_test.npz          ← {p: scores, y: labels, src, dst arrays}
```

**Variáveis de path nos notebooks:**
```python
AML100K_BASE  = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML100K_ARTIF = AML100K_BASE / 'artifacts'
AML100K_PROBS = AML100K_BASE / 'results/probs_v4'
AML100K_MODEL = 'SAGE'
AML100K_SEED  = 42
```

**Schema .npz:**
```
p          float32[N_test]   GNN score (P(fraude))
y          int[N_test]       label binário (IS_FRAUD)
src        int64[N_test]     source node index
dst        int64[N_test]     destination node index
```

**Schema edge_data_v4_clean.pt (dict):**
```
ei_all_cpu   Tensor[2, N_total]    edge index full graph
te_idx       Tensor[N_test]        índices das arestas de teste
```

**Stats:**
- ~2.49M arestas no split de teste
- Fraude: ~1-5% das arestas
- delta_L = 7 dias
- GNN: GraphSAGE (SAGE), seed=42

---

## AML1M

**Mesma fonte do AML100k** — versão 10× maior (1M clientes)

**Paths:**
```
DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M/
  artifacts/
    edge_data_v4_clean.pt
  results_aml1m_graphsage_only/probs_v4/
    GraphSAGE_seed44_test.npz
```

**Variáveis de path:**
```python
AML1M_BASE  = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'
AML1M_ARTIF = AML1M_BASE / 'artifacts'
AML1M_PROBS = AML1M_BASE / 'results_aml1m_graphsage_only/probs_v4'
AML1M_MODEL = 'GraphSAGE'
AML1M_SEED  = 44
```

**Stats:**
- ~24M arestas no split de teste
- GNN: GraphSAGE, seed=44

---

## IBM HI / LI

**Paper:** Altman et al., "Realistic Synthetic Financial Transactions for Anti-Money Laundering Models"
NeurIPS 2023 Datasets & Benchmarks
**DOI:** https://doi.org/10.48550/arXiv.2306.16424
**Kaggle:** https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml

**Descrição:** Transações bancárias sintéticas com dois perfis de laundering:
- **HI** (High Illicit ratio): maior proporção de transações ilícitas
- **LI** (Low Illicit ratio): menor proporção de transações ilícitas

**Paths:**
```
GrafosGNN/data/ibm_aml/
  HI-Small_Trans.csv      ← ~5M transações
  HI-Medium_Trans.csv     ← ~32M transações
  HI-Large_Trans.csv      ← ~180M transações
  LI-Small_Trans.csv      ← ~7M transações
  LI-Medium_Trans.csv     ← ~31M transações
  LI-Large_Trans.csv      ← ~176M transações
  HI-Small_Patterns.txt   ← padrões AML (referência)
  HI-Medium_Patterns.txt
  HI-Large_Patterns.txt
  LI-Small_Patterns.txt
  LI-Medium_Patterns.txt
  LI-Large_Patterns.txt
  HI-Small_accounts.csv   ← contas
  HI-Medium_accounts.csv
  HI-Large_accounts.csv
  LI-Small_accounts.csv
  LI-Medium_accounts.csv
  LI-Large_accounts.csv
```

**Schema CSV (colunas):**
```
Timestamp, From Bank, Account, To Bank, Account.1,
Amount Received, Receiving Currency,
Amount Paid, Payment Currency,
Payment Format, Is Laundering
```
- `Account` = sender account (pandas renomeia duplicata para `Account.1` = receiver)
- `Is Laundering` = label binário (0/1)
- Node ID = `From Bank` + `_` + `Account` (concatenação para unicidade entre bancos)

**Loader (nb04):**
```python
src_id = df['From Bank'].astype(str) + '_' + df['Account'].astype(str)
dst_id = df['To Bank'].astype(str) + '_' + df['Account.1'].astype(str)
y = df['Is Laundering'].values.astype(int)
```

**Stats:**
- delta_L = 30 dias
- Large variants requerem RAM ≥ 48 GB (skip automático em nb04)
- GNN scores salvos por nb05 em: `GrafosGNN/results/nb05_gnn/{variant}_gnn_scores.npz`

---

## IBM AML Transactions

**Mesma fonte IBM/NeurIPS 2023 acima.**

**Path:**
```
GrafosGNN/data/ibm_aml/
  transactions.csv       ← ~1.3M transações
  accounts.csv
  alerts.csv
```

**Schema:**
```
TIMESTAMP, SENDER_ACCOUNT_ID, RECEIVER_ACCOUNT_ID,
TX_AMOUNT, TX_TYPE, IS_FRAUD
```

**Stats:**
- delta_L = 7 dias
- Fraude: ~2% das arestas

---

## Elliptic Bitcoin Dataset

**Paper:** Weber et al., "Anti-Money Laundering in Bitcoin: Experimenting with Graph Convolutional Networks for Financial Forensics"
KDD 2019 Workshop on Anomaly Detection in Finance
**URL:** https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
**DOI:** 10.1145/3326424

**Descrição:** Transações Bitcoin anonimizadas com 49 features por nó, labels illicit/licit em 49 time steps.

**Path:**
```
GrafosGNN/elliptic/elliptic_bitcoin_dataset/
  elliptic_txs_features.csv    ← 203,769 nós × 166 cols (txId, time_step, 166 features)
  elliptic_txs_edgelist.csv    ← 234,355 arestas (txId1, txId2)
  elliptic_txs_classes.csv     ← labels (txId, class): "1"=illicit, "2"=licit, "unknown"
```

**Schema classes:**
```
txId    class
------  -------
int     "1"      illicit (AML)
int     "2"      licit
int     "unknown" sem label
```

**Stats:**
- 203,769 nós | 234,355 arestas
- 4,545 illicit | 42,019 licit | 157,205 unknown
- 49 time steps (sequência temporal de blocos Bitcoin)
- Edge label = OR dos labels dos dois nós (illicit propagado)
- delta_L = 2 time steps

---

## PaySim

**Paper:** Lopez-Rojas, E.A., Elmir, A., Axelsson, S. "PaySim: A Financial Mobile Money Simulator for Fraud Detection"
EMSS 2016
**Kaggle:** https://www.kaggle.com/datasets/ealaxi/paysim1

**Descrição:** Simulação de transações de mobile money em um país africano, com injeção de comportamento fraudulento.

**Path:**
```
GrafosGNN/paysim/
  PS_20174392719_1491204439457_log.csv    ← 6.36M transações
```

**Schema:**
```
step          int     hora simulada (1-744, ~30 dias)
type          str     CASH_IN | CASH_OUT | DEBIT | PAYMENT | TRANSFER
amount        float   valor da transação
nameOrig      str     cliente de origem
oldbalanceOrg float
newbalanceOrig float
nameDest      str     destinatário
oldbalanceDest float
newbalanceDest float
isFraud       int     label (0/1)
isFlaggedFraud int    regra heurística do simulador
```

**Stats:**
- 6,362,620 transações | 8,213 fraudes (0.13%)
- Apenas TRANSFER e CASH_OUT contêm fraudes
- delta_L = 24 horas (steps)

---

## Bitcoin Alpha/OTC

**Paper:** Kumar et al., "Edge Weight Prediction in Weighted Signed Networks"
ICDM 2016
**Stanford SNAP:** https://snap.stanford.edu/data/soc-sign-bitcoin-otc.html
https://snap.stanford.edu/data/soc-sign-bitcoin-alpha.html

**Descrição:** Redes de confiança/desconfiança entre usuários de plataformas Bitcoin.

**Paths:**
```
GrafosGNN/bitcoin_alpha/
  soc-sign-bitcoinalpha.csv    ← 24,186 edges

GrafosGNN/bitcoin_otc/
  soc-sign-bitcoinotc.csv      ← 35,592 edges
```

**Schema (sem header):**
```
col 0: src       user_id de origem
col 1: dst       user_id de destino
col 2: rating    -10 a +10 (confiança)
col 3: timestamp unix timestamp
```

**Label:** `y = 1` se `rating < 0` (desconfiança/fraude)

**Stats:**
- Bitcoin Alpha: 24,186 arestas | ~14% negativos
- Bitcoin OTC:   35,592 arestas | ~14% negativos
- delta_L = 30 dias

---

## Amazon / Yelp Fraud

**Paper (Amazon):** McAuley & Leskovec, "From amateurs to connoisseurs: modeling the evolution of user expertise through online reviews"
WWW 2013
**Paper (Yelp):** Rayana & Akoglu, "Collective Opinion Spam Detection: Bridging Review Networks and Metadata"
KDD 2015

**Paths:**
```
GrafosGNN/data/amazon_fraud/
  Amazon.mat       ← grafo + labels em formato scipy sparse

GrafosGNN/data/yelp_fraud/
  YelpChi.mat      ← grafo + labels em formato scipy sparse
```

**Schema .mat:**
```
mat['homo']    scipy sparse  grafo homofílico (relações entre reviews)
mat['label']   array[N]      labels de nó (0/1 fraude)
```

**Stats:**
- Amazon: ~4.4M arestas | ~10% fraude
- Yelp:   ~3.8M arestas | ~14% fraude
- Sem timestamps → delta_L = N_edges (sem janela temporal)

---

## Libra Bank (Real)

**Paper:** Dumitrescu, B., Baltoiu, A., Budulan, S.
"Anomaly Detection in Graphs of Bank Transactions for Anti Money Laundering Applications"
IEEE Access, 2022
**DOI:** https://doi.org/10.1109/ACCESS.2022.3170467
**Dataset URL:** http://graphomaly.upb.ro/
**Licença:** Livre para uso com citação obrigatória

**Descrição:** Grafo de transações reais do Libra Internet Bank (Romênia), 3 meses de operação.
Único dataset público de banco real para AML. Grafo agregado (sem timestamps individuais por transação).

**Path:**
```
GrafosGNN/data/libra/
  Libra_bank_3months_graph.csv    ← arquivo único com arestas + labels inline
  readme_libra.txt                ← nota dos autores sobre GDPR
```

**Schema CSV (arquivo único):**
```
id_source       int   conta de origem
id_destination  int   conta de destino
cum_amount      float valor cumulativo das transações entre o par (3 meses)
nr_transactions int   número total de transações entre o par
nr_alerts       int   número de transações com alerta AML no par
nr_reports      int   número de transações com relatório AML no par
```

**Labels:**
```python
# Edge label (usado no BTCS)
y_edge = 1 if (nr_alerts > 0) OR (nr_reports > 0)

# Node label (derivado para o GNN)
y_node = 1 if o nó aparece em ≥1 aresta com nr_alerts > 0 OR nr_reports > 0
```

**Stats (verificados em 2026-03-17):**
```
Nós:    385,100  total
        600      alert/report nodes (0.156%)

Arestas:  597,165 total
          444     y_edge = 1  (nr_alerts > 0 OR nr_reports > 0) → 0.074%
          444     nr_alerts > 0
           11     nr_reports > 0  (subconjunto dos 444 alert)

Amount:   min=0.01  max=425,000,000  mean=23,448.90
nr_transactions: min=1  max=24,637  mean=3.05
```

**Diferenças vs AMLSim (impacto no BTCS):**

| Aspecto | AMLSim | Libra |
|---------|--------|-------|
| Labels | Edge-level direto | Edge-level inline no CSV |
| Timestamps | Por transação (step) | N/A — grafo agregado |
| GNN target | Edge classification | Node classification → edge scores |
| delta_L | 7 dias | ∞ (sem restrição temporal) |
| Positivos | ~1-5% arestas | ~0.074% arestas |
| Divisão | train/val/test split | Grafo não dividido (avaliação completa) |

**Loader (nb06, Cell 2):**
```python
df_edges, df_nodes, node2idx = load_libra(LIBRA_CSV)
# LIBRA_CSV = GrafosGNN/data/libra/Libra_bank_3months_graph.csv
```

**GNN (nb06, Cell 3):** GraphSAGE 2-layer, node classification, w_pos ≈ 600×
**Edge scores:** `score_edge(u,v) = max(score_node(u), score_node(v))`

---

## GNN Score Files (nb05 output)

O notebook `nb05_gnn_training.ipynb` treina GraphSAGE em cada dataset e salva:

```
GrafosGNN/results/nb05_gnn/
  {dataset_name}_gnn_scores.npz    ← {p, y, src, dst, timestamps}
```

Datasets com scores GNN (nb05):
- `ibm_aml_txns`, `IBM_HI_Small`, `IBM_HI_Medium`, `IBM_HI_Large`
- `IBM_LI_Small`, `IBM_LI_Medium`, `IBM_LI_Large`
- `elliptic`, `amazon_fraud`, `yelp_fraud`, `paysim`

---

## Convenções de Path

```python
# Colab (Google Drive montado)
IN_COLAB = 'google.colab' in sys.modules
BASE = Path('/content/drive/MyDrive') if IN_COLAB else Path('.').resolve()

# Datasets grandes (AMLSim AML100k/AML1M)
AML100K_BASE = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'

# Datasets no repo GrafosGNN (versionados via .gitignore de dados grandes)
DATA    = BASE / 'GrafosGNN/data'        # bitcoin, elliptic, paysim, ibm_aml, libra
RESULTS = BASE / 'GrafosGNN/results'     # outputs dos notebooks
```

**Drive local (macOS):**
```
~/Library/CloudStorage/GoogleDrive-acsilva@gmail.com/Meu Drive/GrafosGNN/data/libra/
```

---

## DGraph-Fin

**Paper:** Yancheng Dong et al., "DGraph: A Large-Scale Financial Dataset for Graph Anomaly Detection"
NeurIPS 2022 Datasets & Benchmarks
**DOI:** https://arxiv.org/abs/2207.03579
**Download:** https://dgraph.xinye.com/dataset (requer cadastro não-comercial)
**GitHub:** https://github.com/DGraphXinye/DGraphFin_baseline

**Descrição:** Grafo de relações de contato de emergência entre usuários de plataforma de microcrédito online (Finvolution Group, China). Detecção de usuários fraudulentos/defaulters.

**Download:** Cadastro em https://dgraph.xinye.com/dataset (termo de uso não-comercial).

**Path (arquivos reais extraídos):**
```
GrafosGNN/data/dgraph_fin/raw/
  dgraphfin.npz                     ← 649 MB — numpy format (formato real do download)
  dgraphfinv2_edge_timestamp.npy    ← 17 MB — edge timestamps (V2)
  dgraphfinv2_node_timestamp.npy    ← 15 MB — node timestamps (V2)
  Readme.md
```

**Estrutura do .npz (numpy format):**
```python
data['x']               float64[3_700_550, 17]   features de nó (anonimizadas)
data['edge_index']      int64[4_300_999, 2]       arestas — shape (E,2) NÃO (2,E)!
data['edge_type']       int64[4_300_999]           tipo de relacionamento
data['edge_timestamp']  int64[4_300_999]           timestamp ordinal (já incluso no .npz)
data['y']               int64[3_700_550]            label: 0=normal, 1=fraude, 2=blacklist
data['train_mask']      int64[857_899]              índices de treino (não boolean)
data['valid_mask']      int64[183_862]              índices de validação
data['test_mask']       int64[183_840]              índices de teste
```

**Stats:**
```
Nós:     3,700,550 total  |  ~1.32% fraudulentos (label > 0)
Arestas: 4,300,999        |  17 features por nó
```

**Para BTCS:**
- node-level labels → edge scores via `max(score_src, score_dst)`
- `delta_L = 30` (timestamps ordinais disponíveis)
- Loader: `load_dgraph_fin()` em nb04 Cell 4B

---

## T-Finance

**Paper:** Jianheng Tang et al., "Rethinking Graph Neural Networks for Anomaly Detection"
ICML 2022
**DOI:** https://proceedings.mlr.press/v162/tang22b.html
**Download:** https://drive.google.com/drive/folders/1PpNwvZx_YRSCDiHaBUmRIS3x1rZR7fMr
**GitHub:** https://github.com/squareRoot3/Rethinking-Anomaly-Detection

**Descrição:** Rede de transações financeiras reais anonimizada de plataforma fintech chinesa. Nós são contas/usuários; arestas indicam relações de transação. Anomalias incluem fraude, lavagem de dinheiro e apostas online.

**Download:** Google Drive: https://drive.google.com/drive/folders/1PpNwvZx_YRSCDiHaBUmRIS3x1rZR7fMr

**Path (arquivo real extraído):**
```
GrafosGNN/data/t_finance/
  tfinance    ← 652 MB — DGL binary format (SEM extensão, não .pt!)
```

**Estrutura DGL (carregado com `dgl.load_graphs()`):**
```python
g = dgl.load_graphs('tfinance')[0][0]
g.num_nodes()          # 39 357 nós (versão distribuída processada)
g.num_edges()          # 42 445 086 arestas
g.ndata['feature']     # float64[39_357, 10]   features por nó
g.ndata['label']       # int64[39_357, 2]       one-hot: col 0=normal, col 1=fraude
# y_node = g.ndata['label'][:, 1].numpy()
```

**Nota:** A versão distribuída tem 39 357 nós (≠ 939 010 do paper original), mas mantém
o fraud rate de 4.58% exato. Estrutura de grafo diferente (42M arestas vs 3.6M do paper).

**Stats (versão real):**
```
Nós:     39,357 total    |  ~4.58% anomalias (fraude/lavagem/apostas)
Arestas: 42,445,086      |  10 features por nó
Sem timestamps (grafo estático)
```

**Para BTCS:**
- node-level labels → edge scores via `max(score_src, score_dst)`
- `delta_L = n_edges` (sem janela temporal — grafo estático [NT])
- Loader: `load_t_finance()` em nb04 Cell 4B

---

## Elliptic Plus

**Paper:** Youssef Elmougy & Ling Liu, "Demystifying Fraudulent Transactions and Illicit Nodes in the Bitcoin Network for Financial Forensics"
KDD 2023
**DOI:** https://arxiv.org/abs/2404.19109
**Download:** https://drive.google.com/drive/folders/1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l
**GitHub:** https://github.com/git-disl/EllipticPlusPlus

**Descrição:** Extensão do Elliptic original que adiciona:
1. **Transactions Dataset**: mesmos 203k txs + arestas tx→wallet
2. **Actors Dataset**: 822k wallets/endereços Bitcoin com labels de entidade (exchanges, mixers, mining pools, scams, etc.)

**Download:** Google Drive: https://drive.google.com/drive/folders/1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l

**Path (arquivos reais extraídos):**
```
GrafosGNN/data/elliptic_plus/
  Elliptic++ Dataset/                  ← subpasta com este nome exato (inclui espaço e ++)
    txs_features.csv                   ← features por transação (col 0=txId, col 1=timestep)
    txs_classes.csv                    ← labels ('1'=illicit, '2'=licit, 'unknown')
    txs_edgelist.csv                   ← arestas tx→tx
    AddrTx_edgelist.csv               ← arestas wallet→tx (novo no Elliptic++)
    TxAddr_edgelist.csv               ← arestas tx→wallet (novo no Elliptic++)
    AddrAddr_edgelist.csv             ← arestas wallet→wallet
    wallets_features.csv              ← features por wallet address
    wallets_classes.csv               ← labels de wallet (exchanges, mixers, etc.)
    wallets_features_classes_combined.csv  ← combinado features+labels wallets
```

**Nota:** Subfolder se chama `Elliptic++ Dataset` (NÃO `Transactions Dataset` como documentado originalmente).

**Stats (Transactions Dataset):**
```
Nós:     203,769 transações Bitcoin
Arestas: 234,355 tx→tx  +  adicionais tx→wallet
Labels:  4,545 illicit | 42,019 licit | 157,205 unknown
49 time steps
```

**Para BTCS:**
- Compatível com loader Elliptic original (node→edge label propagation)
- `delta_L = 2` time steps
- Loader: `load_elliptic_plus()` em nb04 Cell 4B

---

## GNN Score Files (nb05 output)

O notebook `nb05_gnn_training.ipynb` treina GraphSAGE em cada dataset e salva:

```
GrafosGNN/results/nb05_gnn/
  {dataset_name}_gnn_scores.npz    ← {p, y, src, dst, timestamps}
```

Datasets com scores GNN (nb05):
- `ibm_aml_txns`, `IBM_HI_Small`, `IBM_HI_Medium`, `IBM_HI_Large`
- `IBM_LI_Small`, `IBM_LI_Medium`, `IBM_LI_Large`
- `elliptic`, `elliptic_plus`, `amazon_fraud`, `yelp_fraud`, `paysim`
- `dgraph_fin`, `t_finance` (quando disponíveis)

---

## Convenções de Path

```python
# Colab (Google Drive montado)
IN_COLAB = 'google.colab' in sys.modules
BASE = Path('/content/drive/MyDrive') if IN_COLAB else Path('.').resolve()

# Datasets grandes (AMLSim AML100k/AML1M)
AML100K_BASE = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'

# Datasets no repo GrafosGNN (versionados via .gitignore de dados grandes)
DATA    = BASE / 'GrafosGNN/data'        # bitcoin, elliptic, paysim, ibm_aml, libra, etc.
RESULTS = BASE / 'GrafosGNN/results'     # outputs dos notebooks
```

**Drive local (macOS):**
```
~/Library/CloudStorage/GoogleDrive-acsilva@gmail.com/Meu Drive/GrafosGNN/data/
```

---

## Datasets Ausentes / Não Sincronizados

| Dataset | Motivo | Solução |
|---------|--------|---------|
| AML100k/AML1M CSV brutos | Tamanho (>10GB) — só artefatos .pt/.npz sincronizados localmente | Usar no Colab |
| IBM HI/LI Medium/Large | RAM insuficiente localmente | Usar no Colab com A100 |
| DatasetDissertacao/ (local) | Pasta não sincronizada pelo Google Drive Stream | Abrir no Colab |
| **DGraph-Fin** | ✅ `data/dgraph_fin/raw/dgraphfin.npz` (numpy, 649MB) | https://dgraph.xinye.com/dataset |
| **T-Finance** | ✅ `data/t_finance/tfinance` (DGL binary, 652MB) | https://drive.google.com/drive/folders/1PpNwvZx_YRSCDiHaBUmRIS3x1rZR7fMr |
| **Elliptic++** | ✅ `data/elliptic_plus/Elliptic++ Dataset/` (CSV) | https://drive.google.com/drive/folders/1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l |

---

*Fim do arquivo de referência de datasets.*
