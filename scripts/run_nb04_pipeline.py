#!/usr/bin/env python3
"""Final 3 datasets: amazon_fraud, yelp_fraud, t_finance (with RAM guards)."""
import sys, os, gc, time, math, contextlib, warnings
sys.path.insert(0, '/sessions/friendly-modest-rubin/.local/lib/python3.10/site-packages')
os.environ.setdefault('DGLBACKEND','pytorch')
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
OUT.mkdir(parents=True, exist_ok=True)
GNN_SCORES   = _REPO / 'results/nb05_gnn_scores'
AML100K_BASE = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML100k'
AML1M_BASE   = BASE / 'DatasetDissertacao/IBM_TRANSACTION_AML/AMLSIMFULL/AML1M'

exec(open('/tmp/core_cells.py').read(), globals())

# Load existing results
df_part = pd.read_csv(OUT / 'multi_dataset_results_partial.csv')
all_rows = df_part.to_dict('records')
ALREADY_DONE = set(df_part['dataset'].unique())
print(f'Starting with {len(all_rows)} rows | done: {sorted(ALREADY_DONE)}')

# ── LOADERS ──────────────────────────────────────────────────────────────
def _load_amazon(max_edges=500_000):
    """Amazon fraud sampled to max_edges to avoid OOM."""
    ds = load_mat_fraud('amazon_fraud', 'Amazon.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        rng = np.random.RandomState(42)
        idx = rng.choice(n, max_edges, replace=False); idx.sort()
        ds['src'] = ds['src'][idx]
        ds['dst'] = ds['dst'][idx]
        ds['scores'] = ds['scores'][idx]
        ds['y'] = ds['y'][idx]
        ds['timestamps'] = ds['timestamps'][idx]
        ds['n_edges'] = max_edges
        ds['delta_L'] = max(100, max_edges // 100)
        pos = int(ds['y'].sum())
        print(f'[Amazon] sampled to {max_edges:,} edges | fraud={pos:,} ({100*pos/max_edges:.2f}%)')
    else:
        ds['delta_L'] = max(100, n // 100)
    return ds

def _load_yelp(max_edges=500_000):
    """Yelp fraud sampled to max_edges to avoid OOM."""
    ds = load_mat_fraud('yelp_fraud', 'YelpChi.mat')
    if ds is None: return None
    n = ds['n_edges']
    if n > max_edges:
        rng = np.random.RandomState(42)
        idx = rng.choice(n, max_edges, replace=False); idx.sort()
        ds['src'] = ds['src'][idx]
        ds['dst'] = ds['dst'][idx]
        ds['scores'] = ds['scores'][idx]
        ds['y'] = ds['y'][idx]
        ds['timestamps'] = ds['timestamps'][idx]
        ds['n_edges'] = max_edges
        ds['delta_L'] = max(100, max_edges // 100)
        pos = int(ds['y'].sum())
        print(f'[Yelp] sampled to {max_edges:,} edges | fraud={pos:,} ({100*pos/max_edges:.2f}%)')
    else:
        ds['delta_L'] = max(100, n // 100)
    return ds

def _load_t_finance_2m():
    """T-Finance with 2M edge sample."""
    t_dir = DATA / 't_finance'
    file_path = next((t_dir/f for f in ['tfinance','t-finance.pt','T-Finance'] if (t_dir/f).exists()), None)
    if not file_path: print('[T-Finance] not found'); return None
    try:
        import dgl, torch
        print(f'[T-Finance] loading {file_path} ...')
        gs, _ = dgl.load_graphs(str(file_path))
        g = gs[0]
        labels = g.ndata['label'].numpy().astype(int)
        y_node = labels[:, 1]
        src_t, dst_t = g.edges()
        src_all = src_t.numpy().astype(np.int64)
        dst_all = dst_t.numpy().astype(np.int64)
        del g, gs, labels, src_t, dst_t; gc.collect()

        n_nodes = int(y_node.shape[0])
        n_all = len(src_all)
        MAX = 2_000_000
        rng = np.random.RandomState(42)
        idx = rng.choice(n_all, MAX, replace=False); idx.sort()
        src = src_all[idx]; dst = dst_all[idx]
        del src_all, dst_all; gc.collect()

        n_edges = len(src)
        feat_norm = np.where(y_node == 1, 0.9, 0.1).astype(np.float32)
        scores = np.maximum(feat_norm[src], feat_norm[dst]).astype(np.float32)
        scores += np.random.RandomState(42).uniform(0, 0.01, n_edges)
        y_edge = np.maximum(y_node[src], y_node[dst]).astype(int)
        pos = int(y_edge.sum())
        print(f'[T-Finance] {n_edges:,} edges (2M sample) | fraud={pos:,} ({100*pos/n_edges:.2f}%)')
        return {'name': 't_finance', 'scores': scores, 'src': src, 'dst': dst,
                'timestamps': np.arange(n_edges, dtype=np.int64), 'y': y_edge,
                'n_nodes': n_nodes, 'n_edges': n_edges, 'delta_L': 100_000}
    except Exception as e:
        print(f'[T-Finance] error: {e}'); import traceback; traceback.print_exc(); return None

# ── DATASET LIST ──────────────────────────────────────────────────────────
DATASET_LOADERS = [
    ('amazon_fraud', _load_amazon),
    ('yelp_fraud',   _load_yelp),
    ('t_finance',    _load_t_finance_2m),
]

# ── PIPELINE ──────────────────────────────────────────────────────────────
KS = [0.01, 0.05, 0.10]
GAMMA = 1.0; BUDGET_B = 100
# Hard limit: skip B3_Greedy if >5M edges, skip any method if <0.5GB RAM
B3_MAX_EDGES = 5_000_000
RAM_MIN_GB   = 0.5

for ds_name, loader_fn in DATASET_LOADERS:
    if ds_name in ALREADY_DONE:
        print(f'[SKIP] {ds_name} already done'); continue

    gc.collect()
    avail = psutil.virtual_memory().available / 1e9
    if avail < 1.0:
        print(f'[SKIP] {ds_name} – low RAM ({avail:.1f}GB)'); continue

    print(f'\n{"━"*60}\n  Loading: {ds_name}')
    try:
        ds = loader_fn()
    except MemoryError as e:
        print(f'  [OOM] {e}'); gc.collect(); continue
    except Exception as e:
        print(f'  [ERR] {e}'); continue
    if ds is None:
        print(f'  [SKIP] None'); continue

    name = ds['name']; delta_L = ds['delta_L']
    n_edges = ds['n_edges']; n_nodes = ds['n_nodes']
    print(f'  → {n_nodes:,} nodes | {n_edges:,} edges | pos={ds["y"].sum():,} ({100*ds["y"].mean():.2f}%) | dL={delta_L}')
    print(f'  RAM: {psutil.virtual_memory().available/1e9:.1f}GB')

    for method_name, method_fn in METHODS.items():
        if method_name == 'B3_Greedy' and n_edges > B3_MAX_EDGES:
            print(f'  [{method_name}] SKIP (>{B3_MAX_EDGES//1e6:.0f}M edges)')
            for k in KS:
                all_rows.append({'dataset': name, 'method': method_name, 'n_nodes': n_nodes,
                    'n_edges': n_edges, 'k%': f'{int(k*100)}%', 'k_frac': k, 'delta_L': delta_L,
                    'resolution': GAMMA, 'budget_B': BUDGET_B, 'n_cases': np.nan,
                    'coverage': np.nan, 'purity_induced': np.nan, 'ocr_b100': np.nan,
                    'edges_per_case_median': np.nan, 'edges_per_case_max': np.nan,
                    'e_ind_total': np.nan, 'time_s': np.nan, 'ram_mb': np.nan})
            continue

        for k in KS:
            kp = f'{int(k*100)}%'
            # RAM guard before each call
            avail_now = psutil.virtual_memory().available / 1e9
            if avail_now < RAM_MIN_GB:
                print(f'  [{method_name}] k={kp}: SKIP (RAM {avail_now:.1f}GB < {RAM_MIN_GB}GB)')
                all_rows.append({'dataset': name, 'method': method_name, 'n_nodes': n_nodes,
                    'n_edges': n_edges, 'k%': kp, 'k_frac': k, 'delta_L': delta_L,
                    'resolution': GAMMA, 'budget_B': BUDGET_B, 'n_cases': np.nan,
                    'coverage': np.nan, 'purity_induced': np.nan, 'ocr_b100': np.nan,
                    'edges_per_case_median': np.nan, 'edges_per_case_max': np.nan,
                    'e_ind_total': np.nan, 'time_s': np.nan, 'ram_mb': np.nan})
                continue
            try:
                with measure_resources() as res:
                    if method_name == 'BTCS_v3':
                        cases = method_fn(ds['scores'], ds['src'], ds['dst'],
                                          ds['timestamps'], ds['y'],
                                          k=k, delta_L=delta_L, resolution=GAMMA, budget_B=BUDGET_B)
                    else:
                        cases = method_fn(ds['scores'], ds['src'], ds['dst'],
                                          ds['timestamps'], ds['y'], k=k, budget_B=BUDGET_B)
                    m = evaluate_cases_generic(cases, ds['y'], ds['n_edges'], k)
                row = {'dataset': name, 'method': method_name, 'n_nodes': n_nodes,
                       'n_edges': n_edges, 'k%': kp, 'k_frac': k, 'delta_L': delta_L,
                       'resolution': GAMMA, 'budget_B': BUDGET_B, **m, **res}
                all_rows.append(row)
                print(f'  [{method_name}] k={kp}: cov={m["coverage"]:.3f} pur={m["purity_induced"]:.4f} '
                      f'OCR={m["ocr_b100"]:.3f} cases={m["n_cases"]:,} {res["time_s"]:.1f}s')
            except MemoryError as e:
                print(f'  [{method_name}] k={kp}: OOM'); gc.collect()
                all_rows.append({'dataset': name, 'method': method_name, 'n_nodes': n_nodes,
                    'n_edges': n_edges, 'k%': kp, 'k_frac': k, 'delta_L': delta_L,
                    'resolution': GAMMA, 'budget_B': BUDGET_B, 'n_cases': np.nan,
                    'coverage': np.nan, 'purity_induced': np.nan, 'ocr_b100': np.nan,
                    'edges_per_case_median': np.nan, 'edges_per_case_max': np.nan,
                    'e_ind_total': np.nan, 'time_s': np.nan, 'ram_mb': np.nan})
            except Exception as e:
                print(f'  [{method_name}] k={kp}: ERROR {e}')
                import traceback; traceback.print_exc()
                all_rows.append({'dataset': name, 'method': method_name, 'n_nodes': n_nodes,
                    'n_edges': n_edges, 'k%': kp, 'k_frac': k, 'delta_L': delta_L,
                    'resolution': GAMMA, 'budget_B': BUDGET_B, 'n_cases': np.nan,
                    'coverage': np.nan, 'purity_induced': np.nan, 'ocr_b100': np.nan,
                    'edges_per_case_median': np.nan, 'edges_per_case_max': np.nan,
                    'e_ind_total': np.nan, 'time_s': np.nan, 'ram_mb': np.nan})

    del ds; gc.collect()
    pd.DataFrame(all_rows).to_csv(OUT / 'multi_dataset_results_partial.csv', index=False)
    print(f'  [checkpoint] {len(all_rows)} rows saved')

# ── SAVE FINAL ────────────────────────────────────────────────────────────
df_final = pd.DataFrame(all_rows)
df_final.to_csv(OUT / 'multi_dataset_results.csv', index=False)
print(f'\n✅ {len(df_final)} rows | {df_final["dataset"].nunique()} datasets → multi_dataset_results.csv')

print('\n=== BTCS_v3 @ k=5% ===')
btcs5 = df_final[(df_final.method == 'BTCS_v3') & (df_final['k%'] == '5%')][
    ['dataset', 'coverage', 'purity_induced', 'ocr_b100', 'n_cases', 'time_s', 'n_edges']]
print(btcs5.sort_values('coverage', ascending=False).to_string(index=False))
