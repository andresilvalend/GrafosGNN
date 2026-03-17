#!/usr/bin/env python3
"""
NB06 — Libra Bank finalization
Runs BTCS + B0 + B1 + B2 (fast), captures purity curves.
B3 Greedy: only k=1% result available (716s), k=5% and k=10% marked as N/A.
"""
import sys, os, gc, time, math, contextlib, warnings
sys.path.insert(0, '/sessions/friendly-modest-rubin/.local/lib/python3.10/site-packages')
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
import matplotlib.patches as mpatches
from sklearn.metrics import roc_auc_score, average_precision_score

_GDRIVE = Path('/sessions/friendly-modest-rubin/mnt/Meu Drive')
_REPO   = Path('/sessions/friendly-modest-rubin/mnt/GrafosGNN')
DATA    = _GDRIVE / 'GrafosGNN/data/libra'
OUT     = _REPO / 'results/nb06_libra'
FIGS    = OUT / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

exec(open('/tmp/core_cells.py').read(), globals())

# ══════════════════════════════════════════════════════════════════════════
# 1. LOAD LIBRA BANK
# ══════════════════════════════════════════════════════════════════════════
print('='*60)
print('Carregando Libra Bank...')

df = pd.read_csv(DATA / 'Libra_bank_3months_graph.csv')
print(f'  {len(df):,} edges | colunas: {list(df.columns)}')

all_nodes = pd.unique(pd.concat([df['id_source'], df['id_destination']]))
nmap = {int(v): i for i, v in enumerate(sorted(all_nodes))}
df['src'] = df['id_source'].map(nmap).astype(np.int64)
df['dst'] = df['id_destination'].map(nmap).astype(np.int64)

src       = df['src'].values
dst       = df['dst'].values
n_nodes   = int(max(src.max(), dst.max())) + 1
n_edges   = len(df)

# Labels
df['is_fraud'] = ((df['nr_alerts'] > 0) | (df['nr_reports'] > 0)).astype(int)
y_edges = df['is_fraud'].values.astype(int)
n_fraud = y_edges.sum()
print(f'  {n_nodes:,} nodes | {n_edges:,} edges | fraud={n_fraud} ({n_fraud/n_edges*100:.3f}%)')

# Score heuristic
nr_alerts  = df['nr_alerts'].values.astype(float)
nr_reports = df['nr_reports'].values.astype(float)
nr_trans   = df['nr_transactions'].values.astype(float)
raw_score  = (nr_alerts * 1.0 + nr_reports * 5.0) / (np.sqrt(nr_trans) + 1.0)
s_min, s_max = raw_score.min(), raw_score.max()
scores = (raw_score - s_min) / (s_max - s_min + 1e-12)

print(f'\n  Score heurístico:')
print(f'  AUC-ROC  = {roc_auc_score(y_edges, scores):.4f}')
print(f'  Avg Prec = {average_precision_score(y_edges, scores):.4f}')
for k_pct in [0.01, 0.05, 0.10]:
    K = max(1, int(math.ceil(k_pct * n_edges)))
    top_idx = np.argsort(-scores)[:K]
    rec = y_edges[top_idx].sum() / n_fraud if n_fraud > 0 else 0
    prec = y_edges[top_idx].mean()
    print(f'  Recall@{int(k_pct*100)}% = {rec:.3f}  Precision@{int(k_pct*100)}% = {prec:.4f}')

# No timestamps (aggregated graph) → infinite window
timestamps = np.arange(n_edges, dtype=np.int64)
delta_L = n_edges

print(f'\n  RAM disponível: {psutil.virtual_memory().available/1e9:.1f}GB')

# ══════════════════════════════════════════════════════════════════════════
# 2. COMPUTE PURITY CURVE (same function as in run_curves2.py)
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
# 3. RUN METHODS (skip B3 Greedy at k=5%, k=10%)
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('Rodando BTCS v3 + B0 + B1 + B2 (B3 apenas k=1% pré-calculado)...')

K_VALS  = [0.01, 0.05, 0.10]
METHODS_FAST = ['BTCS_v3', 'B0_Random', 'B1_WCC', 'B2_Louvain']

# Hardcoded B3_Greedy k=1% result (computed earlier, 716s)
B3_PRECOMPUTED = {
    0.01: {'coverage': 0.946, 'purity_induced': 0.0019, 'auc_purity': 0.010,
           'yield_b100': 0.079, 'n_cases': 3062, 'time_s': 716.8}
}

results   = []
curves    = {}   # (method, k_pct) -> (xs, ys)

for method_name in METHODS_FAST:
    fn = METHODS[method_name]
    for k_pct in K_VALS:
        t0 = time.time()
        cases = fn(scores=scores, src=src, dst=dst,
                   timestamps=timestamps, y=y_edges,
                   k=k_pct, delta_L=delta_L)
        t1 = time.time()

        metrics = evaluate_cases_generic(cases, y_edges, n_fraud, k_frac=k_pct)
        xs, ys, auc, yield_b, n_cb = compute_purity_curve(cases, y_edges, scores)

        row = {
            'dataset': 'Libra_Bank',
            'method': method_name,
            'k_pct': k_pct,
            'coverage': round(metrics['coverage'], 4),
            'purity_induced': round(metrics['purity_induced'], 4),
            'auc_purity': round(auc, 4),
            'yield_b100': round(yield_b, 4),
            'n_cases': len(cases),
            'time_s': round(t1-t0, 1)
        }
        results.append(row)
        curves[(method_name, k_pct)] = (xs, ys)

        print(f'  [{method_name}] k={int(k_pct*100)}%: '
              f'cov={row["coverage"]:.3f} pur={row["purity_induced"]:.4f} '
              f'AUC={row["auc_purity"]:.3f} yield@100={row["yield_b100"]:.3f} '
              f'cases={len(cases):,} {t1-t0:.1f}s')

# Add B3 Greedy k=1% pre-computed
for k_pct, vals in B3_PRECOMPUTED.items():
    row = {'dataset': 'Libra_Bank', 'method': 'B3_Greedy', 'k_pct': k_pct}
    row.update(vals)
    results.append(row)
    print(f'  [B3_Greedy] k={int(k_pct*100)}%: cov={vals["coverage"]:.3f} '
          f'pur={vals["purity_induced"]:.4f} AUC={vals["auc_purity"]:.3f} '
          f'yield@100={vals["yield_b100"]:.3f} (pre-computed, 716s)')
print('  [B3_Greedy] k=5%, k=10%: SKIPPED (O(K²N) complexity, ~3h estimate)')

# Save CSV
df_res = pd.DataFrame(results)
df_res.to_csv(OUT / 'libra_results.csv', index=False)
print(f'\nSalvo: results/nb06_libra/libra_results.csv ({len(df_res)} rows)')

# ══════════════════════════════════════════════════════════════════════════
# 4. FIGURAS
# ══════════════════════════════════════════════════════════════════════════
METHOD_ORDER  = ['BTCS_v3', 'B0_Random', 'B1_WCC', 'B2_Louvain', 'B3_Greedy']
METHOD_COLORS = {'BTCS_v3':'#E63946','B0_Random':'#457B9D','B1_WCC':'#2A9D8F',
                 'B2_Louvain':'#E9C46A','B3_Greedy':'#8338EC'}
METHOD_LABELS = {'BTCS_v3':'BTCS v3 (ours)','B0_Random':'B0 Random',
                 'B1_WCC':'B1 WCC','B2_Louvain':'B2 Louvain','B3_Greedy':'B3 Greedy'}

# ── Fig A: Purity curves (3 panels) ──────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
fig.suptitle('Libra Bank — Purity Curves by Method and k', fontsize=13, fontweight='bold')

for ax, k_pct in zip(axes, K_VALS):
    for m in METHODS_FAST:
        if (m, k_pct) not in curves:
            continue
        xs, ys = curves[(m, k_pct)]
        # Truncate to first 5000 edges for clarity
        mask = xs <= 5000
        ax.plot(xs[mask], ys[mask], color=METHOD_COLORS[m],
                label=METHOD_LABELS[m], linewidth=2 if m=='BTCS_v3' else 1.2,
                zorder=3 if m=='BTCS_v3' else 2)
    # B3 single point at k=1%
    if k_pct == 0.01:
        ax.scatter([100], [B3_PRECOMPUTED[0.01]['yield_b100']],
                   color=METHOD_COLORS['B3_Greedy'], marker='*', s=150, zorder=5,
                   label=f'B3 Greedy (k=1% only)')
    ax.axvline(100, color='gray', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.set_xlabel('Edges opened by analyst', fontsize=10)
    ax.set_ylabel('Cumulative purity (fraud fraction)', fontsize=10)
    ax.set_title(f'k = {int(k_pct*100)}%', fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGS / 'figA_libra_purity_curves.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura A salva: figA_libra_purity_curves.png')

# ── Fig B: Coverage × Purity scatter @ k=5% ──────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
df5 = df_res[df_res['k_pct']==0.05]
for m in METHOD_ORDER:
    row = df5[df5['method']==m]
    if row.empty: continue
    ax.scatter(row['coverage'], row['purity_induced'],
               color=METHOD_COLORS[m], s=180, zorder=5, label=METHOD_LABELS[m])
    ax.annotate(METHOD_LABELS[m],
                (float(row['coverage']), float(row['purity_induced'])),
                textcoords='offset points', xytext=(6, 4), fontsize=8)

ax.set_xlabel('Coverage', fontsize=11)
ax.set_ylabel('Purity (induced edges)', fontsize=11)
ax.set_title('Libra Bank — Coverage vs Purity @ k=5%', fontsize=12)
ax.set_xlim(0, 1.05); ax.set_ylim(0, 0.12)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(FIGS / 'figB_libra_cov_pur_scatter.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura B salva: figB_libra_cov_pur_scatter.png')

# ── Fig C: yield@100 and AUC vs k (line plot) ────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

for ax, metric, title in zip(axes,
                              ['yield_b100', 'auc_purity'],
                              ['Yield@100 (H1 Metric)', 'AUC Purity Curve']):
    for m in METHOD_ORDER:
        sub = df_res[df_res['method']==m].sort_values('k_pct')
        if sub.empty: continue
        ax.plot(sub['k_pct']*100, sub[metric],
                color=METHOD_COLORS[m],
                label=METHOD_LABELS[m],
                linewidth=2.5 if m=='BTCS_v3' else 1.5,
                marker='o', markersize=7,
                linestyle='--' if m=='B3_Greedy' else '-',
                zorder=3 if m=='BTCS_v3' else 2)
    ax.set_xlabel('k (%)', fontsize=11)
    ax.set_ylabel(metric, fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xticks([1, 5, 10])
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

plt.suptitle('Libra Bank — Key Metrics vs k', fontsize=13, fontweight='bold')
plt.tight_layout()
fig.savefig(FIGS / 'figC_libra_metrics_vs_k.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura C salva: figC_libra_metrics_vs_k.png')

# ── Fig D: Coverage + n_cases overview ────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

for ax, metric, title in zip(axes,
                              ['coverage', 'n_cases'],
                              ['Coverage vs k', 'Number of Cases vs k']):
    for m in METHOD_ORDER:
        sub = df_res[df_res['method']==m].sort_values('k_pct')
        if sub.empty: continue
        ax.plot(sub['k_pct']*100, sub[metric],
                color=METHOD_COLORS[m], label=METHOD_LABELS[m],
                linewidth=2.5 if m=='BTCS_v3' else 1.5,
                marker='o', markersize=7,
                linestyle='--' if m=='B3_Greedy' else '-')
    ax.set_xlabel('k (%)', fontsize=11)
    ax.set_ylabel(metric, fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xticks([1, 5, 10])
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

plt.suptitle('Libra Bank — Coverage and Case Count', fontsize=13, fontweight='bold')
plt.tight_layout()
fig.savefig(FIGS / 'figD_libra_coverage_ncases.png', dpi=150, bbox_inches='tight')
plt.close()
print('Figura D salva: figD_libra_coverage_ncases.png')

# ══════════════════════════════════════════════════════════════════════════
# 5. LATEX TABLE @ k=5%
# ══════════════════════════════════════════════════════════════════════════
df5 = df_res[df_res['k_pct']==0.05].copy()
df5_full = df_res.pivot_table(index='method', columns='k_pct',
                               values=['coverage','yield_b100','auc_purity'],
                               aggfunc='first')

latex = r"""\begin{table}[t]
\centering
\caption{Libra Bank results (597K edges, 444 fraud, 0.07\% prevalence). B3 Greedy shown at k=1\% only; k=5\%/10\% omitted due to $\mathcal{O}(K^2 N)$ complexity (\textasciitilde 716s per run).}
\label{tab:libra_results}
\begin{tabular}{lcccccc}
\toprule
\textbf{Method} & \multicolumn{2}{c}{\textbf{k=1\%}} & \multicolumn{2}{c}{\textbf{k=5\%}} & \multicolumn{2}{c}{\textbf{k=10\%}} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
 & Cov & Yield@100 & Cov & Yield@100 & Cov & Yield@100 \\
\midrule
"""
for m in METHOD_ORDER:
    sub = df_res[df_res['method']==m].sort_values('k_pct')
    if sub.empty: continue
    row_1 = sub[sub['k_pct']==0.01]
    row_5 = sub[sub['k_pct']==0.05]
    row_10= sub[sub['k_pct']==0.10]

    def fmt_cov(r, bold=False):
        if r.empty: return '---'
        v = float(r['coverage'])
        return f'\\textbf{{{v:.3f}}}' if bold else f'{v:.3f}'
    def fmt_y(r, bold=False):
        if r.empty: return '---'
        v = float(r['yield_b100'])
        return f'\\textbf{{{v:.3f}}}' if bold else f'{v:.3f}'

    is_btcs = (m == 'BTCS_v3')
    label = METHOD_LABELS[m]
    line = (f'{label} & '
            f'{fmt_cov(row_1, is_btcs)} & {fmt_y(row_1, is_btcs)} & '
            f'{fmt_cov(row_5, is_btcs)} & {fmt_y(row_5, is_btcs)} & '
            f'{fmt_cov(row_10, is_btcs)} & {fmt_y(row_10, is_btcs)} \\\\\n')
    latex += line

latex += r"""\bottomrule
\end{tabular}
\end{table}
"""

with open(OUT / 'libra_results_k5.tex', 'w') as f:
    f.write(latex)
print('LaTeX salvo: results/nb06_libra/libra_results_k5.tex')

# ══════════════════════════════════════════════════════════════════════════
# 6. PRINT SUMMARY
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('RESUMO LIBRA BANK — k=5%')
print('='*60)
df5 = df_res[df_res['k_pct']==0.05]
if not df5.empty:
    print(df5[['method','coverage','purity_induced','auc_purity','yield_b100','n_cases']].to_string(index=False))
print('\nk=1%:')
df1 = df_res[df_res['k_pct']==0.01]
print(df1[['method','coverage','purity_induced','auc_purity','yield_b100','n_cases']].to_string(index=False))
print('\nDone.')
