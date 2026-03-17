#!/usr/bin/env python3
"""
Computa case-ranked purity curves para todos os datasets.

Para cada dataset × método × k:
  - Ordena casos por score médio decrescente
  - Computa purity acumulada à medida que casos são abertos
  - Extrai: AUC da curva, yield@B=100 (H1), e curva completa

Outputs:
  results/nb04_multi_dataset/purity_curves.csv   (AUC + yield_b100 por run)
  results/nb04_multi_dataset/figures/fig5_purity_curves_k5.png
  results/nb04_multi_dataset/figures/fig6_auc_heatmap.png
"""
import sys, os, gc, time, math, contextlib, warnings
sys.path.insert(0, '/sessions/friendly-modest-rubin/.local/lib/python3.10/site-packages')
os.environ.setdefault('DGLBACKEND', 'pytorch')
warnings.filterwarnings('ignore')
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import psutil
import igraph as ig
import leidenalg
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

_GDRIVE = Path('/sessions/friendly-modest-rubin/mnt/Meu Drive')
_REPO   = Path('/sessions/friendly-modest-rubin/mnt/GrafosGNN')
BASE    = _GDRIVE
DATA    = BASE / 'GrafosGNN/data'
OUT     = _REPO / 'results/nb04_multi_dataset'
FIGS    = OUT / 'figures'
FIGS.mkdir(parents=True, exist_ok=True)
GNN_SCORES   = _REPO / 'results/nb05_gnn_scores'
AML100K_BASE = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'

exec(open('/tmp/core_cells.py').read(), globals())

# ── NOVA MÉTRICA ──────────────────────────────────────────────────────────
def compute_purity_curve(cases, y_edges, scores, budget_B=100):
    """
    Computa a curva de pureza acumulada por caso.

    Retorna:
        curve_x   : array de N_casos+1 pontos — edges acumuladas abertas
        curve_y   : array de N_casos+1 pontos — purity acumulada
        auc_norm  : AUC normalizada pela area total (0..1)
        yield_b   : pureza ao abrir os primeiros B edges (H1)
        n_cases_b : quantos casos cabem dentro do budget B
    """
    y = np.asarray(y_edges, dtype=int)
    S = np.asarray(scores, dtype=np.float32)

    if not cases:
        return np.array([0]), np.array([0.0]), 0.0, 0.0, 0

    case_data = []
    for c in cases:
        # conteúdo completo que o analista vê = seed + induced
        all_idx = np.array(
            list(c.get('seed_edges', [])) + list(c.get('induced_edges', [])),
            dtype=np.int64)
        all_idx = all_idx[all_idx < len(y)]
        if len(all_idx) == 0:
            continue

        # score do caso = média dos scores das seed edges
        seed_idx = np.array(c.get('seed_edges', []), dtype=np.int64)
        seed_idx = seed_idx[seed_idx < len(S)]
        case_score = float(S[seed_idx].mean()) if len(seed_idx) > 0 else 0.0

        case_data.append({
            'score':   case_score,
            'n':       len(all_idx),
            'n_fraud': int(y[all_idx].sum()),
        })

    if not case_data:
        return np.array([0]), np.array([0.0]), 0.0, 0.0, 0

    # ordena por score decrescente
    case_data.sort(key=lambda x: -x['score'])

    # curva acumulada
    cum_n = 0
    cum_fraud = 0
    xs = [0]
    ys = [0.0]
    for c in case_data:
        cum_n     += c['n']
        cum_fraud += c['n_fraud']
        pur = cum_fraud / cum_n if cum_n > 0 else 0.0
        xs.append(cum_n)
        ys.append(pur)
    xs = np.array(xs, dtype=np.float64)
    ys = np.array(ys, dtype=np.float64)

    # AUC normalizada (eixo x normalizado por total de edges)
    total = xs[-1] if xs[-1] > 0 else 1.0
    auc_raw = float(np.trapz(ys, xs))
    auc_norm = auc_raw / total  # em [0,1]

    # yield@B = H1: purity ao acumular B edges
    budget = budget_B
    fraud_b = 0.0
    n_cases_b = 0
    for c in case_data:
        if budget <= 0:
            break
        take = min(c['n'], budget)
        # proporcional (se caso não cabe inteiro pega fração)
        frac = take / c['n'] if c['n'] > 0 else 0.0
        fraud_b += c['n_fraud'] * frac
        budget -= take
        if take == c['n']:
            n_cases_b += 1

    yield_b = fraud_b / budget_B if budget_B > 0 else 0.0

    return xs, ys, auc_norm, yield_b, n_cases_b


# ── LOADERS (igual run_last3.py) ──────────────────────────────────────────
def _load_amazon(max_edges=500_000):
    ds = load_mat_fraud('amazon_fraud', 'Amazon.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        rng = np.random.RandomState(42)
        idx = rng.choice(n, max_edges, replace=False); idx.sort()
        for k in ['src','dst','scores','y','timestamps']: ds[k] = ds[k][idx]
        ds['n_edges'] = max_edges
    ds['delta_L'] = max(100, ds['n_edges'] // 100)
    return ds

def _load_yelp(max_edges=500_000):
    ds = load_mat_fraud('yelp_fraud', 'YelpChi.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        rng = np.random.RandomState(42)
        idx = rng.choice(n, max_edges, replace=False); idx.sort()
        for k in ['src','dst','scores','y','timestamps']: ds[k] = ds[k][idx]
        ds['n_edges'] = max_edges
    ds['delta_L'] = max(100, ds['n_edges'] // 100)
    return ds

def _load_t_finance():
    t_dir = DATA / 't_finance'
    fp = next((t_dir/f for f in ['tfinance','t-finance.pt'] if (t_dir/f).exists()), None)
    if not fp: return None
    import dgl
    gs, _ = dgl.load_graphs(str(fp))
    g = gs[0]
    labels = g.ndata['label'].numpy().astype(int)
    y_node = labels[:, 1]
    src_all, dst_all = g.edges()
    src_all = src_all.numpy().astype(np.int64)
    dst_all = dst_all.numpy().astype(np.int64)
    del g, gs, labels; gc.collect()
    n_nodes = int(y_node.shape[0])
    MAX = 2_000_000
    idx = np.random.RandomState(42).choice(len(src_all), MAX, replace=False); idx.sort()
    src = src_all[idx]; dst = dst_all[idx]
    del src_all, dst_all; gc.collect()
    feat = np.where(y_node == 1, 0.9, 0.1).astype(np.float32)
    scores = np.maximum(feat[src], feat[dst])
    scores += np.random.RandomState(42).uniform(0, 0.01, len(src))
    y_edge = np.maximum(y_node[src], y_node[dst]).astype(int)
    return {'name':'t_finance','scores':scores,'src':src,'dst':dst,
            'timestamps':np.arange(len(src),dtype=np.int64),'y':y_edge,
            'n_nodes':n_nodes,'n_edges':len(src),'delta_L':100_000}

# ── DATASETS ─────────────────────────────────────────────────────────────
DATASET_LOADERS = [
    ('elliptic',      lambda: _gnn_or('elliptic', load_elliptic)),
    ('bitcoin_alpha', lambda: _gnn_or('bitcoin_alpha', lambda: load_bitcoin_otc_alpha('bitcoin_alpha'))),
    ('bitcoin_otc',   lambda: _gnn_or('bitcoin_otc',   lambda: load_bitcoin_otc_alpha('bitcoin_otc'))),
    ('dgraph_fin',    load_dgraph_fin),
    ('amazon_fraud',  _load_amazon),
    ('yelp_fraud',    _load_yelp),
    ('t_finance',     _load_t_finance),
]

KS     = [0.01, 0.05, 0.10]
GAMMA  = 1.0
B      = 100
B3_MAX = 5_000_000

# ── COLETA DE CURVAS ──────────────────────────────────────────────────────
rows_agg = []    # métricas agregadas (AUC, yield_b100)
curves   = {}    # (ds_name, method, k%) → (xs_norm, ys)

for ds_name, loader_fn in DATASET_LOADERS:
    gc.collect()
    avail = psutil.virtual_memory().available / 1e9
    if avail < 1.0:
        print(f'[SKIP] {ds_name} RAM={avail:.1f}GB'); continue

    print(f'\n{"─"*55}\n  {ds_name}')
    try:
        ds = loader_fn()
    except Exception as e:
        print(f'  [ERR] {e}'); continue
    if ds is None:
        print('  [SKIP] None'); continue

    name = ds['name']
    for method_name, method_fn in METHODS.items():
        skip_b3 = (method_name == 'B3_Greedy' and ds['n_edges'] > B3_MAX)
        for k in KS:
            kp = f'{int(k*100)}%'
            if skip_b3:
                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':np.nan,'yield_b100':np.nan,'n_cases_b100':np.nan})
                continue
            try:
                if method_name == 'BTCS_v3':
                    cases = method_fn(ds['scores'], ds['src'], ds['dst'],
                                      ds['timestamps'], ds['y'],
                                      k=k, delta_L=ds['delta_L'],
                                      resolution=GAMMA, budget_B=B)
                else:
                    cases = method_fn(ds['scores'], ds['src'], ds['dst'],
                                      ds['timestamps'], ds['y'],
                                      k=k, budget_B=B)

                xs, ys, auc, yield_b, n_cb = compute_purity_curve(
                    cases, ds['y'], ds['scores'], budget_B=B)

                # normaliza eixo x para [0,1] para comparação entre datasets
                xs_norm = xs / xs[-1] if xs[-1] > 0 else xs
                curves[(name, method_name, kp)] = (xs_norm, ys)

                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':round(auc,4),
                                 'yield_b100':round(yield_b,4),
                                 'n_cases_b100':n_cb})
                print(f'  [{method_name}] k={kp}: AUC={auc:.3f} yield@100={yield_b:.3f}')
            except Exception as e:
                print(f'  [{method_name}] k={kp}: ERR {e}')
                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':np.nan,'yield_b100':np.nan,'n_cases_b100':np.nan})
    del ds; gc.collect()

# ── SALVA CSV ─────────────────────────────────────────────────────────────
df_curves = pd.DataFrame(rows_agg)
df_curves.to_csv(OUT / 'purity_curves_metrics.csv', index=False)
print(f'\n✅ {len(df_curves)} runs salvas.')

# ── FIGURA 5: Curvas k=5% para 4 datasets representativos ────────────────
REPR_DS = ['elliptic', 'amazon_fraud', 'dgraph_fin', 'bitcoin_otc']
METHODS_ORDER = ['BTCS_v3', 'B0_Random', 'B1_WCC', 'B2_Louvain', 'B3_Greedy']
METHOD_COLORS = {
    'BTCS_v3':    '#E63946',
    'B0_Random':  '#457B9D',
    'B1_WCC':     '#2A9D8F',
    'B2_Louvain': '#E9C46A',
    'B3_Greedy':  '#8338EC',
}
METHOD_LABELS = {
    'BTCS_v3': 'BTCS v3 (ours)',
    'B0_Random': 'B0 Random',
    'B1_WCC': 'B1 WCC',
    'B2_Louvain': 'B2 Louvain',
    'B3_Greedy': 'B3 Greedy',
}
DS_LABELS = {
    'elliptic': 'Elliptic (BTC)', 'amazon_fraud': 'Amazon (500K)',
    'dgraph_fin': 'DGraph-Fin', 'bitcoin_otc': 'BTC-OTC',
    'bitcoin_alpha': 'BTC-Alpha', 'yelp_fraud': 'Yelp (500K)',
    't_finance': 'T-Finance (2M)',
}

fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
for ax, ds in zip(axes, REPR_DS):
    for m in METHODS_ORDER:
        key = (ds, m, '5%')
        if key not in curves: continue
        xs_n, ys = curves[key]
        lw = 2.5 if m == 'BTCS_v3' else 1.4
        ls = '-'  if m == 'BTCS_v3' else '--'
        ax.plot(xs_n * 100, ys * 100, color=METHOD_COLORS[m],
                lw=lw, ls=ls, label=METHOD_LABELS[m], alpha=0.9)

    ax.set_title(DS_LABELS.get(ds, ds), fontsize=10, fontweight='bold')
    ax.set_xlabel('Casos abertos (% do total)', fontsize=9)
    ax.set_ylabel('Pureza acumulada (%)', fontsize=9)
    ax.set_xlim(0, 100); ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, ls='--')

    # anotação yield@B=100
    sub = df_curves[(df_curves.dataset == ds) & (df_curves['k%'] == '5%')]
    btcs_row = sub[sub.method == 'BTCS_v3']
    if not btcs_row.empty and not pd.isna(btcs_row['yield_b100'].values[0]):
        ax.annotate(f"yield@100\n= {btcs_row['yield_b100'].values[0]:.2f}",
                    xy=(5, 95), fontsize=7.5, color=METHOD_COLORS['BTCS_v3'],
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7))

import matplotlib.patches as mpatches
legend_patches = [plt.Line2D([0],[0], color=METHOD_COLORS[m], lw=2 if m=='BTCS_v3' else 1.4,
                              ls='-' if m=='BTCS_v3' else '--', label=METHOD_LABELS[m])
                  for m in METHODS_ORDER]
fig.legend(handles=legend_patches, loc='lower center', ncol=5,
           fontsize=9, bbox_to_anchor=(0.5, -0.05), framealpha=0.9)
fig.suptitle('Curva de Pureza Acumulada por Caso (k=5%) — BTCS v3 vs Baselines',
             fontsize=12, fontweight='bold')
plt.tight_layout()
fig.savefig(FIGS / 'fig5_purity_curves_k5.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 5 saved.')

# ── FIGURA 6: Heatmap AUC (datasets × métodos) @ k=5% ───────────────────
df5 = df_curves[df_curves['k%'] == '5%'].copy()
pivot_auc = df5.pivot_table(index='dataset', columns='method',
                             values='auc_purity', aggfunc='first')
# ordena datasets por BTCS_v3 AUC
if 'BTCS_v3' in pivot_auc.columns:
    pivot_auc = pivot_auc.sort_values('BTCS_v3', ascending=False)
# reordena colunas
cols = [m for m in METHODS_ORDER if m in pivot_auc.columns]
pivot_auc = pivot_auc[cols]

fig, ax = plt.subplots(figsize=(10, 5))
import matplotlib.colors as mcolors
data = pivot_auc.values.astype(float)
im = ax.imshow(data, aspect='auto', cmap='RdYlGn', vmin=0, vmax=1)
ax.set_xticks(range(len(cols)))
ax.set_xticklabels([METHOD_LABELS[m] for m in cols], fontsize=9)
ax.set_yticks(range(len(pivot_auc.index)))
ax.set_yticklabels([DS_LABELS.get(d, d) for d in pivot_auc.index], fontsize=9)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i, j]
        txt = f'{v:.3f}' if not np.isnan(v) else '—'
        color = 'white' if (v < 0.3 or v > 0.7) and not np.isnan(v) else 'black'
        ax.text(j, i, txt, ha='center', va='center', fontsize=8, color=color)
plt.colorbar(im, ax=ax, label='AUC Purity Curve')
ax.set_title('AUC da Curva de Pureza Acumulada @ k=5%\n(mais alto = melhor rankeamento de casos)',
             fontsize=11, fontweight='bold')
plt.tight_layout()
fig.savefig(FIGS / 'fig6_auc_heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 6 saved.')

# ── TABELA RESUMO ─────────────────────────────────────────────────────────
print('\n=== AUC Purity Curve @ k=5% ===')
print(pivot_auc.round(3).to_string())

print('\n=== yield@B=100 (H1) @ k=5% ===')
pivot_yield = df5.pivot_table(index='dataset', columns='method',
                               values='yield_b100', aggfunc='first')
if 'BTCS_v3' in pivot_yield.columns:
    pivot_yield = pivot_yield.reindex(pivot_auc.index)
cols_y = [m for m in METHODS_ORDER if m in pivot_yield.columns]
print(pivot_yield[cols_y].round(3).to_string())
