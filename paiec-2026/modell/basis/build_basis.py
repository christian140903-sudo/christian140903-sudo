"""Baut die gemeinsame, sparsame Datenbasis aus measurement-db (sha 54074453) — eigener Code, nur Lesen.

Ausgabe unter paiec-data/basis/:
  benchmarks.parquet            Katalog (281) + b_code, direction, scale_kind, seen_by_baseline_script
  subjects.parquet              alle Subjekt-Zeilen (benchmark_id, subject_id, Metadaten) + s_code (global)
  items/<bm>.parquet            i_code, item_id, raw_item_id, content_hash (Original), eigene Hashes, Längen, Flags
  responses/benchmark=<bm>/part-0.parquet   b_code, s_code, i_code, trial, test_condition, interactors, response (roh)
  stats/<bm>.json               Prüfzählungen je Benchmark (Fertig-Marke: Datei existiert)

Was tut die Schicht darunter im Fehlerfall schon selbst? hfio wiederholt 429/5xx und löst abgelaufene
signierte URLs neu auf; pyarrow wirft bei kaputten Seiten. Hier: jede Abweichung der Zeilenzahl gegen die
Fußzeile ist fail-closed (Benchmark wird nicht als fertig markiert, Fehler in errors.log, Zeilen >>).
Aufruf: python3 -I build_basis.py [n_worker] [nur_diese_bm,...]
"""
import sys, os, json, hashlib, unicodedata, re, time, traceback, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hfio
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

REV = "54074453da7b9911be0f48e4c560be547bc84d21"
ROOT = os.path.join(os.environ.get("PAIEC_WORK", "work"), "")  # Arbeitsordner, wie daten.py
META = ROOT + "meta/"
CACHE = ROOT + "cache/ft/"
OUT = ROOT + "basis/"
WS = re.compile(r"\s+")


def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def norm_strict(s):  # exakt wie Builder: NFC + strip
    return unicodedata.normalize("NFC", s).strip()


def norm_loose(s):  # eigene, lockerere Normalisierung: NFC, casefold, Whitespace-Läufe -> ' ', strip
    return WS.sub(" ", unicodedata.normalize("NFC", s).casefold()).strip()


def log(msg):
    with open(OUT + "build.log", "a") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")


def offsets(cat, col):
    off, o = {}, 0
    for b, n in zip(cat.folder, cat[col]):
        off[b] = o
        o += int(n)
    return off


def build_items(s, b, i_off, expected):
    # Speichersicher (Lehre aus OOM 09:2x UTC): je Row-Group und je Spalte lesen, Texte in Scheiben à 1000 nach Python.
    f = hfio.RangeFile(s, REV, f"{b}/formatted_tables/items.parquet", block=1 << 23)
    f.max_cache_blocks = 4
    pf = pq.ParquetFile(f)
    recs = {k: [] for k in ["item_id", "raw_item_id", "content_hash", "own_hash_strict", "own_hash_loose", "content_len",
                            "has_assets", "item_features", "ref_answer_hash", "ref_answer_len", "has_rule",
                            "criterion_scale"]}
    st = {"items_rows": 0, "items_bm_mismatch": 0, "content_null": 0, "content_hash_null": 0,
          "content_hash_mismatch": 0, "content_hash_mismatch_examples": [], "criterion_parse_error": 0}
    SL = 1000

    def slices(arr):
        for a in range(0, len(arr), SL):
            yield arr.slice(a, SL).to_pylist()

    for g_i in range(pf.metadata.num_row_groups):
        small = pf.read_row_group(g_i, columns=["item_id", "benchmark_id", "raw_item_id", "content_hash", "item_features",
                                                "asset_manifest"])
        ids = small.column("item_id").to_pylist()
        bms = small.column("benchmark_id").to_pylist()
        chs = small.column("content_hash").to_pylist()
        st["items_rows"] += len(ids)
        st["items_bm_mismatch"] += sum(1 for x in bms if x != b)
        st["content_hash_null"] += sum(1 for x in chs if x is None)
        recs["item_id"] += ids
        recs["raw_item_id"] += small.column("raw_item_id").to_pylist()
        recs["content_hash"] += chs
        recs["item_features"] += small.column("item_features").to_pylist()
        recs["has_assets"] += small.column("asset_manifest").is_valid().to_pylist()
        del small, bms
        content = pf.read_row_group(g_i, columns=["content"]).column("content").combine_chunks()
        k = 0
        for part in slices(content):
            for c in part:
                ch = chs[k]
                if c is None:
                    st["content_null"] += 1
                    hs = hl = ln = None
                else:
                    hs = sha16(norm_strict(c))
                    hl = sha16(norm_loose(c))
                    ln = len(c)
                    if ch is not None and ch != hs:
                        st["content_hash_mismatch"] += 1
                        if len(st["content_hash_mismatch_examples"]) < 5:
                            st["content_hash_mismatch_examples"].append(ids[k])
                recs["own_hash_strict"].append(hs)
                recs["own_hash_loose"].append(hl)
                recs["content_len"].append(ln)
                k += 1
        del content
        crit = pf.read_row_group(g_i, columns=["grading_criterion"]).column("grading_criterion").combine_chunks()
        for part in slices(crit):
            for g in part:
                ra_h = ra_len = sc = None
                rule = None
                if g is not None:
                    try:
                        gj = json.loads(g)
                        ra = gj.get("reference_answer")
                        if ra is not None:
                            ras = ra if isinstance(ra, str) else json.dumps(ra, sort_keys=True, ensure_ascii=False)
                            ra_h = sha16(norm_strict(ras))
                            ra_len = len(ras)
                        rule = gj.get("rule") is not None
                        if gj.get("response_scale") is not None:
                            sc = json.dumps(gj["response_scale"], sort_keys=True)
                    except Exception:
                        st["criterion_parse_error"] += 1
                recs["ref_answer_hash"].append(ra_h)
                recs["ref_answer_len"].append(ra_len)
                recs["has_rule"].append(rule)
                recs["criterion_scale"].append(sc)
        del crit
    if st["items_rows"] != expected:
        raise RuntimeError(f"{b}: items rows {st['items_rows']} != footer {expected}")
    n = st["items_rows"]
    tab = pa.table({
        "i_code": pa.array(np.arange(i_off, i_off + n, dtype=np.int32)),
        "benchmark_id": pa.array([b] * n).dictionary_encode(),
        "item_id": pa.array(recs["item_id"], pa.string()),
        "raw_item_id": pa.array(recs["raw_item_id"], pa.string()),
        "content_hash": pa.array(recs["content_hash"], pa.string()),
        "own_hash_strict": pa.array(recs["own_hash_strict"], pa.string()),
        "own_hash_loose": pa.array(recs["own_hash_loose"], pa.string()),
        "content_len": pa.array(recs["content_len"], pa.int64()),
        "has_assets": pa.array(recs["has_assets"], pa.bool_()),
        "item_features": pa.array(recs["item_features"], pa.string()),
        "ref_answer_hash": pa.array(recs["ref_answer_hash"], pa.string()),
        "ref_answer_len": pa.array(recs["ref_answer_len"], pa.int64()),
        "has_rule": pa.array(recs["has_rule"], pa.bool_()),
        "criterion_scale": pa.array(recs["criterion_scale"], pa.string()),
    })
    item_ids = pd.Index(recs["item_id"])
    st["items_id_unique"] = bool(item_ids.is_unique)
    st["items_bytes_fetched"] = f.bytes_fetched
    return tab, item_ids, st


def build_responses(s, b, b_code, s_index, s_off, i_index, i_off, expected, out_path, binary):
    f = hfio.RangeFile(s, REV, f"{b}/formatted_tables/responses.parquet", block=1 << 23)
    f.max_cache_blocks = 8
    pf = pq.ParquetFile(f, read_dictionary=["subject_id", "item_id", "test_condition", "interactors", "benchmark_id"])
    cols = ["subject_id", "item_id", "benchmark_id", "trial", "test_condition", "interactors", "response"]
    st = {"resp_rows": 0, "resp_bm_mismatch": 0, "fk_subject_miss": 0, "fk_item_miss": 0, "response_null": 0,
          "response_nonfinite": 0, "trial_min": None, "trial_max": None}
    vc = {}
    schema = pa.schema([("b_code", pa.int16()), ("s_code", pa.int32()), ("i_code", pa.int32()), ("trial", pa.int32()),
                        ("test_condition", pa.dictionary(pa.int32(), pa.string())),
                        ("interactors", pa.dictionary(pa.int32(), pa.string())), ("response", pa.float64())])
    tmp = out_path + ".tmp"
    w = pq.ParquetWriter(tmp, schema, compression="zstd", compression_level=6)
    for batch in pf.iter_batches(columns=cols, batch_size=1_000_000):
        n = batch.num_rows
        st["resp_rows"] += n
        bm = batch.column("benchmark_id")
        bmd = bm.dictionary.to_pylist()
        bad = [i for i, x in enumerate(bmd) if x != b]
        if bad:
            st["resp_bm_mismatch"] += int(np.isin(bm.indices.to_numpy(zero_copy_only=False), bad).sum())

        def codes(col, index, off, key):
            arr = batch.column(col)
            loc = index.get_indexer(arr.dictionary.to_pylist())
            idx = arr.indices.to_numpy(zero_copy_only=False)
            m = loc[idx]
            miss = int((m < 0).sum())
            st[key] += miss
            return np.where(m < 0, -1, m + off).astype(np.int32)

        sc = codes("subject_id", s_index, s_off, "fk_subject_miss")
        ic = codes("item_id", i_index, i_off, "fk_item_miss")
        trial = batch.column("trial").to_numpy(zero_copy_only=False)
        tmin, tmax = int(trial.min()), int(trial.max())
        st["trial_min"] = tmin if st["trial_min"] is None else min(st["trial_min"], tmin)
        st["trial_max"] = tmax if st["trial_max"] is None else max(st["trial_max"], tmax)
        resp = batch.column("response")
        st["response_null"] += resp.null_count
        rv = resp.to_numpy(zero_copy_only=False)
        st["response_nonfinite"] += int((~np.isfinite(rv[~np.isnan(rv)])).sum()) if rv.size else 0
        u, cnt = np.unique(rv[~np.isnan(rv)], return_counts=True)
        if len(u) <= 50:
            for a, c in zip(u.tolist(), cnt.tolist()):
                vc[repr(a)] = vc.get(repr(a), 0) + c
        else:
            vc["__many__"] = vc.get("__many__", 0) + int(cnt.sum())

        def dictcol(col):
            arr = batch.column(col)
            return pa.DictionaryArray.from_arrays(arr.indices.cast(pa.int32()), arr.dictionary.cast(pa.string()))

        t = pa.table({"b_code": pa.array(np.full(n, b_code, dtype=np.int16)), "s_code": pa.array(sc),
                      "i_code": pa.array(ic), "trial": pa.array(trial.astype(np.int32)),
                      "test_condition": dictcol("test_condition"), "interactors": dictcol("interactors"),
                      "response": resp}, schema=schema)
        w.write_table(t, row_group_size=1_000_000)
    w.close()
    if st["resp_rows"] != expected:
        os.remove(tmp)
        raise RuntimeError(f"{b}: responses rows {st['resp_rows']} != footer {expected}")
    st["response_value_counts"] = vc
    st["resp_bytes_fetched"] = f.bytes_fetched
    # Eindeutigkeit des Beobachtungsschlüssels (s, i, trial, test_condition, interactors), NULL als ein Wert
    import pyarrow.compute as pc
    r = pq.read_table(tmp, columns=["s_code", "i_code", "trial", "test_condition", "interactors"])

    def strcodes(col):  # globale Codes über alle Batches (vereinheitlichtes Dictionary), NULL als eigener Wert -1
        ca = r.column(col).unify_dictionaries()
        parts = [pc.fill_null(ch.indices.cast(pa.int64()), -1).to_numpy(zero_copy_only=False) for ch in ca.chunks]
        return np.concatenate(parts) if parts else np.zeros(0, np.int64)

    df = pd.DataFrame({"s": r.column("s_code").to_numpy(), "i": r.column("i_code").to_numpy(),
                       "t": r.column("trial").to_numpy(), "c": strcodes("test_condition"), "x": strcodes("interactors")})
    st["dup_observation_keys"] = int(df.duplicated(["s", "i", "t", "c", "x"]).sum())
    st["distinct_subject_item_pairs"] = int(df[["s", "i"]].drop_duplicates().shape[0])
    st["distinct_subjects_in_responses"] = int(df.s.nunique())
    st["distinct_items_in_responses"] = int(df.i.nunique())
    del df, r
    os.replace(tmp, out_path)
    return st


def job(args):
    b, b_code, s_off, i_off, rows, binary = args
    if os.path.exists(OUT + f"stats/{b}.json"):
        return b, "skip"
    try:
        t0 = time.time()
        s = hfio.session(True)
        subj = pq.read_table(CACHE + f"{b}/subjects.parquet").to_pandas()
        s_index = pd.Index(subj.subject_id)
        st = {"benchmark": b, "b_code": b_code, "subjects_rows": len(subj), "subjects_id_unique": bool(s_index.is_unique)}
        itab, i_index, sti = build_items(s, b, i_off, rows["items"])
        st.update(sti)
        pq.write_table(itab, OUT + f"items/{b}.parquet", compression="zstd")
        os.makedirs(OUT + f"responses/benchmark={b}", exist_ok=True)
        str_ = build_responses(s, b, b_code, s_index, s_off, i_index, i_off, rows["responses"],
                               OUT + f"responses/benchmark={b}/part-0.parquet", binary)
        st.update(str_)
        st["seconds"] = round(time.time() - t0, 1)
        with open(OUT + f"stats/{b}.json", "w") as f:
            json.dump(st, f)
        log(f"ok {b} items={st['items_rows']} resp={st['resp_rows']} {st['seconds']}s")
        return b, "ok"
    except Exception as ex:
        with open(OUT + "errors.log", "a") as f:
            f.write(f"{b}: {type(ex).__name__}: {str(ex)[:300]}\n{traceback.format_exc()[-1500:]}\n")
        log(f"FEHLER {b}")
        return b, "error"


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    for d in ("items", "responses", "stats"):
        os.makedirs(OUT + d, exist_ok=True)
    cat = pd.read_parquet(META + "catalog.parquet").sort_values("folder").reset_index(drop=True)
    cat["b_code"] = np.arange(len(cat), dtype=np.int16)
    s_off = offsets(cat, "rows_subjects")
    i_off = offsets(cat, "rows_items")
    # globale Tabellen (klein) einmalig
    if not os.path.exists(OUT + "benchmarks.parquet"):
        c2 = cat.copy()
        c2["direction"] = c2.response_scale.map(lambda x: json.loads(x).get("direction"))
        c2["scale_kind"] = c2.response_scale.map(lambda x: json.loads(x).get("kind"))
        c2["seen_by_baseline_script"] = c2.folder <= "helm_afr"
        c2["s_code_offset"] = c2.folder.map(s_off)
        c2["i_code_offset"] = c2.folder.map(i_off)
        c2.to_parquet(OUT + "benchmarks.parquet")
    if not os.path.exists(OUT + "subjects.parquet"):
        parts = []
        for b in cat.folder:
            t = pq.read_table(CACHE + f"{b}/subjects.parquet").to_pandas()
            t.insert(0, "benchmark_id", b)
            t.insert(0, "s_code", np.arange(s_off[b], s_off[b] + len(t), dtype=np.int32))
            parts.append(t)
        pd.concat(parts, ignore_index=True).to_parquet(OUT + "subjects.parquet")
    jobs = []
    for _, r in cat.iterrows():
        if only and r.folder not in only:
            continue
        jobs.append((r.folder, int(r.b_code), s_off[r.folder], i_off[r.folder],
                     {"items": int(r.rows_items), "responses": int(r.rows_responses)}, r.response_type == "binary"))
    # große zuerst, damit sie nicht am Ende allein laufen
    jobs.sort(key=lambda j: -(j[4]["responses"] + j[4]["items"]))
    log(f"start {len(jobs)} jobs, workers={nw}")
    res = {"ok": 0, "skip": 0, "error": 0}
    with cf.ThreadPoolExecutor(nw) as ex:
        for b, stt in ex.map(job, jobs):
            res[stt] += 1
    log(f"ende {res}")
    print(res)


if __name__ == "__main__":
    main()
