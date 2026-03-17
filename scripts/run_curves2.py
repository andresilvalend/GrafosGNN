#!/usr/bin/env python3
"""Pass 2: purity curves para elliptic, btc, amazon, yelp, t_finance.
   Roda DGraph-Fin separado (muito RAM).
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

# ── PURITY CURVE FUNCTION ─────────────────────────────────────────────────
def compute_purity_curve(cases, y_edges, scores, budget_B=100):
    y = np.asarray(y_edges, dtype=int)
    S = np.asarray(scores,  dtype=np.float32)
    if not cases:
        return np.array([0]), np.array([0.0]), 0.0, 0.0, 0

    case_data = []
    for c in cases:
        all_idx = np.array(
            list(c.get('seed_edges', [])) + list(c.get('induced_edges', [])),
            dtype=np.int64)
        all_idx = all_idx[all_idx < len(y)]
        if len(all_idx) == 0:
            continue
        seed_idx = np.array(c.get('seed_edges', []), dtype=np.int64)
        seed_idx = seed_idx[seed_idx < len(S)]
        case_score = float(S[seed_idx].mean()) if len(seed_idx) > 0 else 0.0
        case_data.append({'score': case_score, 'n': len(all_idx),
                          'n_fraud': int(y[all_idx].sum())})
    if not case_data:
        return np.array([0]), np.array([0.0]), 0.0, 0.0, 0

    case_data.sort(key=lambda x: -x['score'])
    cum_n, cum_fraud = 0, 0
    xs, ys = [0], [0.0]
    for c in case_data:
        cum_n += c['n']; cum_fraud += c['n_fraud']
        xs.append(cum_n); ys.append(cum_fraud / cum_n if cum_n > 0 else 0.0)
    xs, ys = np.array(xs, dtype=np.float64), np.array(ys, dtype=np.float64)

    total   = xs[-1] if xs[-1] > 0 else 1.0
    auc_raw = float(np.trapz(ys, xs))
    auc_norm = auc_raw / total

    budget, fraud_b, n_cases_b = budget_B, 0.0, 0
    for c in case_data:
        if budget <= 0: break
        take = min(c['n'], budget)
        fraud_b += c['n_fraud'] * (take / c['n']) if c['n'] > 0 else 0
        budget -= take
        if take == c['n']: n_cases_b += 1
    yield_b = fraud_b / budget_B if budget_B > 0 else 0.0

    return xs, ys, auc_norm, yield_b, n_cases_b


# ── LOADERS ───────────────────────────────────────────────────────────────
def _load_amazon(max_edges=500_000):
    ds = load_mat_fraud('amazon_fraud', 'Amazon.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        idx = np.random.RandomState(42).choice(n, max_edges, replace=False); idx.sort()
        for k2 in ['src','dst','scores','y','timestamps']: ds[k2] = ds[k2][idx]
        ds['n_edges'] = max_edges
    ds['delta_L'] = max(100, ds['n_edges'] // 100)
    return ds

def _load_yelp(max_edges=500_000):
    ds = load_mat_fraud('yelp_fraud', 'YelpChi.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        idx = np.random.RandomState(42).choice(n, max_edges, replace=False); idx.sort()
        for k2 in ['src','dst','scores','y','timestamps']: ds[k2] = ds[k2][idx]
        ds['n_edges'] = max_edges
    ds['delta_L'] = max(100, ds['n_edges'] // 100)
    return ds

def _load_t_finance():
    fp = next((DATA/'t_finance'/f for f in ['tfinance','t-finance.pt']
               if (DATA/'t_finance'/f).exists()), None)
    if not fp: return None
    import dgl
    gs, _ = dgl.load_graphs(str(fp)); g = gs[0]
    labels = g.ndata['label'].numpy().astype(int); y_node = labels[:, 1]
    s_all, d_all = g.edges()
    s_all = s_all.numpy().astype(np.int64); d_all = d_all.numpy().astype(np.int64)
    del g, gs, labels; gc.collect()
    MAX = 2_000_000
    idx = np.random.RandomState(42).choice(len(s_all), MAX, replace=False); idx.sort()
    src = s_all[idx]; dst = d_all[idx]; del s_all, d_all; gc.collect()
    feat = np.where(y_node==1, 0.9, 0.1).astype(np.float32)
    scores = np.maximum(feat[src], feat[dst])
    scores += np.random.RandomState(42).uniform(0, 0.01, len(src))
    y_edge = np.maximum(y_node[src], y_node[dst]).astype(int)
    return {'name':'t_finance','scores':scores,'src':src,'dst':dst,
            'timestamps':np.arange(len(src),dtype=np.int64),'y':y_edge,
            'n_nodes':int(y_node.shape[0]),'n_edges':len(src),'delta_L':100_000}


DATASET_LOADERS = [
    ('elliptic',      load_elliptic),
    ('bitcoin_alpha', lambda: load_bitcoin_otc_alpha('bitcoin_alpha')),
    ('bitcoin_otc',   lambda: load_bitcoin_otc_alpha('bitcoin_otc')),
    ('amazon_fraud',  _load_amazon),
    ('yelp_fraud',    _load_yelp),
    ('t_finance',     _load_t_finance),
]

KS = [0.01, 0.05, 0.10]; B = 100; B3_MAX = 5_000_000

# ── Carrega resultados anteriores ─────────────────────────────────────────
prev_csv = OUT / 'purity_curves_metrics.csv'
if prev_csv.exists():
    df_prev = pd.read_csv(prev_csv)
    rows_agg = df_prev.to_dict('records')
    done_ds  = set(df_prev['dataset'].unique())
    print(f'Loaded {len(rows_agg)} prev rows | done: {sorted(done_ds)}')
else:
    rows_agg = []; done_ds = set()

curves = {}

# ── PIPELINE ──────────────────────────────────────────────────────────────
for ds_name, loader_fn in DATASET_LOADERS:
    if ds_name in done_ds:
        print(f'[SKIP] {ds_name} already done'); continue
    gc.collect()
    avail = psutil.virtual_memory().available / 1e9
    if avail < 0.8:
        print(f'[SKIP] {ds_name} RAM={avail:.1f}GB'); continue

    print(f'\n{"─"*55}\n  {ds_name}  RAM={avail:.1f}GB')
    try:
        ds = loader_fn()
    except Exception as e:
        print(f'  [ERR] {e}'); continue
    if ds is None:
        print('  [SKIP] None'); continue

    name = ds['name']
    for method_name, method_fn in METHODS.items():
        skip = (method_name == 'B3_Greedy' and ds['n_edges'] > B3_MAX)
        for k in KS:
            kp = f'{int(k*100)}%'
            if skip:
                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':np.nan,'yield_b100':np.nan,'n_cases_b100':np.nan})
                continue
            try:
                if method_name == 'BTCS_v3':
                    cases = method_fn(ds['scores'],ds['src'],ds['dst'],
                                      ds['timestamps'],ds['y'],
                                      k=k,delta_L=ds['delta_L'],resolution=1.0,budget_B=B)
                else:
                    cases = method_fn(ds['scores'],ds['src'],ds['dst'],
                                      ds['timestamps'],ds['y'],k=k,budget_B=B)
                xs,ys,auc,yb,ncb = compute_purity_curve(cases,ds['y'],ds['scores'],B)
                xs_n = xs / xs[-1] if xs[-1] > 0 else xs
                curves[(name,method_name,kp)] = (xs_n, ys)
                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':round(auc,4),'yield_b100':round(yb,4),
                                 'n_cases_b100':ncb})
                print(f'  [{method_name}] k={kp}: AUC={auc:.3f} yield@100={yb:.3f}')
            except Exception as e:
                print(f'  [{method_name}] k={kp}: ERR {e}')
                rows_agg.append({'dataset':name,'method':method_name,'k%':kp,
                                 'auc_purity':np.nan,'yield_b100':np.nan,'n_cases_b100':np.nan})
    del ds; gc.collect()
    pd.DataFrame(rows_agg).to_csv(OUT/'purity_curves_metrics.csv', index=False)
    print(f'  [checkpoint] {len(rows_agg)} rows')

# ── SAVE + FIGURES ────────────────────────────────────────────────────────
df_all = pd.DataFrame(rows_agg)
df_all.to_csv(OUT / 'purity_curves_metrics.csv', index=False)
print(f'\n✅ {len(df_all)} rows | {df_all.dataset.nunique()} datasets')

METHODS_ORDER = ['BTCS_v3','B0_Random','B1_WCC','B2_Louvain','B3_Greedy']
METHOD_COLORS = {'BTCS_v3':'#E63946','B0_Random':'#457B9D','B1_WCC':'#2A9D8F',
                 'B2_Louvain':'#E9C46A','B3_Greedy':'#8338EC'}
METHOD_LABELS = {'BTCS_v3':'BTCS v3 (ours)','B0_Random':'B0 Random',
                 'B1_WCC':'B1 WCC','B2_Louvain':'B2 Louvain','B3_Greedy':'B3 Greedy'}
DS_LABELS = {'elliptic':'Elliptic (BTC)','amazon_fraud':'Amazon (500K)',
             'dgraph_fin':'DGraph-Fin','bitcoin_otc':'BTC-OTC',
             'bitcoin_alpha':'BTC-Alpha','yelp_fraud':'Yelp (500K)',
             't_finance':'T-Finance (2M)'}

# Fig 5: curvas para os datasets que temos nesta passada
ds_available = [d for d in ['elliptic','bitcoin_otc','amazon_fraud','yelp_fraud',
                             't_finance','bitcoin_alpha']
                if any((d,m,'5%') in curves for m in METHODS_ORDER)]

if ds_available:
    ncols = min(4, len(ds_available))
    nrows = math.ceil(len(ds_available) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols*4.5, nrows*4))
    axes = np.array(axes).flatten() if hasattr(axes, '__iter__') else [axes]

    for ax, ds in zip(axes, ds_available):
        for m in METHODS_ORDER:
            key = (ds, m, '5%')
            if key not in curves: continue
            xs_n, ys = curves[key]
            lw = 2.5 if m=='BTCS_v3' else 1.4
            ls = '-'  if m=='BTCS_v3' else '--'
            ax.plot(xs_n*100, ys*100, color=METHOD_COLORS[m],
                    lw=lw, ls=ls, label=METHOD_LABELS[m], alpha=0.9)

        sub = df_all[(df_all.dataset==ds)&(df_all['k%']=='5%')&(df_all.method=='BTCS_v3')]
        if not sub.empty and not pd.isna(sub['yield_b100'].values[0]):
            ax.annotate(f"yield@100={sub['yield_b100'].values[0]:.2f}",
                        xy=(3,93), fontsize=8, color=METHOD_COLORS['BTCS_v3'],
                        bbox=dict(boxstyle='round,pad=0.2',fc='white',alpha=0.8))

        ax.set_title(DS_LABELS.get(ds,ds), fontsize=10, fontweight='bold')
        ax.set_xlabel('Casos abertos (% total)', fontsize=8)
        ax.set_ylabel('Pureza acumulada (%)', fontsize=8)
        ax.set_xlim(0,100); ax.set_ylim(0,105)
        ax.grid(True, alpha=0.3, ls='--')

    for ax in axes[len(ds_available):]: ax.set_visible(False)

    legend_lines = [plt.Line2D([0],[0], color=METHOD_COLORS[m],
                                lw=2 if m=='BTCS_v3' else 1.4,
                                ls='-' if m=='BTCS_v3' else '--',
                                label=METHOD_LABELS[m]) for m in METHODS_ORDER]
    fig.legend(handles=legend_lines, loc='lower center', ncol=5,
               fontsize=9, bbox_to_anchor=(0.5,-0.04), framealpha=0.9)
    fig.suptitle('Curva de Pureza Acumulada por Caso (k=5%)',
                 fontsize=12, fontweight='bold')
    plt.tight_layout()
    fig.savefig(FIGS/'fig5_purity_curves_k5.png', dpi=150, bbox_inches='tight')
    plt.close()
    print('Fig 5 updated.')

# Heatmap AUC
df5 = df_all[df_all['k%']=='5%']
pivot = df5.pivot_table(index='dataset', columns='method',
                         values='auc_purity', aggfunc='first')
if 'BTCS_v3' in pivot.columns:
    pivot = pivot.sort_values('BTCS_v3', ascending=False)
cols = [m for m in METHODS_ORDER if m in pivot.columns]
pivot = pivot[cols]

fig, ax = plt.subplots(figsize=(10,5))
data = pivot.values.astype(float)
im = ax.imshow(data, aspect='auto', cmap='RdYlGn', vmin=0, vmax=1)
ax.set_xticks(range(len(cols)))
ax.set_xticklabels([METHOD_LABELS[m] for m in cols], fontsize=9)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels([DS_LABELS.get(d,d) for d in pivot.index], fontsize=9)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i,j]
        txt = f'{v:.3f}' if not np.isnan(v) else '—'
        color = 'white' if (not np.isnan(v) and (v<0.3 or v>0.7)) else 'black'
        ax.text(j,i,txt,ha='center',va='center',fontsize=8,color=color)
plt.colorbar(im, ax=ax, label='AUC Purity Curve')
ax.set_title('AUC da Curva de Pureza Acumulada @ k=5%', fontsize=11, fontweight='bold')
plt.tight_layout()
fig.savefig(FIGS/'fig6_auc_heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 6 updated.')

print('\n=== AUC Purity @ k=5% ===')
print(pivot.round(3).to_string())
print('\n=== yield@B=100 @ k=5% ===')
pvy = df5.pivot_table(index='dataset',columns='method',values='yield_b100',aggfunc='first')
pvy = pvy.reindex(pivot.index)
cols_y = [m for m in METHODS_ORDER if m in pvy.columns]
print(pvy[cols_y].round(3).to_string())
