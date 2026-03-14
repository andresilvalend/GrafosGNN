"""
download_datasets.py — Baixar todos os datasets para o Google Drive.
Rodar no Colab ou terminal local com internet.

Uso no Colab:
  1) Montar Drive
  2) !pip install kaggle gdown --quiet
  3) Configurar Kaggle API key (ver instruções abaixo)
  4) %run scripts/download_datasets.py

Uso local:
  python scripts/download_datasets.py
"""

import os, subprocess, sys, zipfile, gzip, shutil
from pathlib import Path

# ---------- CONFIG ----------
# Ajuste BASE se rodar fora do Colab
try:
    from google.colab import drive
    BASE = Path("/content/drive/MyDrive/GrafosGNN/data")
except ImportError:
    BASE = Path(__file__).resolve().parent.parent / "data"

BASE.mkdir(parents=True, exist_ok=True)
print(f"[INFO] Base dir: {BASE}")

def run(cmd):
    """Executa comando shell e printa output."""
    print(f"  $ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [WARN] {r.stderr.strip()}")
    return r

# ============================================================
# 1. BITCOIN OTC  (SNAP — download direto, sem autenticação)
# ============================================================
def download_bitcoin_otc():
    d = BASE / "bitcoin_otc"
    d.mkdir(exist_ok=True)
    out = d / "soc-sign-bitcoinotc.csv"
    if out.exists():
        print("[SKIP] Bitcoin OTC já existe")
        return
    print("[1/6] Baixando Bitcoin OTC (SNAP)...")
    gz = d / "soc-sign-bitcoinotc.csv.gz"
    run(f"wget -q -O {gz} https://snap.stanford.edu/data/soc-sign-bitcoinotc.csv.gz")
    # Descompactar
    import gzip as gz_mod
    with gz_mod.open(gz, 'rb') as f_in, open(out, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz.unlink()
    print(f"  -> {out}  ({out.stat().st_size / 1e6:.1f} MB)")

# ============================================================
# 2. BITCOIN ALPHA  (SNAP — download direto)
# ============================================================
def download_bitcoin_alpha():
    d = BASE / "bitcoin_alpha"
    d.mkdir(exist_ok=True)
    out = d / "soc-sign-bitcoinalpha.csv"
    if out.exists():
        print("[SKIP] Bitcoin Alpha já existe")
        return
    print("[2/6] Baixando Bitcoin Alpha (SNAP)...")
    gz = d / "soc-sign-bitcoinalpha.csv.gz"
    run(f"wget -q -O {gz} https://snap.stanford.edu/data/soc-sign-bitcoinalpha.csv.gz")
    import gzip as gz_mod
    with gz_mod.open(gz, 'rb') as f_in, open(out, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz.unlink()
    print(f"  -> {out}  ({out.stat().st_size / 1e6:.1f} MB)")

# ============================================================
# 3. PAYSIM  (Kaggle — precisa de API key)
# ============================================================
def download_paysim():
    d = BASE / "paysim"
    d.mkdir(exist_ok=True)
    # Checa se já baixou
    csvs = list(d.glob("*.csv"))
    if csvs:
        print(f"[SKIP] PaySim já existe ({len(csvs)} csvs)")
        return
    print("[3/6] Baixando PaySim (Kaggle)...")
    print("  [INFO] Requer Kaggle API key em ~/.kaggle/kaggle.json")
    print("  [INFO] Para configurar no Colab:")
    print("    from google.colab import files")
    print("    files.upload()  # upload kaggle.json")
    print("    !mkdir -p ~/.kaggle && mv kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json")
    r = run(f"kaggle datasets download -d ealaxi/paysim1 -p {d} --unzip")
    if r.returncode != 0:
        print("  [FALLBACK] Tentando download alternativo via gdown...")
        # PaySim também disponível em outros mirrors
        print("  [MANUAL] Baixe manualmente de: https://www.kaggle.com/datasets/ealaxi/paysim1")
        print(f"           e extraia em: {d}/")

# ============================================================
# 4. ELLIPTIC  (Kaggle — dataset Bitcoin)
# ============================================================
def download_elliptic():
    d = BASE / "elliptic"
    d.mkdir(exist_ok=True)
    if (d / "elliptic_txs_features.csv").exists() or list(d.glob("*features*")):
        print("[SKIP] Elliptic já existe")
        return
    print("[4/6] Baixando Elliptic (Kaggle)...")
    r = run(f"kaggle datasets download -d ellipticco/elliptic-data-set -p {d} --unzip")
    if r.returncode != 0:
        print("  [MANUAL] Baixe de: https://www.kaggle.com/datasets/ellipticco/elliptic-data-set")
        print(f"           e extraia em: {d}/")
    # Elliptic vem com subpasta, mover arquivos para raiz
    for sub in d.glob("elliptic_bitcoin_dataset/*"):
        dest = d / sub.name
        if not dest.exists():
            shutil.move(str(sub), str(dest))

# ============================================================
# 5. DGRAPH-FIN  (Site oficial — requer registro)
# ============================================================
def download_dgraph_fin():
    d = BASE / "dgraph_fin"
    d.mkdir(exist_ok=True)
    if list(d.glob("*.csv")) or list(d.glob("*.pt")) or list(d.glob("*.npz")):
        print("[SKIP] DGraph-Fin já existe")
        return
    print("[5/6] DGraph-Fin requer registro manual:")
    print("  1. Acesse: https://dgraph.xinye.com/")
    print("  2. Registre-se e baixe o dataset DGraphFin")
    print(f"  3. Extraia em: {d}/")
    print("  [ALT] Também disponível via DGL: dgl.data.FraudDataset('amazon')")
    print("        ou torch_geometric.datasets.DGraphFin(root=...)")

# ============================================================
# 6. ETHEREUM PHISHING  (Kaggle)
# ============================================================
def download_ethereum():
    d = BASE / "ethereum_phishing"
    d.mkdir(exist_ok=True)
    if list(d.glob("*.csv")):
        print(f"[SKIP] Ethereum Phishing já existe")
        return
    print("[6/6] Baixando Ethereum Phishing (Kaggle)...")
    r = run(f"kaggle datasets download -d xblock/ethereum-phishing-transaction-network -p {d} --unzip")
    if r.returncode != 0:
        print("  [MANUAL] Baixe de: https://www.kaggle.com/datasets/xblock/ethereum-phishing-transaction-network")
        print(f"           e extraia em: {d}/")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BTCS Multi-Dataset Downloader")
    print("=" * 60)

    download_bitcoin_otc()
    download_bitcoin_alpha()
    download_paysim()
    download_elliptic()
    download_dgraph_fin()
    download_ethereum()

    print("\n" + "=" * 60)
    print("STATUS FINAL:")
    print("=" * 60)
    for ds in sorted(BASE.iterdir()):
        if ds.is_dir():
            files = list(ds.rglob("*"))
            total = sum(f.stat().st_size for f in files if f.is_file())
            n_files = sum(1 for f in files if f.is_file())
            print(f"  {ds.name:25s}  {n_files:3d} files  {total/1e6:8.1f} MB")
