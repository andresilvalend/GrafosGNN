#!/usr/bin/env python3
"""
Multiple seeds — BTCS v3 com seeds 42/43/44/45/46
Objetivo: calcular mean ± std para validação estatística
Datasets: elliptic, bitcoin_otc, yelp_fraud, amazon_fraud (k=1% only para static)
"""
import sys, os, gc, time, math, warnings, contextlib
sys.path.insert(0, '/sessions/friendly-modest-rubin/.local/lib/python3.10/site-packages')
warnings.filterwarnings('ignore')
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import igraph as ig
import leidenalg
from collections import defaultdict

_GDRIVE = Path('/sessions/friendly-modest-rubin/mnt/Meu Drive')
_REPO   = Path('/sessions/friendly-modest-rubin/mnt/GrafosGNN')
DATA    = _REPO / 'data'
GNN_SCORES   = _REPO / 'results/nb05_gnn_scores'
AML100K_BASE = _GDRIVE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = _GDRIVE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'
OUT  = _REPO / 'results/nb08_seeds'
OUT.mkdir(parents=True, exist_ok=True)

exec(open('/tmp/core_cells.py').read(), globals())

def compute_purity_curve(cases, y_edges, scores, budget_B=100):
    y = np.asarray(y_edges, dtype=int)
    S = np.asarray(scores, dtype=np.float32)
    if not cases:
        return 0.0, 0.0
    case_data = []
    for c in cases:
        all_idx = np.array(list(c.get('seed_edges',[])) + list(c.get('induced_edges',[])), dtype=np.int64)
        all_idx = all_idx[all_idx < len(y)]
        if len(all_idx) == 0: continue
        seed_idx = np.array(c.get('seed_edges',[]), dtype=np.int64)
        seed_idx = seed_idx[seed_idx < len(S)]
        case_score = float(S[seed_idx].mean()) if len(seed_idx) > 0 else 0.0
        case_data.append({'score': case_score, 'n': len(all_idx), 'n_fraud': int(y[all_idx].sum())})
    if not case_data: return 0.0, 0.0
    case_data.sort(key=lambda x: -x['score'])
    cum_n, cum_fraud = 0, 0
    xs, ys = [0], [0.0]
    for c in case_data:
        cum_n += c['n']; cum_fraud += c['n_fraud']
        xs.append(cum_n); ys.append(cum_fraud/cum_n if cum_n > 0 else 0.0)
    xs = np.array(xs); ys = np.array(ys)
    total = xs[-1] if xs[-1] > 0 else 1.0
    auc = float(np.trapz(ys, xs)) / total
    budget, fraud_b = budget_B, 0.0
    for c in case_data:
        if budget <= 0: break
        take = min(c['n'], budget)
        fraud_b += c['n_fraud'] * (take/c['n']) if c['n'] > 0 else 0
        budget -= take
    yield_b = fraud_b / budget_B if budget_B > 0 else 0.0
    return auc, yield_b

# ══════════════════════════════════════════════════════════════════════════
SEEDS  = [42, 43, 44, 45, 46]
K_VALS = [0.01, 0.05, 0.10]

DATASETS = [
    ('elliptic',     load_elliptic,                              [0.01, 0.05, 0.10]),
    ('bitcoin_otc',  lambda: load_bitcoin_otc_alpha('bitcoin_otc'), [0.01, 0.05, 0.10]),
    ('yelp_fraud',   lambda: load_mat_fraud('yelp_fraud', 'YelpChi.mat'), [0.01]),
    ('amazon_fraud', lambda: load_mat_fraud('amazon_fraud', 'Amazon.mat'), [0.01]),
]

results = []

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

    for k_pct in k_vals_ds:
        seed_aucs, seed_yields, seed_covs = [], [], []

        for seed in SEEDS:
            t0 = time.time()
            cases = btcs_generic(scores=scores, src=src, dst=dst,
                                 timestamps=timestamps, y=y_edges,
                                 k=k_pct, delta_L=delta_L, seed=seed)
            t1 = time.time()

            metrics = evaluate_cases_generic(cases, y_edges, n_fraud, k_frac=k_pct)
            auc, yield_b = compute_purity_curve(cases, y_edges, scores)

            seed_aucs.append(auc)
            seed_yields.append(yield_b)
            seed_covs.append(metrics['coverage'])

        # Aggregate
        row = {
            'dataset':       ds_name,
            'k_pct':         k_pct,
            'n_seeds':        len(SEEDS),
            'seeds':          str(SEEDS),
            'auc_mean':      round(float(np.mean(seed_aucs)), 4),
            'auc_std':       round(float(np.std(seed_aucs)), 4),
            'yield_mean':    round(float(np.mean(seed_yields)), 4),
            'yield_std':     round(float(np.std(seed_yields)), 4),
            'coverage_mean': round(float(np.mean(seed_covs)), 4),
            'coverage_std':  round(float(np.std(seed_covs)), 4),
        }
        results.append(row)
        print(f'  k={int(k_pct*100)}%: '
              f'yield={row["yield_mean"]:.3f}±{row["yield_std"]:.4f}  '
              f'AUC={row["auc_mean"]:.3f}±{row["auc_std"]:.4f}  '
              f'cov={row["coverage_mean"]:.3f}±{row["coverage_std"]:.4f}')

    del ds; gc.collect()

# Save
df = pd.DataFrame(results)
df.to_csv(OUT / 'seeds_results.csv', index=False)
print(f'\nSalvo: {OUT}/seeds_results.csv ({len(df)} rows)')

# Print summary table
print('\n' + '='*70)
print('RESUMO — BTCS v3 com 5 seeds (42–46)')
print('='*70)
print(df[['dataset','k_pct','yield_mean','yield_std','auc_mean','auc_std',
          'coverage_mean','coverage_std']].to_string(index=False))

# LaTeX table
latex = r"""\begin{table}[t]
\centering
\caption{BTCS v3 stability across 5 random seeds (42–46). Mean $\pm$ std over seeds.}
\label{tab:seeds}
\begin{tabular}{llccc}
\toprule
\textbf{Dataset} & \textbf{k} & \textbf{Yield@100} & \textbf{AUC Purity} & \textbf{Coverage} \\
\midrule
"""
for _, r in df.iterrows():
    latex += (f"{r['dataset'].replace('_',' ')} & "
              f"{int(r['k_pct']*100)}\\% & "
              f"${r['yield_mean']:.3f} \\pm {r['yield_std']:.4f}$ & "
              f"${r['auc_mean']:.3f} \\pm {r['auc_std']:.4f}$ & "
              f"${r['coverage_mean']:.3f} \\pm {r['coverage_std']:.4f}$ \\\\\n")

latex += r"""\bottomrule
\end{tabular}
\end{table}
"""
with open(OUT / 'seeds_table.tex', 'w') as f:
    f.write(latex)
print('LaTeX salvo.')
print('Done.')
