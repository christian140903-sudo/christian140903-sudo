"""Step 0a: fetch the small metadata tables of measurement-db at the pinned revision and assemble the catalog.

Needs your OWN Hugging Face account: accept the access conditions of `aims-foundations/measurement-db` on huggingface.co,
create a read token and `export HF_TOKEN=...` (the token is read from the environment only, never stored or printed).
Only PAIEC_WORK (a directory you choose) is written:
    $PAIEC_WORK/cache/ft/<benchmark>/benchmarks.parquet and subjects.parquet   (about 11 MB for all 281 folders)
    $PAIEC_WORK/meta/catalog.parquet                                          (input of modell/basis/build_basis.py)
Every downloaded file is checked against scripts/checksums_ft_tables.sha256 (SHA-256) and, where the Hub reports one,
against the Hub's LFS SHA-256. A mismatch aborts (fail-closed). Revision is fixed; there is no option to change it.

Usage: python3 -I scripts/download_data.py [--only name1,name2]
Then:  python3 -I modell/basis/build_basis.py 3        (Step 0b, streams items/responses by range requests)
Not covered: the catalog columns ch_* and n_claims of the author's local catalog are not rebuilt (no later step uses them).
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modell" / "basis"))
import hfio  # noqa: E402

REV = "54074453da7b9911be0f48e4c560be547bc84d21"
SMALL = ("benchmarks", "subjects")
COUNTED = ("subjects", "items", "responses", "traces", "assets")


def load_expected(path):
    exp = {}
    for line in Path(path).read_text().splitlines():
        h, p = line.split("  ", 1)
        exp[p] = h
    return exp


def fetch(s, path, size, lfs_oid, expected):
    r = s.get(hfio.resolve_url(REV, path), timeout=300)
    if r.status_code != 200:
        raise hfio.HFError(f"GET {path} -> HTTP {r.status_code}")
    data = r.content
    if len(data) != size:
        raise RuntimeError(f"{path}: size {len(data)} != {size}")
    h = hashlib.sha256(data).hexdigest()
    if lfs_oid and h != lfs_oid:
        raise RuntimeError(f"{path}: sha256 differs from Hub LFS oid")
    if expected is not None and h != expected:
        raise RuntimeError(f"{path}: sha256 differs from scripts/checksums_ft_tables.sha256")
    return data


def assemble_catalog(ft_dir, rows_by_folder):
    """ft_dir/<folder>/benchmarks.parquet (1 row each) + footer row counts -> catalog DataFrame (sorted by folder)."""
    import pandas as pd
    parts = []
    for folder in sorted(rows_by_folder):
        t = pd.read_parquet(Path(ft_dir) / folder / "benchmarks.parquet").drop(columns=["description"], errors="ignore")
        t["folder"] = folder
        for k in COUNTED:
            t["rows_" + k] = rows_by_folder[folder].get(k)
        parts.append(t)
    return pd.concat(parts, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    work = os.environ.get("PAIEC_WORK")
    if not work:
        sys.exit("PAIEC_WORK is not set (directory for downloaded data)")
    work = Path(work)
    expected = load_expected(REPO_ROOT / "scripts" / "checksums_ft_tables.sha256")
    s = hfio.session()
    top, _ = hfio.get_json(s, f"/api/datasets/{hfio.REPO}/tree/{REV}")
    folders = sorted(e["path"] for e in top if e["type"] == "directory")
    if a.only:
        folders = [f for f in folders if f in set(a.only.split(","))]
    rows = {}
    for b in folders:
        tree, _ = hfio.get_json(s, f"/api/datasets/{hfio.REPO}/tree/{REV}/{b}/formatted_tables")
        by = {Path(e["path"]).stem: e for e in tree if e["type"] == "file" and e["path"].endswith(".parquet")}
        out = work / "cache" / "ft" / b
        out.mkdir(parents=True, exist_ok=True)
        for k in SMALL:
            e = by[k]
            p = f"{b}/formatted_tables/{k}.parquet"
            if p not in expected and not a.only:
                raise RuntimeError(f"no shipped checksum for {p}")
            data = fetch(s, p, e["size"], (e.get("lfs") or {}).get("oid"), expected.get(p))
            (out / f"{k}.parquet").write_bytes(data)
        import pyarrow.parquet as pq
        rows[b] = {}
        for k in COUNTED:
            if k in by:
                f = hfio.RangeFile(s, REV, f"{b}/formatted_tables/{k}.parquet", size=by[k]["size"], block=1 << 16)
                rows[b][k] = pq.ParquetFile(f).metadata.num_rows
        print("ok", b, flush=True)
    (work / "meta").mkdir(parents=True, exist_ok=True)
    assemble_catalog(work / "cache" / "ft", rows).to_parquet(work / "meta" / "catalog.parquet")
    print("catalog written:", len(rows), "folders")


if __name__ == "__main__":
    main()
