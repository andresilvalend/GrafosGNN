"""
nb14 — HGS Algorithm Improvements
Script de execução dos experimentos comparativos.
"""
import numpy as np
import pandas as pd
import igraph as ig
import leidenalg
import math
import time
import os
from collections import defaultdict

BASE = '/sessions/sweet-friendly-goldberg/mnt/GrafosGNN'
DATA_DIR = os.path.join(BASE, 'data')
RESULTS_DIR = os.path.join(BASE, 'results', 'nb14_improvements')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ============================================================
# 1. FUNÇÕES DE CAP
# ============================================================

def cap_by_score(induced_edges, scores, budget_B):
    """Original: top-B por score."""
    if len(induced_edges) <= budget_B:
        return list(induced_edges)
    idx_arr = np.array(induced_edges, dtype=np.int64)
    valid = idx_arr[idx_arr < len(scores)]
    if len(valid) == 0:
        return []
    sc = scores[valid]
    top_b = valid[np.argsort(-sc)[:budget_B]]
    return top_b.tolist()


def cap_by_node_coverage(induced_edges, scores, src, dst, budget_B):
    """
    HGS_v2_NC: Greedy max-node-coverage.

    Fase 1: iterar edges em ordem de score decrescente, adicionar se cobre nó novo
    Fase 2: preencher budget restante com top-score

    Intuição: garante que nós com edges de score baixo (como fraud edges)
    ainda apareçam na apresentação.
    """
    if len(induced_edges) <= budget_B:
        return list(induced_edges)

    idx_arr = np.array(induced_edges, dtype=np.int64)
    valid = idx_arr[idx_arr < len(scores)]
    if len(valid) == 0:
        return []

    sc = scores[valid]
    order = np.argsort(-sc)
    sorted_edges = valid[order]

    edge_src_arr = src[sorted_edges] if sorted_edges.max() < len(src) else None
    edge_dst_arr = dst[sorted_edges] if sorted_edges.max() < len(dst) else None

    if edge_src_arr is None or edge_dst_arr is None:
        return cap_by_score(induced_edges, scores, budget_B)

    covered = set()
    selected = []
    selected_set = set()

    # Fase 1: greedy node coverage
    for i in range(len(sorted_edges)):
        if len(selected) >= budget_B:
            break
        eid = int(sorted_edges[i])
        s_node = int(edge_src_arr[i])
        d_node = int(edge_dst_arr[i])
        if s_node not in covered or d_node not in covered:
            selected.append(eid)
            selected_set.add(eid)
            covered.add(s_node)
            covered.add(d_node)

    # Fase 2: preencher budget restante com top-score
    for i in range(len(sorted_edges)):
        if len(selected) >= budget_B:
            break
        eid = int(sorted_edges[i])
        if eid not in selected_set:
            selected.append(eid)
            selected_set.add(eid)

    return selected


# ============================================================
# 2. BUILD Lk (com e sem pesos)
# ============================================================

def build_Lk(src_sel, dst_sel, ts_sel, delta_L, max_hub_edges=500):
    node_map = defaultdict(list)
    for i in range(len(src_sel)):
        node_map[int(src_sel[i])].append((i, int(ts_sel[i])))
        node_map[int(dst_sel[i])].append((i, int(ts_sel[i])))
    edge_set = set()
    for node, elist in node_map.items():
        if len(elist) < 2:
            continue
        elist.sort(key=lambda x: x[1])
        if len(elist) > max_hub_edges:
            elist = elist[:max_hub_edges]
        for i in range(len(elist)):
            ei, ti = elist[i]
            for j in range(i+1, len(elist)):
                ej, tj = elist[j]
                if tj - ti > delta_L:
                    break
                if ei != ej:
                    edge_set.add((min(ei, ej), max(ei, ej)))
    return list(edge_set), None


def build_Lk_weighted(src_sel, dst_sel, ts_sel, scores_sel, delta_L, max_hub_edges=500):
    """Lk com pesos = avg(score_ei, score_ej)."""
    node_map = defaultdict(list)
    for i in range(len(src_sel)):
        node_map[int(src_sel[i])].append((i, int(ts_sel[i])))
        node_map[int(dst_sel[i])].append((i, int(ts_sel[i])))
    edge_weight = {}
    for node, elist in node_map.items():
        if len(elist) < 2:
            continue
        elist.sort(key=lambda x: x[1])
        if len(elist) > max_hub_edges:
            elist = elist[:max_hub_edges]
        for i in range(len(elist)):
            ei, ti = elist[i]
            for j in range(i+1, len(elist)):
                ej, tj = elist[j]
                if tj - ti > delta_L:
                    break
                if ei != ej:
                    key = (min(ei, ej), max(ei, ej))
                    w = float(scores_sel[ei] + scores_sel[ej]) / 2.0
                    if key not in edge_weight or w > edge_weight[key]:
                        edge_weight[key] = w
    edges = list(edge_weight.keys())
    weights = [edge_weight[e] for e in edges]
    return edges, weights


# ============================================================
# 3. HGS GENÉRICO COM VARIANTES
# ============================================================

def hgs_generic(scores, src, dst, timestamps, y,
                k=0.05, delta_L=7, resolution=1.0, budget_B=100, seed=42,
                variant='baseline'):
    """
    variant: 'baseline' | 'nc' | 'sw' | 'both'
    """
    use_nc = variant in ('nc', 'both')
    use_sw = variant in ('sw', 'both')

    scores = np.asarray(scores, dtype=float)
    src = np.asarray(src, dtype=np.int64)
    dst = np.asarray(dst, dtype=np.int64)
    ts = np.asarray(timestamps, dtype=np.int64)
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]

    src_sel = src[sel]
    dst_sel = dst[sel]
    ts_sel = ts[sel]
    sc_sel = scores[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    # Step 1: WCC
    all_nodes = np.unique(np.concatenate([src_sel, dst_sel]))
    nmap = {int(n): i for i, n in enumerate(all_nodes)}
    edges_compact = [(nmap[int(s)], nmap[int(d)]) for s, d in zip(src_sel, dst_sel)]
    g_node = ig.Graph(n=len(all_nodes), edges=edges_compact, directed=False)
    g_node.simplify()
    wcc = g_node.connected_components(mode='weak')
    wcc_mem = np.array(wcc.membership, dtype=np.int64)
    n_wcc = int(wcc_mem.max()) + 1
    edge_wcc = np.array([wcc_mem[nmap[int(s)]] for s in src_sel], dtype=np.int64)

    wcc_edge_lists = [[] for _ in range(n_wcc)]
    wcc_node_sets = [set() for _ in range(n_wcc)]
    for i in range(K):
        w = int(edge_wcc[i])
        wcc_edge_lists[w].append(i)
        wcc_node_sets[w].update([int(src_sel[i]), int(dst_sel[i])])

    wcc_gid = -np.ones(max_node, dtype=np.int64)
    for w, nodes in enumerate(wcc_node_sets):
        for nid in nodes:
            wcc_gid[nid] = w
    g_src_w = np.where(src < max_node, wcc_gid[src], -1)
    g_dst_w = np.where(dst < max_node, wcc_gid[dst], -1)
    mask_w = (g_src_w == g_dst_w) & (g_src_w >= 0)
    idx_w = np.where(mask_w)[0]
    wcc_ind_count = np.zeros(n_wcc, dtype=np.int64)
    if len(idx_w) > 0:
        gw = g_src_w[idx_w]
        uq, cnt = np.unique(gw, return_counts=True)
        wcc_ind_count[uq] = cnt

    # Step 2: Leiden hierárquico para WCCs grandes
    final_mem = np.full(K, -1, dtype=np.int64)
    next_id = 0

    for w in range(n_wcc):
        comp = wcc_edge_lists[w]
        if not comp:
            continue
        need_split = (budget_B is not None and wcc_ind_count[w] > budget_B and len(comp) >= 2)
        if not need_split:
            for i in comp:
                final_mem[i] = next_id
            next_id += 1
        else:
            comp_arr = np.array(comp, dtype=np.int64)
            if use_sw:
                lk_edges, lk_weights = build_Lk_weighted(
                    src_sel[comp_arr], dst_sel[comp_arr],
                    ts_sel[comp_arr], sc_sel[comp_arr], delta_L
                )
            else:
                lk_edges, _ = build_Lk(
                    src_sel[comp_arr], dst_sel[comp_arr],
                    ts_sel[comp_arr], delta_L
                )
                lk_weights = None

            if not lk_edges:
                for i in comp:
                    final_mem[i] = next_id
                    next_id += 1
            else:
                g_local = ig.Graph(n=len(comp), edges=lk_edges, directed=False)
                g_local.simplify()

                if use_sw and lk_weights is not None and len(lk_weights) > 0:
                    w_arr = np.array(lk_weights, dtype=float)
                    w_min, w_max = w_arr.min(), w_arr.max()
                    if w_max > w_min:
                        w_norm = ((w_arr - w_min) / (w_max - w_min)).tolist()
                    else:
                        w_norm = [1.0] * len(lk_weights)
                    # Assign weights to edges (after simplify, lengths might differ)
                    if len(w_norm) == g_local.ecount():
                        g_local.es['weight'] = w_norm
                        part = leidenalg.find_partition(
                            g_local, leidenalg.RBConfigurationVertexPartition,
                            weights='weight',
                            resolution_parameter=resolution, seed=seed
                        )
                    else:
                        part = leidenalg.find_partition(
                            g_local, leidenalg.RBConfigurationVertexPartition,
                            resolution_parameter=resolution, seed=seed
                        )
                else:
                    part = leidenalg.find_partition(
                        g_local, leidenalg.RBConfigurationVertexPartition,
                        resolution_parameter=resolution, seed=seed
                    )

                local_mem = np.array(part.membership, dtype=np.int64)
                n_sub = int(local_mem.max()) + 1
                for j, idx in enumerate(comp):
                    final_mem[idx] = next_id + int(local_mem[j])
                next_id += n_sub

    # Step 3: Montar casos
    n_total = next_id
    node_votes = defaultdict(lambda: defaultdict(int))
    for i in range(K):
        g = int(final_mem[i])
        if g < 0:
            continue
        node_votes[int(src_sel[i])][g] += 1
        node_votes[int(dst_sel[i])][g] += 1

    cases = [{'nodes': set(), 'seed_edges': [], 'induced_edges': [], 'presented_edges': [], 'score': 0.0}
             for _ in range(n_total)]
    for nid, votes in node_votes.items():
        best = max(votes, key=votes.get)
        cases[best]['nodes'].add(nid)
    for i in range(K):
        g = int(final_mem[i])
        if g >= 0:
            cases[g]['seed_edges'].append(int(sel[i]))
    cases = [c for c in cases if c['nodes']]

    # Step 4: Arestas induzidas
    gid_of = -np.ones(max_node, dtype=np.int64)
    for g, case in enumerate(cases):
        for nid in case['nodes']:
            gid_of[nid] = g
    g_src_f = np.where(src < max_node, gid_of[src], -1)
    g_dst_f = np.where(dst < max_node, gid_of[dst], -1)
    mask_f = (g_src_f == g_dst_f) & (g_src_f >= 0)
    idx_f = np.where(mask_f)[0]
    if len(idx_f) > 0:
        gf = g_src_f[idx_f]
        order = np.argsort(gf, kind='stable')
        g_sorted = gf[order]
        i_sorted = idx_f[order]
        uq, cnt = np.unique(g_sorted, return_counts=True)
        for g_id, grp in zip(uq, np.split(i_sorted, np.cumsum(cnt)[:-1])):
            cases[g_id]['induced_edges'] = grp.tolist()

    # Case score = max score das seed_edges
    for case in cases:
        if case['seed_edges']:
            valid_seeds = [i for i in case['seed_edges'] if i < len(scores)]
            case['score'] = float(scores[valid_seeds].max()) if valid_seeds else 0.0

    # Step 5: Budget cap
    for case in cases:
        ie = case['induced_edges']
        if len(ie) > budget_B:
            if use_nc:
                case['presented_edges'] = cap_by_node_coverage(ie, scores, src, dst, budget_B)
            else:
                case['presented_edges'] = cap_by_score(ie, scores, budget_B)
        else:
            case['presented_edges'] = list(ie)

    return cases


# ============================================================
# 4. AVALIAÇÃO
# ============================================================

def evaluate_bccs_p(cases, src, dst, y, budget_B=100):
    y = np.asarray(y, dtype=int)
    total_fraud = int(y.sum())
    if total_fraud == 0 or not cases:
        return {}

    all_presented = set()
    all_induced = set()
    for c in cases:
        pres = c.get('presented_edges', c.get('induced_edges', []))
        all_presented.update(pres[:budget_B] if len(pres) > budget_B else pres)
        all_induced.update(c.get('induced_edges', []))

    pres_arr = np.array(list(all_presented), dtype=np.int64)
    ind_arr = np.array(list(all_induced), dtype=np.int64)

    valid_pres = pres_arr[pres_arr < len(y)]
    valid_ind = ind_arr[ind_arr < len(y)]

    fraud_cov = float(y[valid_pres].sum()) / total_fraud if len(valid_pres) > 0 else 0.0
    part_cov = float(y[valid_ind].sum()) / total_fraud if len(valid_ind) > 0 else 0.0

    cases_sorted = sorted(cases, key=lambda c: -c.get('score', 0))
    if cases_sorted:
        top = cases_sorted[0]
        pres = top.get('presented_edges', top.get('induced_edges', []))
        valid_top = np.array([i for i in pres if i < len(y)], dtype=np.int64)
        yield_b = float(y[valid_top].sum()) / max(len(valid_top), 1) if len(valid_top) > 0 else 0.0
    else:
        yield_b = 0.0

    purities = []
    for c in cases_sorted:
        pres = c.get('presented_edges', c.get('induced_edges', []))
        valid = np.array([i for i in pres if i < len(y)], dtype=np.int64)
        if len(valid) > 0:
            purities.append(float(y[valid].sum()) / len(valid))

    auc = float(np.mean(np.cumsum(purities) / np.arange(1, len(purities)+1))) if purities else 0.0

    ind_sizes = np.array([len(c.get('induced_edges', [])) for c in cases])

    return {
        'n_cases': len(cases),
        'fraud_coverage': fraud_cov,
        'partition_coverage': part_cov,
        'yield_b100': yield_b,
        'auc_purity': auc,
        'edges_max': float(ind_sizes.max()) if len(ind_sizes) > 0 else 0,
        'edges_median': float(np.median(ind_sizes)) if len(ind_sizes) > 0 else 0,
    }


# ============================================================
# 5. LOADERS
# ============================================================

def load_elliptic():
    """
    Loader identico ao nb04_core_cells.py:
    - y = max(y_src, y_dst)  → edge é fraud se QUALQUER endpoint é fraud
    - score = oracle perfeito (1.0 fraud, 0.0 legit, 0.5 unknown)
    - delta_L = 2
    """
    import glob as globmod
    base = os.path.join(DATA_DIR, 'elliptic')
    feat_csvs  = globmod.glob(os.path.join(base, '**', '*features*'), recursive=True)
    edge_csvs  = globmod.glob(os.path.join(base, '**', '*edgelist*'), recursive=True)
    class_csvs = globmod.glob(os.path.join(base, '**', '*classes*'), recursive=True)

    df_feat  = pd.read_csv(feat_csvs[0], header=None)
    df_edges = pd.read_csv(edge_csvs[0])
    df_class = pd.read_csv(class_csvs[0])
    df_class.columns = ['txId', 'class']
    df_edges.columns = ['src', 'dst']

    # Node labels: apenas classes 1 (illicit) e 2 (licit); unknown ignorados
    node_label = {}
    for _, row in df_class.iterrows():
        if row['class'] in ['1', '2', 1, 2]:
            node_label[int(row['txId'])] = 1 if str(row['class']) == '1' else 0

    # Timestamps
    node_ts = dict(zip(df_feat[0].astype(int), df_feat[1].astype(int)))

    # ID map
    all_ids = pd.unique(pd.concat([df_edges['src'], df_edges['dst']]))
    id_map  = {int(v): i for i, v in enumerate(sorted(all_ids))}
    src_arr = df_edges['src'].map(id_map).values.astype(np.int64)
    dst_arr = df_edges['dst'].map(id_map).values.astype(np.int64)

    # y = 1 se qualquer endpoint é fraud (igual nb04)
    y_src = np.array([node_label.get(int(s), 0) for s in df_edges['src']])
    y_dst = np.array([node_label.get(int(d), 0) for d in df_edges['dst']])
    y = np.maximum(y_src, y_dst).astype(int)

    # Timestamps = max dos dois endpoints
    ts_src = np.array([node_ts.get(int(s), 0) for s in df_edges['src']], dtype=np.int64)
    ts_dst = np.array([node_ts.get(int(d), 0) for d in df_edges['dst']], dtype=np.int64)
    ts_arr = np.maximum(ts_src, ts_dst)

    # Score oracle: 1.0 se fraud, 0.0 se licit, 0.5 se unknown (igual nb04)
    def ns(nid):
        if nid in node_label:
            return 1.0 if node_label[nid] == 1 else 0.0
        return 0.5
    sc_src = np.array([ns(int(s)) for s in df_edges['src']], dtype=float)
    sc_dst = np.array([ns(int(d)) for d in df_edges['dst']], dtype=float)
    scores = np.maximum(sc_src, sc_dst)
    scores += np.random.RandomState(42).uniform(0, 0.01, len(scores))

    print(f'Elliptic: {len(src_arr):,} edges | fraud={y.sum():,} ({100*y.mean():.2f}%)')
    return scores, src_arr, dst_arr, ts_arr, y, 2  # delta_L=2


def load_bitcoin_otc():
    """
    Loader identico ao nb04_core_cells.py:
    - score = -ratings normalizado (negativo = suspeito)
    - y = (ratings < 0)
    - delta_L = 30
    """
    path = os.path.join(DATA_DIR, 'bitcoin_otc', 'soc-sign-bitcoinotc.csv')
    df = pd.read_csv(path, header=None, names=['src', 'dst', 'rating', 'timestamp'])
    df = df.dropna()

    all_nodes = pd.unique(pd.concat([df['src'], df['dst']]))
    nmap = {v: i for i, v in enumerate(sorted(all_nodes))}

    src_arr = df['src'].map(nmap).values.astype(np.int64)
    dst_arr = df['dst'].map(nmap).values.astype(np.int64)
    ratings = df['rating'].values.astype(float)

    y = (ratings < 0).astype(int)
    scores = -ratings
    scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-8)

    ts_days = (df['timestamp'].values.astype(np.int64) - df['timestamp'].min()) // 86400

    print(f'Bitcoin-OTC: {len(src_arr):,} edges | fraud={y.sum():,} ({100*y.mean():.2f}%)')
    return scores, src_arr, dst_arr, ts_days, y, 30  # delta_L=30


# ============================================================
# 6. MAIN — EXPERIMENTOS
# ============================================================

if __name__ == '__main__':
    print('=== nb14: HGS Algorithm Improvements ===\n')

    variants = ['baseline', 'nc', 'sw', 'both']
    k_values = [0.01, 0.05]

    # ---- Elliptic ----
    print('=== Carregando Elliptic ===')
    ell_scores, ell_src, ell_dst, ell_ts, ell_y, ell_dL = load_elliptic()

    results = []
    for k in k_values:
        for v in variants:
            print(f'\n--- Elliptic k={k*100:.0f}% | variant={v} ---')
            t0 = time.perf_counter()
            cases = hgs_generic(
                ell_scores, ell_src, ell_dst, ell_ts, ell_y,
                k=k, delta_L=ell_dL, resolution=1.0, budget_B=100, seed=42,
                variant=v
            )
            t1 = time.perf_counter()
            m = evaluate_bccs_p(cases, ell_src, ell_dst, ell_y, budget_B=100)
            m['dataset'] = 'Elliptic'
            m['method'] = f'HGS_v2_{v.upper()}' if v != 'baseline' else 'HGS_v1_baseline'
            m['k_pct'] = k * 100
            m['time_s'] = round(t1 - t0, 4)
            results.append(m)
            print(f'  fraud_cov={m["fraud_coverage"]:.4f} | part_cov={m["partition_coverage"]:.4f} | yield@100={m["yield_b100"]:.4f} | auc={m["auc_purity"]:.4f} | t={t1-t0:.2f}s')

    # ---- Bitcoin-OTC ----
    print('\n\n=== Carregando Bitcoin-OTC ===')
    btc_scores, btc_src, btc_dst, btc_ts, btc_y, btc_dL = load_bitcoin_otc()

    for k in k_values:
        for v in variants:
            print(f'\n--- Bitcoin-OTC k={k*100:.0f}% | variant={v} ---')
            t0 = time.perf_counter()
            cases = hgs_generic(
                btc_scores, btc_src, btc_dst, btc_ts, btc_y,
                k=k, delta_L=btc_dL, resolution=1.0, budget_B=100, seed=42,
                variant=v
            )
            t1 = time.perf_counter()
            m = evaluate_bccs_p(cases, btc_src, btc_dst, btc_y, budget_B=100)
            m['dataset'] = 'Bitcoin-OTC'
            m['method'] = f'HGS_v2_{v.upper()}' if v != 'baseline' else 'HGS_v1_baseline'
            m['k_pct'] = k * 100
            m['time_s'] = round(t1 - t0, 4)
            results.append(m)
            print(f'  fraud_cov={m["fraud_coverage"]:.4f} | part_cov={m["partition_coverage"]:.4f} | yield@100={m["yield_b100"]:.4f} | auc={m["auc_purity"]:.4f} | t={t1-t0:.2f}s')

    # ---- Salvar resultados ----
    df = pd.DataFrame(results)
    cols = ['dataset','method','k_pct','fraud_coverage','partition_coverage',
            'yield_b100','auc_purity','n_cases','edges_max','edges_median','time_s']
    df = df[cols]

    out_path = os.path.join(RESULTS_DIR, 'nb14_improvements_results.csv')
    df.to_csv(out_path, index=False)
    print(f'\n\nResultados salvos em: {out_path}')

    # ---- Resumo de ganhos ----
    print('\n=== RESUMO: GANHO NC vs BASELINE ===')
    print(f'{"Dataset":<15} {"k%":<6} {"Baseline":>12} {"NC":>12} {"SW":>12} {"BOTH":>12} {"Δ_NC":>10} {"Δ_BOTH":>10}')
    print('-' * 90)
    for ds in ['Elliptic', 'Bitcoin-OTC']:
        for k in k_values:
            sub = df[(df['dataset']==ds) & (df['k_pct']==k*100)]
            row = {}
            for _, r in sub.iterrows():
                row[r['method']] = r['fraud_coverage']
            base = row.get('HGS_v1_baseline', np.nan)
            nc   = row.get('HGS_v2_NC', np.nan)
            sw   = row.get('HGS_v2_SW', np.nan)
            both = row.get('HGS_v2_BOTH', np.nan)
            delta_nc   = nc - base if not (np.isnan(nc) or np.isnan(base)) else np.nan
            delta_both = both - base if not (np.isnan(both) or np.isnan(base)) else np.nan
            print(f'{ds:<15} {k*100:<6.0f} {base:>12.4f} {nc:>12.4f} {sw:>12.4f} {both:>12.4f} {delta_nc:>+10.4f} {delta_both:>+10.4f}')

    print('\n=== TABELA COMPLETA ===')
    print(df.to_string(index=False))


# ============================================================
# 7. EXPERIMENTO COM SCORE IMPERFECTO (simulação real-world)
# ============================================================
def run_noisy_score_experiment():
    """
    Demonstra o problema do budget cap com scores imperfectos.
    
    No mundo real (ex: Elliptic++) o score do modelo NÃO é oracle.
    Simulamos isso adicionando ruído ao score do Elliptic.
    
    Para cada nível de ruído, compara:
    - HGS_v1_baseline (top-B por score)
    - HGS_v2_NC (node coverage cap)
    
    Hipótese: NC mantém fraud_coverage melhor à medida que o score degrada.
    """
    print('\n\n=== EXPERIMENTO: Score Imperfecto (simulação real-world) ===')
    print('Dataset: Elliptic k=5% | variando nível de ruído no score')
    
    ell_scores, ell_src, ell_dst, ell_ts, ell_y, ell_dL = load_elliptic()
    
    noise_levels = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
    results_noise = []
    
    for noise in noise_levels:
        rng = np.random.RandomState(99)
        # Mistura o score oracle com ruído uniforme
        noisy_scores = (1 - noise) * ell_scores + noise * rng.uniform(0, 1, len(ell_scores))
        
        for v in ['baseline', 'nc']:
            cases = hgs_generic(
                noisy_scores, ell_src, ell_dst, ell_ts, ell_y,
                k=0.05, delta_L=ell_dL, resolution=1.0, budget_B=100, seed=42,
                variant=v
            )
            m = evaluate_bccs_p(cases, ell_src, ell_dst, ell_y, budget_B=100)
            m['noise'] = noise
            m['method'] = 'HGS_v1_baseline' if v == 'baseline' else 'HGS_v2_NC'
            results_noise.append(m)
    
    df_noise = pd.DataFrame(results_noise)
    
    print(f'\n{"Ruído":<8} {"Baseline fraud_cov":>20} {"NC fraud_cov":>15} {"Δ NC":>10} {"Baseline part_cov":>18} {"NC part_cov":>12}')
    print('-' * 90)
    for noise in noise_levels:
        sub = df_noise[df_noise['noise'] == noise]
        base = sub[sub['method']=='HGS_v1_baseline'].iloc[0]
        nc   = sub[sub['method']=='HGS_v2_NC'].iloc[0]
        delta = nc['fraud_coverage'] - base['fraud_coverage']
        print(f'{noise:<8.1f} {base["fraud_coverage"]:>20.4f} {nc["fraud_coverage"]:>15.4f} {delta:>+10.4f} {base["partition_coverage"]:>18.4f} {nc["partition_coverage"]:>12.4f}')
    
    # Salvar
    out_path = os.path.join(RESULTS_DIR, 'nb14_noisy_score_experiment.csv')
    df_noise.to_csv(out_path, index=False)
    print(f'\nSalvo em: {out_path}')
    return df_noise


if __name__ == '__main__':
    pass  # Já rodou acima
