#!/usr/bin/env python3
"""
Ablation study — BTCS v3 component contributions
Compara 3 variantes em 5 datasets representativos:
  A1: WCC_only     — WCC sem sub-segmentação (= B1_WCC)
  A2: Leiden_flat  — Leiden direto no subgrafo top-k (sem WCC prévia, sem janela temporal)
  A3: BTCS_v3      — WCC + Leiden temporal (pipeline completo)

Pergunta central: cada componente (WCC hierárquico + janela temporal Lk) contribui?
"""
import sys, os, gc, time, math, warnings
sys.path.insert(0, '/sessions/friendly-modest-rubin/.local/lib/python3.10/site-packages')
warnings.filterwarnings('ignore')
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import igraph as ig
import leidenalg
import contextlib
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

_GDRIVE = Path('/sessions/friendly-modest-rubin/mnt/Meu Drive')
_REPO   = Path('/sessions/friendly-modest-rubin/mnt/GrafosGNN')
DATA    = _REPO / "data"
GNN_SCORES   = _REPO / 'results/nb05_gnn_scores'
AML100K_BASE = _GDRIVE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = _GDRIVE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'
OUT    = _REPO / 'results/nb07_ablation'
FIGS   = OUT / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

exec(open('/tmp/core_cells.py').read(), globals())

# ══════════════════════════════════════════════════════════════════════════
# Leiden flat: Leiden direto no subgrafo top-k sem hierarquia
# ══════════════════════════════════════════════════════════════════════════
def btcs_leiden_flat(scores, src, dst, timestamps, y,
                     k=0.01, delta_L=None, resolution=1.0, budget_B=100, seed=42, **kw):
    """A2: Leiden direto no subgrafo top-k.
    Sem WCC prévia, sem janela temporal Lk — só Leiden na adjacência top-k.
    """
    scores = np.asarray(scores, dtype=float)
    src    = np.asarray(src,    dtype=np.int64)
    dst    = np.asarray(dst,    dtype=np.int64)
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    src_sel, dst_sel = src[sel], dst[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    # Build igraph sobre top-k
    all_nodes = np.unique(np.concatenate([src_sel, dst_sel]))
    nmap = {int(n): i for i, n in enumerate(all_nodes)}
    edges_compact = [(nmap[int(s)], nmap[int(d)]) for s, d in zip(src_sel, dst_sel)]
    g = ig.Graph(n=len(all_nodes), edges=edges_compact, directed=False)
    g.simplify()

    # Leiden direto (sem janela temporal — usa adjacência completa top-k)
    part = leidenalg.find_partition(
        g, leidenalg.RBConfigurationVertexPartition,
        resolution_parameter=resolution, seed=seed)
    leiden_mem = np.array(part.membership, dtype=np.int64)
    n_parts = int(leiden_mem.max()) + 1

    # Atribuir cada edge top-k à sua partição (maioria dos endpoints)
    edge_parts = np.array([leiden_mem[nmap[int(s)]] for s in src_sel], dtype=np.int64)

    part_edge_lists = defaultdict(list)
    part_node_sets  = defaultdict(set)
    for i in range(K):
        p = int(edge_parts[i])
        part_edge_lists[p].append(i)
        part_node_sets[p].update([int(src_sel[i]), int(dst_sel[i])])

    # Induzir arestas e montar casos
    cases = []
    for p, comp in part_edge_lists.items():
        nodes = part_node_sets[p]
        # Arestas induzidas no grafo completo
        node_mask = -np.ones(max_node, dtype=np.int64)
        for nid in nodes:
            node_mask[nid] = 1
        g_s = np.where(src < max_node, node_mask[src], -1)
        g_d = np.where(dst < max_node, node_mask[dst], -1)
        ind = np.where((g_s == 1) & (g_d == 1))[0]
        if len(ind) > budget_B:
            ind = ind[np.argsort(-scores[ind])[:budget_B]]
        cases.append({
            'nodes': nodes,
            'seed_edges': comp,
            'induced_edges': ind.tolist()
        })

    n_large_before = sum(1 for p, comp in part_edge_lists.items()
                         if len(comp) >= budget_B)
    print(f'  [Leiden_flat] {len(cases)} cases | parts_large(≥B)={n_large_before}')
    return cases

# ══════════════════════════════════════════════════════════════════════════
# Purity curve (same as run_curves2)
# ══════════════════════════════════════════════════════════════════════════
def compute_purity_curve(cases, y_edges, scores, budget_B=100):
    y = np.asarray(y_edges, dtype=int)
    S = np.asarray(scores, dtype=np.float32)
    if not cases:
        return np.array([0.0]), np.array([0.0]), 0.0, 0.0, 0
    case_data = []
    for c in cases:
        all_idx = np.array(
            list(c.get('seed_edges', [])) + list(c.get('induced_edges', [])),
            dtype=np.int64)
        all_idx = all_idx[all_idx < len(y)]
        if len(all_idx) == 0: continue
        seed_idx = np.array(c.get('seed_edges', []), dtype=np.int64)
        seed_idx = seed_idx[seed_idx < len(S)]
        case_score = float(S[seed_idx].mean()) if len(seed_idx) > 0 else 0.0
        case_data.append({'score': case_score, 'n': len(all_idx),
                          'n_fraud': int(y[all_idx].sum())})
    if not case_data:
        return np.array([0.0]), np.array([0.0]), 0.0, 0.0, 0
    case_data.sort(key=lambda x: -x['score'])
    cum_n, cum_fraud = 0, 0
    xs, ys = [0], [0.0]
    for c in case_data:
        cum_n += c['n']; cum_fraud += c['n_fraud']
        xs.append(cum_n); ys.append(cum_fraud/cum_n if cum_n > 0 else 0.0)
    xs = np.array(xs, dtype=np.float64)
    ys = np.array(ys, dtype=np.float64)
    total = xs[-1] if xs[-1] > 0 else 1.0
    auc_norm = float(np.trapz(ys, xs)) / total
    budget, fraud_b, n_cb = budget_B, 0.0, 0
    for c in case_data:
        if budget <= 0: break
        take = min(c['n'], budget)
        fraud_b += c['n_fraud'] * (take/c['n']) if c['n'] > 0 else 0
        budget -= take
        if take == c['n']: n_cb += 1
    yield_b = fraud_b / budget_B if budget_B > 0 else 0.0
    return xs, ys, auc_norm, yield_b, n_cb

# ══════════════════════════════════════════════════════════════════════════
# Dataset loaders (5 representativos, sem OOM)
# ══════════════════════════════════════════════════════════════════════════
# static graphs (Amazon/Yelp) = single giant WCC → only k=1% is safe
# temporal graphs (Elliptic, BTC, T-Finance) = multiple WCCs → all k values
DATASETS = [
    ('elliptic',      load_elliptic,                            [0.01, 0.05, 0.10]),
    ('amazon_fraud',  lambda: load_mat_fraud('amazon_fraud', 'Amazon.mat'), [0.01]),
    ('yelp_fraud',    lambda: load_mat_fraud('yelp_fraud',   'YelpChi.mat'), [0.01]),
    ('bitcoin_otc',   lambda: load_bitcoin_otc_alpha('bitcoin_otc'), [0.01, 0.05, 0.10]),
    ('t_finance',     load_t_finance,                           [0.01, 0.05, 0.10]),
]

# ══════════════════════════════════════════════════════════════════════════
# Run ablation
# ══════════════════════════════════════════════════════════════════════════
ABLATION_METHODS = {
    'WCC_only':    METHODS['B1_WCC'],
    'Leiden_flat': btcs_leiden_flat,
    'BTCS_v3':     METHODS['BTCS_v3'],
}
M_COLORS = {'WCC_only': '#2A9D8F', 'Leiden_flat': '#E9C46A', 'BTCS_v3': '#E63946'}
M_LABELS = {'WCC_only': 'A1: WCC only', 'Leiden_flat': 'A2: Leiden flat', 'BTCS_v3': 'A3: BTCS v3 (ours)'}

K_VALS = [0.01, 0.05, 0.10]
results = []
curves  = {}

import psutil

for ds_name, loader_fn, k_vals_ds in DATASETS:
    print(f'\n{"━"*60}\n  Dataset: {ds_name}')
    gc.collect()
    if psutil.virtual_memory().available / 1e9 < 0.8:
        print('  [SKIP] Low RAM'); continue
    try:
        ds = loader_fn()
    except Exception as e:
        print(f'  [ERR] {e}'); continue
    if ds is None:
        print(f'  [SKIP]'); continue

    scores     = ds['scores']
    src        = ds['src']
    dst        = ds['dst']
    timestamps = ds['timestamps']
    y_edges    = ds['y']
    delta_L    = ds['delta_L']
    n_fraud    = int(y_edges.sum())
    n_edges    = len(scores)
    print(f'  {n_edges:,} edges | fraud={n_fraud} ({100*n_fraud/n_edges:.2f}%)')

    for method_name, method_fn in ABLATION_METHODS.items():
        for k_pct in k_vals_ds:
            t0 = time.time()
            cases = method_fn(scores=scores, src=src, dst=dst,
                              timestamps=timestamps, y=y_edges,
                              k=k_pct, delta_L=delta_L)
            t1 = time.time()

            metrics = evaluate_cases_generic(cases, y_edges, n_fraud, k_frac=k_pct)
            xs, ys, auc, yield_b, _ = compute_purity_curve(cases, y_edges, scores)

            # Case size stats
            case_sizes = [len(c.get('seed_edges',[])) + len(c.get('induced_edges',[]))
                         for c in cases]
            max_sz  = max(case_sizes) if case_sizes else 0
            med_sz  = float(np.median(case_sizes)) if case_sizes else 0
            n_giant = sum(1 for s in case_sizes if s >= 100)  # cases hitting budget

            row = {
                'dataset':    ds_name,
                'method':     method_name,
                'k_pct':      k_pct,
                'coverage':   round(metrics['coverage'], 4),
                'purity_ind': round(metrics['purity_induced'], 4),
                'auc_purity': round(auc, 4),
                'yield_b100': round(yield_b, 4),
                'n_cases':    len(cases),
                'max_case':   max_sz,
                'med_case':   med_sz,
                'n_capped':   n_giant,
                'time_s':     round(t1-t0, 2),
            }
            results.append(row)
            curves[(ds_name, method_name, k_pct)] = (xs, ys)

            print(f'  [{method_name}] k={int(k_pct*100)}%: '
                  f'cov={row["coverage"]:.3f} AUC={row["auc_purity"]:.3f} '
                  f'yield={row["yield_b100"]:.3f} cases={len(cases):,} '
                  f'max={max_sz} capped={n_giant} {t1-t0:.1f}s')

    del ds; gc.collect()

# Save CSV
df = pd.DataFrame(results)
df.to_csv(OUT / 'ablation_results.csv', index=False)
print(f'\nSalvo: {OUT}/ablation_results.csv ({len(df)} rows)')

# ══════════════════════════════════════════════════════════════════════════
# FIGURA 1 — Purity curves @ k=5% (5 datasets × 3 métodos)
# ══════════════════════════════════════════════════════════════════════════
datasets_plot = [d for d, _, _ in DATASETS]
fig, axes = plt.subplots(1, len(datasets_plot), figsize=(18, 4))
fig.suptitle('Ablation — Purity Curves @ k=5%\nA1: WCC only  |  A2: Leiden flat  |  A3: BTCS v3',
             fontsize=12, fontweight='bold')

for ax, ds in zip(axes, datasets_plot):
    for m in ['WCC_only', 'Leiden_flat', 'BTCS_v3']:
        key = (ds, m, 0.05)
        if key not in curves: continue
        xs, ys = curves[key]
        mask = xs <= 3000
        lw = 2.5 if m == 'BTCS_v3' else 1.5
        ax.plot(xs[mask], ys[mask], color=M_COLORS[m], label=M_LABELS[m],
                linewidth=lw, zorder=3 if m=='BTCS_v3' else 2)
    ax.axvline(100, color='gray', linestyle='--', linewidth=0.8, alpha=0.6, label='B=100')
    ax.set_title(ds.replace('_', '\n'), fontsize=9)
    ax.set_xlabel('Edges opened', fontsize=8)
    ax.set_ylabel('Cumulative purity', fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGS / 'fig1_ablation_curves.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura 1 salva.')

# ══════════════════════════════════════════════════════════════════════════
# FIGURA 2 — Bar chart: yield@100 e AUC por método, k=5%
# ══════════════════════════════════════════════════════════════════════════
df5 = df[df['k_pct'] == 0.05]
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('Ablation — Yield@100 e AUC Purity @ k=5%', fontsize=12, fontweight='bold')

x = np.arange(len(datasets_plot))
width = 0.25
methods_order = ['WCC_only', 'Leiden_flat', 'BTCS_v3']

for ax, metric, title in zip(axes, ['yield_b100', 'auc_purity'],
                                    ['Yield@100 (H1 — analista)', 'AUC Curva de Pureza']):
    for i, m in enumerate(methods_order):
        vals = [float(df5[(df5['dataset']==ds) & (df5['method']==m)][metric].values[0])
                if not df5[(df5['dataset']==ds) & (df5['method']==m)].empty else 0.0
                for ds in datasets_plot]
        bars = ax.bar(x + i*width, vals, width, label=M_LABELS[m],
                      color=M_COLORS[m], alpha=0.85)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{v:.2f}', ha='center', va='bottom', fontsize=7, rotation=45)
    ax.set_xticks(x + width)
    ax.set_xticklabels([d.replace('_', '\n') for d in datasets_plot], fontsize=8)
    ax.set_ylabel(metric, fontsize=10)
    ax.set_title(title, fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis='y')

plt.tight_layout()
fig.savefig(FIGS / 'fig2_ablation_bar.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura 2 salva.')

# ══════════════════════════════════════════════════════════════════════════
# FIGURA 3 — Giant case problem: n_capped (casos que atingem budget B)
# ══════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
fig.suptitle('Problema do Caso Gigante — Casos que atingem budget B=100 @ k=5%',
             fontsize=11, fontweight='bold')

for ax, metric, title in zip(axes,
                              ['n_capped', 'max_case'],
                              ['Nº de casos capped (≥100 edges)', 'Tamanho do maior caso']):
    for i, m in enumerate(methods_order):
        vals = [float(df5[(df5['dataset']==ds) & (df5['method']==m)][metric].values[0])
                if not df5[(df5['dataset']==ds) & (df5['method']==m)].empty else 0.0
                for ds in datasets_plot]
        ax.bar(x + i*width, vals, width, label=M_LABELS[m],
               color=M_COLORS[m], alpha=0.85)
    ax.set_xticks(x + width)
    ax.set_xticklabels([d.replace('_', '\n') for d in datasets_plot], fontsize=8)
    ax.set_ylabel(metric, fontsize=10)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis='y')

plt.tight_layout()
fig.savefig(FIGS / 'fig3_ablation_giant_case.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura 3 salva.')

# ══════════════════════════════════════════════════════════════════════════
# FIGURA 4 — Yield@100 vs k (1%, 5%, 10%) por dataset
# ══════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, len(datasets_plot), figsize=(18, 4))
fig.suptitle('Ablation — Yield@100 vs k por Dataset', fontsize=12, fontweight='bold')

for ax, ds in zip(axes, datasets_plot):
    for m in methods_order:
        sub = df[(df['dataset']==ds) & (df['method']==m)].sort_values('k_pct')
        if sub.empty: continue
        ax.plot(sub['k_pct']*100, sub['yield_b100'],
                color=M_COLORS[m], label=M_LABELS[m],
                linewidth=2.5 if m=='BTCS_v3' else 1.5,
                marker='o', markersize=6)
    ax.set_title(ds.replace('_', '\n'), fontsize=9)
    ax.set_xlabel('k (%)', fontsize=8)
    ax.set_ylabel('Yield@100', fontsize=8)
    ax.set_xticks([1, 5, 10])
    ax.set_ylim(0, 1.1)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGS / 'fig4_ablation_yield_vs_k.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura 4 salva.')

# ══════════════════════════════════════════════════════════════════════════
# LATEX TABLE
# ══════════════════════════════════════════════════════════════════════════
df5 = df[df['k_pct'] == 0.05].copy()

latex = r"""\begin{table}[t]
\centering
\caption{Ablation study @ k=5\%. A1: WCC only (no sub-segmentation), A2: Leiden applied flat to top-$k$ subgraph (no temporal window), A3: BTCS v3 (WCC + temporal Leiden, full pipeline). \textbf{Bold} = best per dataset.}
\label{tab:ablation}
\resizebox{\linewidth}{!}{
\begin{tabular}{lcccccccccc}
\toprule
 & \multicolumn{2}{c}{\textbf{A1: WCC only}} & \multicolumn{2}{c}{\textbf{A2: Leiden flat}} & \multicolumn{2}{c}{\textbf{A3: BTCS v3}} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
\textbf{Dataset} & Yld@100 & AUC & Yld@100 & AUC & Yld@100 & AUC \\
\midrule
"""
for ds in datasets_plot:
    row_parts = []
    vals = {}
    for m in ['WCC_only', 'Leiden_flat', 'BTCS_v3']:
        r = df5[(df5['dataset']==ds) & (df5['method']==m)]
        if r.empty:
            vals[m] = (float('nan'), float('nan'))
        else:
            vals[m] = (float(r['yield_b100'].iloc[0]), float(r['auc_purity'].iloc[0]))

    best_y = max((v[0] for v in vals.values() if not np.isnan(v[0])), default=0)
    best_a = max((v[1] for v in vals.values() if not np.isnan(v[1])), default=0)

    def fmt(v, best):
        if np.isnan(v): return '---'
        s = f'{v:.3f}'
        return f'\\textbf{{{s}}}' if abs(v - best) < 0.001 else s

    row = f'{ds.replace("_", " ")} & '
    for m in ['WCC_only', 'Leiden_flat', 'BTCS_v3']:
        y, a = vals[m]
        row += f'{fmt(y, best_y)} & {fmt(a, best_a)} & '
    latex += row.rstrip(' & ') + ' \\\\\n'

latex += r"""\bottomrule
\end{tabular}}
\end{table}
"""

with open(OUT / 'ablation_table.tex', 'w') as f:
    f.write(latex)
print('LaTeX salvo.')

# ══════════════════════════════════════════════════════════════════════════
# RESUMO
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '='*65)
print('RESUMO ABLATION @ k=5%')
print('='*65)
print(df5[['dataset','method','coverage','auc_purity','yield_b100','n_cases','n_capped','max_case']].to_string(index=False))
print('\nDone.')
