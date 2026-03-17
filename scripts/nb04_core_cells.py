
# ======= CELL 2 =======
# CELULA 2 - Funcoes utilitarias

@contextlib.contextmanager
def measure_resources():
    proc = psutil.Process(os.getpid())
    m0 = proc.memory_info().rss / 1024**2
    t0 = time.perf_counter()
    r  = {}
    yield r
    r['time_s'] = time.perf_counter() - t0
    r['ram_mb']  = proc.memory_info().rss / 1024**2 - m0


def evaluate_cases_generic(cases, y_edges, n_test, k_frac):
    """Avalia casos para qualquer dataset.
    
    Args:
        cases: lista de dicts com 'nodes', 'seed_edges', 'induced_edges'
        y_edges: array de labels (0/1) para TODAS as arestas usadas como 'full'
        n_test: numero total de arestas de teste
        k_frac: fracao k usada
    """
    y = np.asarray(y_edges, dtype=int)
    pos_total = int(y.sum())
    K = max(1, int(math.ceil(k_frac * n_test)))
    
    if not cases:
        return {m: np.nan for m in [
            'n_cases','coverage','purity_induced','ocr_b100',
            'edges_per_case_median','edges_per_case_max','e_ind_total']}
    
    ind_sizes = np.array([len(c['induced_edges']) for c in cases])
    non_empty = [c['induced_edges'] for c in cases if c['induced_edges']]
    if non_empty:
        all_ind = np.unique(np.concatenate(
            [np.asarray(x, dtype=np.int64) for x in non_empty]))
    else:
        all_ind = np.array([], dtype=np.int64)
    
    # Clamp indices
    valid = all_ind[all_ind < len(y)]
    pos_ind = int(y[valid].sum()) if len(valid) > 0 else 0
    coverage = float(pos_ind / max(pos_total, 1))
    purity = float(pos_ind / max(int(ind_sizes.sum()), 1))
    
    return {
        'n_cases': len(cases),
        'coverage': coverage,
        'purity_induced': purity,
        'ocr_b100': float((ind_sizes > 100).mean()),
        'edges_per_case_median': float(np.median(ind_sizes)),
        'edges_per_case_max': float(ind_sizes.max()),
        'e_ind_total': int(ind_sizes.sum()),
    }

print('Funcoes utilitarias definidas.')

# ======= CELL 3 =======
# CELULA 3 - BTCS v3 generico
# Aceita qualquer dataset via interface padronizada:
#   scores: array de probabilidades/scores por aresta
#   src, dst: arrays de endpoints
#   timestamps: array de timestamps (int64)
#   y: labels ground truth (0/1)

def build_Lk(src_sel, dst_sel, ts_sel, delta_L, max_hub_edges=500):
    K = len(src_sel)
    node_map = defaultdict(list)
    for i in range(K):
        node_map[int(src_sel[i])].append((i, int(ts_sel[i])))
        node_map[int(dst_sel[i])].append((i, int(ts_sel[i])))
    lk_edges = set()
    for node, elist in node_map.items():
        if len(elist) < 2:
            continue
        if len(elist) > max_hub_edges:
            elist.sort(key=lambda x: x[1])
            elist = elist[:max_hub_edges]
        else:
            elist.sort(key=lambda x: x[1])
        for i in range(len(elist)):
            ei, ti = elist[i]
            for j in range(i+1, len(elist)):
                ej, tj = elist[j]
                if tj - ti > delta_L:
                    break
                if ei != ej:
                    lk_edges.add((min(ei, ej), max(ei, ej)))
    return list(lk_edges)


def btcs_generic(scores, src, dst, timestamps, y,
                 k=0.01, delta_L=7, resolution=1.0, budget_B=100, seed=42):
    """BTCS v3 generico: funciona com qualquer dataset.
    
    Args:
        scores: array (N,) de scores por aresta (maior = mais suspeito)
        src: array (N,) de source node IDs
        dst: array (N,) de dest node IDs
        timestamps: array (N,) de timestamps (int)
        y: array (N,) de labels ground truth
        k: fracao de top edges
        delta_L: janela temporal para Lk
        resolution: gamma do Leiden
        budget_B: max edges induzidas por caso
        seed: random seed
    
    Returns:
        cases: lista de dicts
    """
    scores = np.asarray(scores, dtype=float)
    src = np.asarray(src, dtype=np.int64)
    dst = np.asarray(dst, dtype=np.int64)
    ts = np.asarray(timestamps, dtype=np.int64)
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    
    src_sel, dst_sel, ts_sel = src[sel], dst[sel], ts[sel]
    max_node = int(max(src.max(), dst.max())) + 1
    print(f'  K={K:,} top edges (of {N:,})')
    
    # Step 1: WCC no subgrafo de nos top-k
    all_nodes = np.unique(np.concatenate([src_sel, dst_sel]))
    nmap = {int(n): i for i, n in enumerate(all_nodes)}
    edges_compact = [(nmap[int(s)], nmap[int(d)])
                     for s, d in zip(src_sel, dst_sel)]
    g_node = ig.Graph(n=len(all_nodes), edges=edges_compact, directed=False)
    g_node.simplify()
    wcc = g_node.connected_components(mode='weak')
    wcc_mem = np.array(wcc.membership, dtype=np.int64)
    n_wcc = int(wcc_mem.max()) + 1
    edge_wcc = np.array([wcc_mem[nmap[int(s)]] for s in src_sel], dtype=np.int64)
    
    # Agrupar por WCC
    wcc_edge_lists = [[] for _ in range(n_wcc)]
    wcc_node_sets = [set() for _ in range(n_wcc)]
    for i in range(K):
        w = int(edge_wcc[i])
        wcc_edge_lists[w].append(i)
        wcc_node_sets[w].update([int(src_sel[i]), int(dst_sel[i])])
    
    # Contar induzidas por WCC (vetorizado)
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
    
    n_small = int((wcc_ind_count[wcc_ind_count > 0] <= (budget_B or 1e18)).sum())
    n_large = int((wcc_ind_count > (budget_B or 1e18)).sum())
    print(f'  WCC: {n_wcc:,} comps | {n_small} small, {n_large} large')
    
    # Step 2: Hierarquico - split grandes com Leiden
    final_mem = np.full(K, -1, dtype=np.int64)
    next_id = 0
    for w in range(n_wcc):
        comp = wcc_edge_lists[w]
        if not comp:
            continue
        need_split = (budget_B is not None and wcc_ind_count[w] > budget_B
                      and len(comp) >= 2)
        if not need_split:
            for i in comp:
                final_mem[i] = next_id
            next_id += 1
        else:
            comp_arr = np.array(comp, dtype=np.int64)
            lk_local = build_Lk(src_sel[comp_arr], dst_sel[comp_arr],
                                ts_sel[comp_arr], delta_L)
            if not lk_local:
                for i in comp:
                    final_mem[i] = next_id
                    next_id += 1
            else:
                g_local = ig.Graph(n=len(comp), edges=lk_local, directed=False)
                g_local.simplify()
                part = leidenalg.find_partition(
                    g_local, leidenalg.RBConfigurationVertexPartition,
                    resolution_parameter=resolution, seed=seed)
                local_mem = np.array(part.membership, dtype=np.int64)
                n_sub = int(local_mem.max()) + 1
                for j, idx in enumerate(comp):
                    final_mem[idx] = next_id + int(local_mem[j])
                next_id += n_sub
    
    # Step 3: Montar casos (voto majoritario)
    n_total = next_id
    node_votes = defaultdict(lambda: defaultdict(int))
    for i in range(K):
        g = int(final_mem[i])
        if g < 0: continue
        node_votes[int(src_sel[i])][g] += 1
        node_votes[int(dst_sel[i])][g] += 1
    
    cases = [{'nodes': set(), 'seed_edges': [], 'induced_edges': []}
             for _ in range(n_total)]
    for nid, votes in node_votes.items():
        best = max(votes, key=votes.get)
        cases[best]['nodes'].add(nid)
    for i in range(K):
        g = int(final_mem[i])
        if g >= 0:
            cases[g]['seed_edges'].append(int(sel[i]))
    cases = [c for c in cases if c['nodes']]
    
    # Step 4: Arestas induzidas (vetorizado)
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
    
    # Step 5: Budget cap
    n_capped = 0
    if budget_B is not None:
        for case in cases:
            if len(case['induced_edges']) > budget_B:
                n_capped += 1
                idx_arr = np.array(case['induced_edges'], dtype=np.int64)
                valid_idx = idx_arr[idx_arr < len(scores)]
                sc_ind = scores[valid_idx]
                top_b = valid_idx[np.argsort(-sc_ind)[:budget_B]]
                case['induced_edges'] = top_b.tolist()
    
    ind_sizes = np.array([len(c['induced_edges']) for c in cases])
    print(f'  Final: {len(cases)} cases | capped={n_capped} | '
          f'median={np.median(ind_sizes):.0f} max={ind_sizes.max()}')
    return cases

print('BTCS v3 generico definido.')

# ======= CELL 4 =======
# CELULA 3B - Baselines (mesma interface que btcs_generic)
# Todos recebem (scores, src, dst, timestamps, y, k, budget_B) e retornam cases[]

def baseline_random(scores, src, dst, timestamps, y,
                    k=0.01, budget_B=100, seed=42, **kw):
    """B0: Atribuição aleatória. Top-k edges → grupos aleatórios de ≤B."""
    rng = np.random.RandomState(seed)
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    src_sel, dst_sel = src[sel], dst[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    # Atribuir cada edge a um grupo aleatório
    perm = rng.permutation(K)
    group_size = max(1, budget_B // 2)  # ~B/2 edges por grupo
    n_groups = max(1, K // group_size)
    mem = np.zeros(K, dtype=np.int64)
    for i, idx in enumerate(perm):
        mem[idx] = i % n_groups

    # Montar casos
    cases = [{'nodes': set(), 'seed_edges': [], 'induced_edges': []}
             for _ in range(n_groups)]
    for i in range(K):
        g = int(mem[i])
        cases[g]['nodes'].update([int(src_sel[i]), int(dst_sel[i])])
        cases[g]['seed_edges'].append(int(sel[i]))
    cases = [c for c in cases if c['nodes']]

    # Arestas induzidas + budget cap
    gid_of = -np.ones(max_node, dtype=np.int64)
    for g, case in enumerate(cases):
        for nid in case['nodes']: gid_of[nid] = g
    gs = np.where(src < max_node, gid_of[src], -1)
    gd = np.where(dst < max_node, gid_of[dst], -1)
    mask = (gs == gd) & (gs >= 0)
    idx_f = np.where(mask)[0]
    if len(idx_f) > 0:
        gf = gs[idx_f]
        order = np.argsort(gf, kind='stable')
        uq, cnt = np.unique(gf[order], return_counts=True)
        for g_id, grp in zip(uq, np.split(idx_f[order], np.cumsum(cnt)[:-1])):
            cases[g_id]['induced_edges'] = grp.tolist()
    for case in cases:
        if len(case['induced_edges']) > budget_B:
            idx_arr = np.array(case['induced_edges'], dtype=np.int64)
            valid = idx_arr[idx_arr < len(scores)]
            case['induced_edges'] = valid[np.argsort(-scores[valid])[:budget_B]].tolist()
    print(f'  [B0-Random] {len(cases)} cases')
    return cases


def baseline_wcc_only(scores, src, dst, timestamps, y,
                      k=0.01, budget_B=100, **kw):
    """B1: WCC-only. Top-k edges → WCC, sem Leiden. Budget cap por score."""
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    src_sel, dst_sel = src[sel], dst[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    all_nodes = np.unique(np.concatenate([src_sel, dst_sel]))
    nmap = {int(n): i for i, n in enumerate(all_nodes)}
    edges_compact = [(nmap[int(s)], nmap[int(d)])
                     for s, d in zip(src_sel, dst_sel)]
    g = ig.Graph(n=len(all_nodes), edges=edges_compact, directed=False)
    g.simplify()
    wcc = g.connected_components(mode='weak')
    wcc_mem = np.array(wcc.membership, dtype=np.int64)

    # Cada WCC = 1 caso
    n_wcc = int(wcc_mem.max()) + 1
    cases = [{'nodes': set(), 'seed_edges': [], 'induced_edges': []}
             for _ in range(n_wcc)]
    for i in range(K):
        w = int(wcc_mem[nmap[int(src_sel[i])]])
        cases[w]['nodes'].update([int(src_sel[i]), int(dst_sel[i])])
        cases[w]['seed_edges'].append(int(sel[i]))
    cases = [c for c in cases if c['nodes']]

    # Arestas induzidas + budget cap
    gid_of = -np.ones(max_node, dtype=np.int64)
    for g_id, case in enumerate(cases):
        for nid in case['nodes']: gid_of[nid] = g_id
    gs = np.where(src < max_node, gid_of[src], -1)
    gd = np.where(dst < max_node, gid_of[dst], -1)
    mask = (gs == gd) & (gs >= 0)
    idx_f = np.where(mask)[0]
    if len(idx_f) > 0:
        gf = gs[idx_f]
        order = np.argsort(gf, kind='stable')
        uq, cnt = np.unique(gf[order], return_counts=True)
        for g_id, grp in zip(uq, np.split(idx_f[order], np.cumsum(cnt)[:-1])):
            cases[g_id]['induced_edges'] = grp.tolist()
    for case in cases:
        if len(case['induced_edges']) > budget_B:
            idx_arr = np.array(case['induced_edges'], dtype=np.int64)
            valid = idx_arr[idx_arr < len(scores)]
            case['induced_edges'] = valid[np.argsort(-scores[valid])[:budget_B]].tolist()
    print(f'  [B1-WCC] {len(cases)} cases')
    return cases


def baseline_louvain(scores, src, dst, timestamps, y,
                     k=0.01, budget_B=100, **kw):
    """B2: Louvain community detection no subgrafo top-k.
    Usa igraph community_multilevel (Louvain) no grafo de nós.
    """
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    src_sel, dst_sel = src[sel], dst[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    all_nodes = np.unique(np.concatenate([src_sel, dst_sel]))
    nmap = {int(n): i for i, n in enumerate(all_nodes)}
    edges_compact = [(nmap[int(s)], nmap[int(d)])
                     for s, d in zip(src_sel, dst_sel)]
    g = ig.Graph(n=len(all_nodes), edges=edges_compact, directed=False)
    g.simplify()

    # Louvain
    part = g.community_multilevel()
    mem = np.array(part.membership, dtype=np.int64)
    n_comm = int(mem.max()) + 1

    cases = [{'nodes': set(), 'seed_edges': [], 'induced_edges': []}
             for _ in range(n_comm)]
    for i in range(K):
        c = int(mem[nmap[int(src_sel[i])]])
        cases[c]['nodes'].update([int(src_sel[i]), int(dst_sel[i])])
        cases[c]['seed_edges'].append(int(sel[i]))
    cases = [c for c in cases if c['nodes']]

    # Arestas induzidas + budget cap
    gid_of = -np.ones(max_node, dtype=np.int64)
    for g_id, case in enumerate(cases):
        for nid in case['nodes']: gid_of[nid] = g_id
    gs = np.where(src < max_node, gid_of[src], -1)
    gd = np.where(dst < max_node, gid_of[dst], -1)
    mask = (gs == gd) & (gs >= 0)
    idx_f = np.where(mask)[0]
    if len(idx_f) > 0:
        gf = gs[idx_f]
        order = np.argsort(gf, kind='stable')
        uq, cnt = np.unique(gf[order], return_counts=True)
        for g_id, grp in zip(uq, np.split(idx_f[order], np.cumsum(cnt)[:-1])):
            cases[g_id]['induced_edges'] = grp.tolist()
    for case in cases:
        if len(case['induced_edges']) > budget_B:
            idx_arr = np.array(case['induced_edges'], dtype=np.int64)
            valid = idx_arr[idx_arr < len(scores)]
            case['induced_edges'] = valid[np.argsort(-scores[valid])[:budget_B]].tolist()
    print(f'  [B2-Louvain] {len(cases)} cases')
    return cases


def baseline_greedy_expand(scores, src, dst, timestamps, y,
                           k=0.01, budget_B=100, **kw):
    """B3: Greedy seed expansion.
    Para cada seed edge (top-k por score decrescente), expande BFS
    adicionando vizinhos até atingir budget_B induzidas.
    """
    N = len(scores)
    K = max(1, int(math.ceil(k * N)))
    sel = np.argsort(-scores)[:K]
    src_sel, dst_sel = src[sel], dst[sel]
    max_node = int(max(src.max(), dst.max())) + 1

    # Adjacency list (todo o grafo)
    adj = defaultdict(set)
    edge_of = defaultdict(list)  # node -> list of edge indices
    for idx in range(N):
        s, d = int(src[idx]), int(dst[idx])
        adj[s].add(d)
        adj[d].add(s)
        edge_of[s].append(idx)
        edge_of[d].append(idx)

    assigned = set()  # nodes já atribuidos
    cases = []

    for i in range(K):
        s, d = int(src_sel[i]), int(dst_sel[i])
        if s in assigned and d in assigned:
            continue

        # Iniciar caso com esta seed edge
        case_nodes = {s, d}
        assigned.update(case_nodes)

        # Expandir greedily até budget
        frontier = set()
        for n in case_nodes:
            frontier.update(adj[n] - assigned)

        while frontier:
            # Contar arestas induzidas se adicionarmos cada candidato
            best_node, best_gain = None, -1
            for cand in list(frontier)[:200]:  # limitar busca
                gain = len(adj[cand] & case_nodes)
                if gain > best_gain:
                    best_gain = gain
                    best_node = cand

            if best_node is None:
                break

            # Checar se budget seria violado
            case_nodes.add(best_node)
            # Contar induzidas
            n_ind = 0
            for n in case_nodes:
                for idx in edge_of[n]:
                    s2, d2 = int(src[idx]), int(dst[idx])
                    if s2 in case_nodes and d2 in case_nodes:
                        n_ind += 1
                if n_ind // 2 > budget_B:
                    break
            n_ind = n_ind // 2  # cada aresta contada 2x

            if n_ind > budget_B:
                case_nodes.remove(best_node)
                break

            assigned.add(best_node)
            frontier = set()
            for n in case_nodes:
                frontier.update(adj[n] - assigned)

        # Encontrar arestas induzidas
        induced = []
        for n in case_nodes:
            for idx in edge_of[n]:
                if int(src[idx]) in case_nodes and int(dst[idx]) in case_nodes:
                    induced.append(idx)
        induced = list(set(induced))
        if len(induced) > budget_B:
            idx_arr = np.array(induced, dtype=np.int64)
            induced = idx_arr[np.argsort(-scores[idx_arr])[:budget_B]].tolist()

        cases.append({
            'nodes': case_nodes,
            'seed_edges': [int(sel[i])],
            'induced_edges': induced
        })

        if len(cases) >= K:  # safety
            break

    print(f'  [B3-Greedy] {len(cases)} cases')
    return cases


METHODS = {
    'BTCS_v3': btcs_generic,
    'B0_Random': baseline_random,
    'B1_WCC': baseline_wcc_only,
    'B2_Louvain': baseline_louvain,
    'B3_Greedy': baseline_greedy_expand,
}

print(f'Algoritmos definidos: {", ".join(METHODS.keys())}')

# ======= CELL 5 =======
# CELULA 4 - Loaders por dataset

def load_bitcoin_otc_alpha(name='bitcoin_otc'):
    path = DATA / name
    csvs = list(path.glob('*.csv'))
    assert csvs, f'Nenhum CSV em {path}'
    df = pd.read_csv(csvs[0], header=None,
                     names=['src', 'dst', 'rating', 'timestamp'])
    all_ids = pd.unique(pd.concat([df['src'], df['dst']]))
    id_map = {v: i for i, v in enumerate(sorted(all_ids))}
    src = df['src'].map(id_map).values.astype(np.int64)
    dst = df['dst'].map(id_map).values.astype(np.int64)
    ratings = df['rating'].values.astype(float)
    scores = -ratings
    scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-8)
    y = (ratings < 0).astype(int)
    ts_days = (df['timestamp'].values.astype(np.int64) - df['timestamp'].min()) // 86400
    print(f'[{name}] {len(df):,} edges | nodes={len(id_map):,} | '
          f'neg={y.sum():,} ({100*y.mean():.1f}%)')
    return {'name': name, 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': ts_days, 'y': y,
            'n_nodes': len(id_map), 'n_edges': len(df), 'delta_L': 30}


def load_paysim():
    csvs = list((DATA / 'paysim').glob('*.csv'))
    assert csvs, 'PaySim CSV nao encontrado'
    df = pd.read_csv(csvs[0])
    all_ids = pd.unique(pd.concat([df['nameOrig'], df['nameDest']]))
    id_map = {v: i for i, v in enumerate(all_ids)}
    src = df['nameOrig'].map(id_map).values.astype(np.int64)
    dst = df['nameDest'].map(id_map).values.astype(np.int64)
    y = df['isFraud'].values.astype(int)
    timestamps = df['step'].values.astype(np.int64)
    type_risk = df['type'].map({'TRANSFER':0.8,'CASH_OUT':0.9,
        'PAYMENT':0.3,'CASH_IN':0.1,'DEBIT':0.2}).fillna(0.5).values
    amount_norm = (df['amount'].values - df['amount'].min()) / \
                  (df['amount'].max() - df['amount'].min() + 1e-8)
    scores = type_risk * amount_norm
    print(f'[PaySim] {len(df):,} txns | nodes={len(id_map):,} | '
          f'fraud={y.sum():,} ({100*y.mean():.2f}%) [H]')
    return {'name': 'paysim', 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': len(id_map), 'n_edges': len(df), 'delta_L': 24}


def load_elliptic():
    path = DATA / 'elliptic'
    feat_csv = list(path.rglob('*features*'))
    edge_csv = list(path.rglob('*edgelist*'))
    class_csv = list(path.rglob('*classes*'))
    assert feat_csv and edge_csv and class_csv, 'Elliptic nao encontrado'
    df_feat = pd.read_csv(feat_csv[0], header=None)
    df_edges = pd.read_csv(edge_csv[0])
    df_class = pd.read_csv(class_csv[0])
    df_class.columns = ['txId', 'class']
    node_label = {}
    for _, row in df_class.iterrows():
        if row['class'] in ['1','2',1,2]:
            node_label[int(row['txId'])] = 1 if str(row['class'])=='1' else 0
    node_ts = dict(zip(df_feat[0].astype(int), df_feat[1].astype(int)))
    df_edges.columns = ['src','dst']
    all_ids = pd.unique(pd.concat([df_edges['src'], df_edges['dst']]))
    id_map = {int(v): i for i, v in enumerate(sorted(all_ids))}
    src = df_edges['src'].map(id_map).values.astype(np.int64)
    dst = df_edges['dst'].map(id_map).values.astype(np.int64)
    y_src = np.array([node_label.get(int(s),0) for s in df_edges['src']])
    y_dst = np.array([node_label.get(int(d),0) for d in df_edges['dst']])
    y = np.maximum(y_src, y_dst)
    ts_src = np.array([node_ts.get(int(s),0) for s in df_edges['src']])
    ts_dst = np.array([node_ts.get(int(d),0) for d in df_edges['dst']])
    timestamps = np.maximum(ts_src, ts_dst).astype(np.int64)
    def ns(nid):
        if nid in node_label: return 1.0 if node_label[nid]==1 else 0.0
        return 0.5
    scores = np.maximum(
        np.array([ns(int(s)) for s in df_edges['src']]),
        np.array([ns(int(d)) for d in df_edges['dst']]))
    scores += np.random.RandomState(42).uniform(0, 0.01, len(scores))
    print(f'[Elliptic] {len(df_edges):,} edges | nodes={len(id_map):,} | '
          f'illicit_edges={y.sum():,} ({100*y.mean():.1f}%) [H]')
    return {'name': 'elliptic', 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': len(id_map), 'n_edges': len(df_edges), 'delta_L': 2}


def load_ibm_aml_transactions():
    csv_path = DATA / 'ibm_aml' / 'transactions.csv'
    assert csv_path.exists(), f'{csv_path} nao encontrado'
    df = pd.read_csv(csv_path)
    all_ids = pd.unique(pd.concat([
        df['SENDER_ACCOUNT_ID'].astype(str),
        df['RECEIVER_ACCOUNT_ID'].astype(str)]))
    id_map = {v: i for i, v in enumerate(sorted(all_ids))}
    src = df['SENDER_ACCOUNT_ID'].astype(str).map(id_map).values.astype(np.int64)
    dst = df['RECEIVER_ACCOUNT_ID'].astype(str).map(id_map).values.astype(np.int64)
    y = df['IS_FRAUD'].values.astype(int)
    ts = pd.to_numeric(df['TIMESTAMP'], errors='coerce').fillna(0).values.astype(np.int64)
    if ts.max() > 1e9: ts = (ts - ts.min()) // 86400
    amount = df['TX_AMOUNT'].values.astype(float)
    scores = (amount - amount.min()) / (amount.max() - amount.min() + 1e-8)
    scores += np.random.RandomState(42).uniform(0, 0.01, len(scores))
    print(f'[IBM AML txns] {len(df):,} txns | nodes={len(id_map):,} | '
          f'fraud={y.sum():,} ({100*y.mean():.2f}%) [H]')
    return {'name': 'ibm_aml_txns', 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': ts, 'y': y,
            'n_nodes': len(id_map), 'n_edges': len(df), 'delta_L': 7}


def load_ibm_hili(filename, display_name):
    """Loader genérico para IBM AML HI/LI datasets.
    Todos têm mesmo formato: Timestamp,From Bank,Account,To Bank,Account,...,Is Laundering
    Pandas auto-renomeia col duplicada Account -> Account.1
    """
    csv_path = DATA / 'ibm_aml' / filename
    assert csv_path.exists(), f'{csv_path} nao encontrado'
    df = pd.read_csv(csv_path, header=0)
    # Account = sender, Account.1 = receiver
    src_id = df['From Bank'].astype(str) + '_' + df['Account'].astype(str)
    dst_id = df['To Bank'].astype(str) + '_' + df['Account.1'].astype(str)
    all_ids = pd.unique(pd.concat([src_id, dst_id]))
    id_map = {v: i for i, v in enumerate(all_ids)}
    src = src_id.map(id_map).values.astype(np.int64)
    dst = dst_id.map(id_map).values.astype(np.int64)
    y = df['Is Laundering'].values.astype(int)
    # Timestamp ordinal
    ts_str = df['Timestamp'].astype(str)
    ts_sorted = ts_str.sort_values().unique()
    ts_map = {v: i for i, v in enumerate(ts_sorted)}
    timestamps = ts_str.map(ts_map).values.astype(np.int64)
    # Score: amount normalizado
    amount = df['Amount Paid'].fillna(df['Amount Received']).values.astype(float)
    scores = (amount - amount.min()) / (amount.max() - amount.min() + 1e-8)
    scores += np.random.RandomState(42).uniform(0, 0.001, len(scores))
    print(f'[{display_name}] {len(df):,} txns | nodes={len(id_map):,} | '
          f'laund={y.sum():,} ({100*y.mean():.2f}%) [H]')
    return {'name': display_name, 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': len(id_map), 'n_edges': len(df), 'delta_L': 30}


def load_mat_fraud(name, mat_filename, adj_key='homo'):
    import scipy.io as sio
    import scipy.sparse as sp
    mat_path = DATA / name / mat_filename
    assert mat_path.exists(), f'{mat_path} nao encontrado'
    mat = sio.loadmat(str(mat_path))
    adj = mat[adj_key]
    if sp.issparse(adj): adj = adj.tocoo()
    else: adj = sp.coo_matrix(adj)
    labels = np.asarray(mat['label']).flatten()
    n_nodes = len(labels)
    row, col = adj.row, adj.col
    mask_upper = row < col
    src = row[mask_upper].astype(np.int64)
    dst = col[mask_upper].astype(np.int64)
    n_edges = len(src)
    y = np.maximum(labels[src], labels[dst]).astype(int)
    scores = np.maximum(labels[src].astype(float), labels[dst].astype(float))
    scores += np.random.RandomState(42).uniform(0, 0.01, len(scores))
    timestamps = np.arange(n_edges, dtype=np.int64)
    print(f'[{name}] {n_nodes:,} nodes | {n_edges:,} edges | '
          f'fraud_edges={y.sum():,} ({100*y.mean():.1f}%) [H][NT]')
    return {'name': name, 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': n_nodes, 'n_edges': n_edges, 'delta_L': n_edges}


def load_aml_pretrained(base, artif_sub, probs_sub, model, seed, name):
    artif = base / artif_sub
    probs = base / probs_sub
    npz = np.load(probs / f'{model}_seed{seed}_test.npz')
    scores = np.asarray(npz['p'], dtype=float)
    y = np.asarray(npz['y'], dtype=int)
    cache = torch.load(artif / 'edge_data_v4_clean.pt',
                       map_location='cpu', weights_only=False)
    ei_all = cache['ei_all_cpu']
    te_idx = cache['te_idx']
    if isinstance(te_idx, torch.Tensor): te_idx = te_idx.numpy()
    if isinstance(ei_all, torch.Tensor): ei_all = ei_all.numpy()
    src = ei_all[0, te_idx].astype(np.int64)
    dst = ei_all[1, te_idx].astype(np.int64)
    candidates = ['transactions.csv','transaction.csv',
                  'hi-large_trans.csv','hi-medium_trans.csv','hi-small_trans.csv',
                  'li-large_trans.csv','li-medium_trans.csv','li-small_trans.csv']
    csv_path = next((list(base.rglob(c))[0] for c in candidates
                     if list(base.rglob(c))), None)
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.lower()
    time_col = next(c for c in ['timestamp','time'] if c in df.columns)
    ts_raw = pd.to_numeric(df[time_col], errors='coerce').fillna(0).astype(np.int64).values
    order = np.argsort(ts_raw, kind='stable')
    ts_sort = ts_raw[order]
    src_col = next(c for c in ['sender_account_id','src'] if c in df.columns)
    dst_col = next(c for c in ['receiver_account_id','dst'] if c in df.columns)
    mask = df[src_col].astype(str).values[order] != df[dst_col].astype(str).values[order]
    timestamps = ts_sort[mask][te_idx]
    print(f'[{name}] {len(scores):,} edges | pos={y.sum():,} ({100*y.mean():.2f}%)')
    return {'name': name, 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': int(max(src.max(), dst.max()))+1,
            'n_edges': len(scores), 'delta_L': 7}

print('Loaders definidos.')

# ============================================================
# GNN Score Loader (replaces heuristic [H] loaders)
# Reads .npz files saved by nb05_gnn_training
# ============================================================

DELTA_L_MAP = {
    'ibm_aml_txns': 7, 'IBM_HI_Small': 30, 'IBM_HI_Medium': 30,
    'IBM_HI_Large': 30, 'IBM_LI_Small': 30, 'IBM_LI_Medium': 30,
    'IBM_LI_Large': 30, 'elliptic': 2, 'amazon_fraud': None,
    'yelp_fraud': None, 'paysim': 24,
}

def load_gnn_scores(dataset_name, delta_L=None):
    """Load GNN-trained edge scores from nb05 .npz files.
    Returns same dict format as other loaders: {name, scores, src, dst, timestamps, y, ...}
    """
    npz_path = GNN_SCORES / f'{dataset_name}_gnn_scores.npz'
    assert npz_path.exists(), f'{npz_path} not found. Run nb05 first.'
    npz = np.load(npz_path)
    scores = npz['p'].astype(float)
    y = npz['y'].astype(int)
    src = npz['src'].astype(np.int64)
    dst = npz['dst'].astype(np.int64)
    timestamps = npz['timestamps'].astype(np.int64)
    n_nodes = int(max(src.max(), dst.max()) + 1)
    n_edges = len(scores)
    pos = int(y.sum())
    if delta_L is None:
        delta_L = DELTA_L_MAP.get(dataset_name)
    if delta_L is None:
        delta_L = n_edges  # no temporal window (NT datasets)
    print(f'[{dataset_name}] {n_edges:,} edges | nodes={n_nodes:,} | '
          f'pos={pos:,} ({100*pos/n_edges:.2f}%) [GNN]')
    return {'name': dataset_name, 'scores': scores, 'src': src, 'dst': dst,
            'timestamps': timestamps, 'y': y,
            'n_nodes': n_nodes, 'n_edges': n_edges, 'delta_L': delta_L}


print('All loaders defined (including GNN score loader).')


# ======= CELL 6 =======
# CELULA 4B - Loaders para novos datasets reais: DGraph-Fin, T-Finance, Elliptic++
#
# Arquivos já extraídos em GrafosGNN/data/ (Google Drive):
#   DGraph-Fin : data/dgraph_fin/raw/dgraphfin.npz  (649 MB, numpy format)
#   T-Finance  : data/t_finance/tfinance             (652 MB, DGL binary format)
#   Elliptic++ : data/elliptic_plus/Elliptic++ Dataset/  (CSV files)
#
# Os loaders retornam None silenciosamente se os arquivos não existirem.

import os

# ─────────────────────────────────────────────────────────────────────────
# DGraph-Fin
# ─────────────────────────────────────────────────────────────────────────
def load_dgraph_fin():
    """Loader para DGraph-Fin (Finvolution Group, NeurIPS 2022).

    Arquivo: GrafosGNN/data/dgraph_fin/raw/dgraphfin.npz  (numpy format)

    Estrutura do .npz:
        x              float64[3_700_550, 17]   features de nó
        edge_index     int64[4_300_999, 2]       arestas (N,2) — transposta vs PyG!
        edge_type      int64[4_300_999]          tipo de relacionamento
        edge_timestamp int64[4_300_999]          timestamp ordinal
        y              int64[3_700_550]           label (0=normal, 1=fraude, 2=blacklist)
        train_mask / valid_mask / test_mask       índices (não boolean)

    Para BTCS: y_bin = (y>0); edge scores = max(score_src, score_dst)
    delta_L = 30 time steps
    """
    raw_dir = DATA / 'dgraph_fin' / 'raw'
    npz_path = raw_dir / 'dgraphfin.npz'

    # Fallbacks: PyG .pt ou zip original
    pt_path  = raw_dir / 'DGraphFin.pt'
    zip_path = raw_dir / 'DGraphFin.zip'

    if not npz_path.exists() and not pt_path.exists() and not zip_path.exists():
        print('[DGraph-Fin] Arquivo não encontrado — ver docs/datasets.md')
        return None

    try:
        # ── CASO 1: numpy .npz (formato real baixado) ──
        if npz_path.exists():
            data  = np.load(npz_path, allow_pickle=True)
            x      = data['x'].astype(np.float32)         # (N, 17)
            ei_np  = data['edge_index']                    # (E, 2) — NOTA: shape (E,2) não (2,E)
            if ei_np.shape[0] == 2:                        # caso já seja (2, E)
                src = ei_np[0].astype(np.int64)
                dst = ei_np[1].astype(np.int64)
            else:                                           # shape (E, 2)
                src = ei_np[:, 0].astype(np.int64)
                dst = ei_np[:, 1].astype(np.int64)
            y_node = data['y'].astype(int)
            et     = data['edge_timestamp'].astype(np.int64) if 'edge_timestamp' in data else np.arange(len(src), dtype=np.int64)

        # ── CASO 2: PyTorch .pt ──
        else:
            import torch
            if not pt_path.exists() and zip_path.exists():
                import zipfile
                print('[DGraph-Fin] Extraindo zip...')
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(raw_dir)
            try:
                from torch_geometric.datasets import DGraphFin as _DGF
                ds = _DGF(root=str(DATA / 'dgraph_fin'))
                raw = ds[0]
            except Exception:
                raw = torch.load(pt_path, map_location='cpu', weights_only=False)
            if hasattr(raw, 'x'):
                x      = raw.x.numpy().astype(np.float32)
                ei_t   = raw.edge_index.numpy()
                src, dst = ei_t[0].astype(np.int64), ei_t[1].astype(np.int64)
                y_node = raw.y.numpy().astype(int)
                et     = raw.edge_time.numpy().astype(np.int64) if hasattr(raw, 'edge_time') else np.arange(len(src), dtype=np.int64)
            else:  # dict
                x      = np.array(raw['x'], dtype=np.float32)
                ei_t   = np.array(raw['edge_index'])
                src, dst = ei_t[0].astype(np.int64), ei_t[1].astype(np.int64)
                y_node = np.array(raw['y'], dtype=int)
                et_raw = raw.get('edge_time', raw.get('edge_timestamp', None))
                et     = np.array(et_raw, dtype=np.int64) if et_raw is not None else np.arange(len(src), dtype=np.int64)

        n_nodes = x.shape[0]
        n_edges = len(src)

        # Binary label: fraude (1) ou blacklist (2) → ambos suspeitos
        y_node_bin = (y_node > 0).astype(int)

        # Heuristic: feature norm (substituir por GNN do nb05)
        feat_norm = np.linalg.norm(x, axis=1).astype(np.float64)
        feat_norm = (feat_norm - feat_norm.min()) / (feat_norm.max() - feat_norm.min() + 1e-8)
        scores_edge = np.maximum(feat_norm[src], feat_norm[dst]).astype(np.float32)
        scores_edge += np.random.RandomState(42).uniform(0, 0.01, n_edges)

        y_edge = np.maximum(y_node_bin[src], y_node_bin[dst]).astype(int)
        pos = int(y_edge.sum())
        print(f'[DGraph-Fin] {n_edges:,} edges | nodes={n_nodes:,} | '
              f'fraud_edges={pos:,} ({100*pos/n_edges:.2f}%) [H]')

        return {'name': 'dgraph_fin', 'scores': scores_edge, 'src': src, 'dst': dst,
                'timestamps': et, 'y': y_edge,
                'n_nodes': n_nodes, 'n_edges': n_edges, 'delta_L': 30}

    except Exception as e:
        print(f'[DGraph-Fin] Erro ao carregar: {e}')
        import traceback; traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────
# T-Finance
# ─────────────────────────────────────────────────────────────────────────
def load_t_finance():
    """Loader para T-Finance (ICML 2022, Tang et al.).

    Arquivo: GrafosGNN/data/t_finance/tfinance  (DGL binary format, sem extensão)

    Estrutura DGL:
        g.ndata['feature']  float64[N, 10]       features de nó
        g.ndata['label']    int64[N, 2]           one-hot: [normal, fraude]
        g.edges()                                 src/dst sem timestamps

    Nota: versão distribuída tem 39 357 nós (fraud rate = 4.58%, igual ao paper).
    Para BTCS: node scores → edge scores via max(), delta_L = n_edges (sem janela)
    """
    t_dir = DATA / 't_finance'

    # Aceita vários nomes de arquivo: sem extensão (real) ou com extensão (variantes)
    candidates = ['tfinance', 't-finance.pt', 'T-Finance.pt', 'data.pt',
                  'tfinance.pt', 't_finance.pt', 'TFinance.pt']
    file_path = next((t_dir / f for f in candidates if (t_dir / f).exists()), None)

    # Procura em subdirectórios também
    if file_path is None and t_dir.exists():
        for sub in t_dir.iterdir():
            if sub.is_dir():
                file_path = next((sub / f for f in candidates if (sub / f).exists()), None)
                if file_path:
                    break

    if file_path is None:
        print('[T-Finance] Arquivo não encontrado — ver docs/datasets.md')
        return None

    try:
        # Tenta primeiro como DGL (formato do arquivo real 'tfinance')
        try:
            import os as _os
            _os.environ.setdefault('DGLBACKEND', 'pytorch')
            import dgl as _dgl
            gs, _ = _dgl.load_graphs(str(file_path))
            g = gs[0]
            import torch as _torch
            feat   = g.ndata['feature'].numpy().astype(np.float32)     # (N, 10)
            labels = g.ndata['label'].numpy().astype(int)               # (N, 2) one-hot
            y_node = labels[:, 1]                                       # coluna 1 = fraude
            src_t, dst_t = g.edges()
            src = src_t.numpy().astype(np.int64)
            dst = dst_t.numpy().astype(np.int64)
            x = feat
        except Exception as _dgl_err:
            # Fallback: PyTorch .pt
            import torch
            raw = torch.load(file_path, map_location='cpu', weights_only=False)
            if hasattr(raw, 'x'):
                x      = raw.x.numpy().astype(np.float32)
                ei     = raw.edge_index.numpy()
                y_node = raw.y.numpy().astype(int).flatten()
            elif isinstance(raw, dict):
                x      = np.array(raw['x'], dtype=np.float32)
                ei     = np.array(raw['edge_index'])
                y_node = np.array(raw['y'], dtype=int).flatten()
            else:
                raise ValueError(f'Formato desconhecido: {type(raw)}  (DGL erro: {_dgl_err})')
            src = ei[0].astype(np.int64)
            dst = ei[1].astype(np.int64)

        n_nodes = x.shape[0]
        n_edges = len(src)

        # Feature-based heuristic scores (substituir por GNN do nb05)
        feat_norm = np.linalg.norm(x, axis=1).astype(np.float64)
        feat_norm = (feat_norm - feat_norm.min()) / (feat_norm.max() - feat_norm.min() + 1e-8)
        scores_edge = np.maximum(feat_norm[src], feat_norm[dst]).astype(np.float32)
        scores_edge += np.random.RandomState(42).uniform(0, 0.01, n_edges)

        y_edge = np.maximum(y_node[src], y_node[dst]).astype(int)
        pos = int(y_edge.sum())
        print(f'[T-Finance] {n_edges:,} edges | nodes={n_nodes:,} | '
              f'fraud_edges={pos:,} ({100*pos/n_edges:.2f}%) [H]')

        return {'name': 't_finance', 'scores': scores_edge, 'src': src, 'dst': dst,
                'timestamps': np.arange(n_edges, dtype=np.int64),  # NT: sem timestamps
                'y': y_edge,
                'n_nodes': n_nodes, 'n_edges': n_edges,
                'delta_L': n_edges}  # sem janela temporal

    except Exception as e:
        print(f'[T-Finance] Erro ao carregar: {e}')
        import traceback; traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────
# Elliptic++
# ─────────────────────────────────────────────────────────────────────────
def load_elliptic_plus(use_actors=False):
    """Loader para Elliptic++ (KDD 2023, extends Elliptic with wallet/actor labels).

    Arquivos: GrafosGNN/data/elliptic_plus/Elliptic++ Dataset/
        txs_features.csv     ← features de nó (col 0=txId, col 1=timestep, cols 2+=features)
        txs_classes.csv      ← labels ('1'=illicit, '2'=licit, 'unknown')
        txs_edgelist.csv     ← arestas tx→tx

    Para BTCS: usa Transactions Dataset. delta_L = 2 time steps.
    """
    ep_dir = DATA / 'elliptic_plus'

    # Detecta estrutura de subpasta — prioridade: 'Elliptic++ Dataset', depois flat
    for sub in ['Elliptic++ Dataset', 'Transactions Dataset', '']:
        tx_dir = ep_dir / sub if sub else ep_dir
        if (tx_dir / 'txs_features.csv').exists() or (tx_dir / 'elliptic_txs_features.csv').exists():
            break
    else:
        print('[Elliptic++] Arquivos não encontrados — ver docs/datasets.md')
        return None

    feat_candidates = ['txs_features.csv', 'elliptic_txs_features.csv']
    edge_candidates = ['txs_edgelist.csv', 'elliptic_txs_edgelist.csv']
    cls_candidates  = ['txs_classes.csv',  'elliptic_txs_classes.csv']

    feat_csv = next((tx_dir / f for f in feat_candidates if (tx_dir / f).exists()), None)
    edge_csv = next((tx_dir / f for f in edge_candidates if (tx_dir / f).exists()), None)
    cls_csv  = next((tx_dir / f for f in cls_candidates  if (tx_dir / f).exists()), None)

    if feat_csv is None or edge_csv is None or cls_csv is None:
        missing = [n for n,v in [('features',feat_csv),('edges',edge_csv),('classes',cls_csv)] if v is None]
        print(f'[Elliptic++] Arquivos faltando: {missing}')
        return None

    try:
        df_feat  = pd.read_csv(feat_csv, header=None)
        df_edges = pd.read_csv(edge_csv)
        df_class = pd.read_csv(cls_csv)
        df_class.columns = ['txId', 'class']

        # Node labels: '1'=illicit, '2'=licit
        node_label = {}
        for _, row in df_class.iterrows():
            c = str(row['class'])
            if c in ['1', '2']:
                node_label[int(row['txId'])] = (1 if c == '1' else 0)

        # Time steps from feature col 1
        node_ts = dict(zip(df_feat[0].astype(int), df_feat[1].astype(int)))

        df_edges.columns = ['src', 'dst']
        all_ids = pd.unique(pd.concat([df_edges['src'], df_edges['dst']]))
        id_map  = {int(v): i for i, v in enumerate(sorted(all_ids))}
        src = df_edges['src'].map(id_map).values.astype(np.int64)
        dst = df_edges['dst'].map(id_map).values.astype(np.int64)

        y_src = np.array([node_label.get(int(s), 0) for s in df_edges['src']])
        y_dst = np.array([node_label.get(int(d), 0) for d in df_edges['dst']])
        y     = np.maximum(y_src, y_dst).astype(int)

        ts_src = np.array([node_ts.get(int(s), 0) for s in df_edges['src']])
        ts_dst = np.array([node_ts.get(int(d), 0) for d in df_edges['dst']])
        timestamps = np.maximum(ts_src, ts_dst).astype(np.int64)

        def ns(nid):
            if nid in node_label: return 1.0 if node_label[nid] == 1 else 0.0
            return 0.5
        scores = np.maximum(
            np.array([ns(int(s)) for s in df_edges['src']]),
            np.array([ns(int(d)) for d in df_edges['dst']]))
        scores += np.random.RandomState(42).uniform(0, 0.01, len(scores))

        n_nodes = len(id_map)
        n_edges = len(src)
        pos = int(y.sum())
        print(f'[Elliptic++] {n_edges:,} edges | nodes={n_nodes:,} | '
              f'illicit_edges={pos:,} ({100*pos/n_edges:.1f}%) [H]')

        return {'name': 'elliptic_plus', 'scores': scores, 'src': src, 'dst': dst,
                'timestamps': timestamps, 'y': y,
                'n_nodes': n_nodes, 'n_edges': n_edges, 'delta_L': 2}

    except Exception as e:
        print(f'[Elliptic++] Erro ao carregar: {e}')
        import traceback; traceback.print_exc()
        return None


print('Loaders DGraph-Fin, T-Finance, Elliptic++ definidos.')
print('Tentando carregar...')
print('Loaders 4B prontos.')
