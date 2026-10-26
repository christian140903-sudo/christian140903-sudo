"""agg_split.py (P4) — teilt PAIEC_WORK/modell/agg.parquet streaming in je-Benchmark-Dateien agg_je_b/b<code>.parquet.
agg.parquet ist nach b_code monoton (geprüft) -> Zeilen eines Benchmarks sind zusammenhängend; Reihenfolge und dtypes
bleiben erhalten. Prüft am Ende: Summe der Zeilen = Zeilen der Quelle (fail-closed, rc 3)."""
import os, sys
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

W = Path(os.environ["PAIEC_WORK"]) / "modell"
ziel = W / "agg_je_b"
ziel.mkdir(exist_ok=True)
pf = pq.ParquetFile(W / "agg.parquet")
n_quelle = pf.metadata.num_rows
puffer, aktuell, n_out, dateien = [], None, 0, 0


def schreibe():
    global puffer, n_out, dateien
    if not puffer:
        return
    t = pa.concat_tables(puffer)
    pq.write_table(t, ziel / f"b{aktuell}.parquet")
    n_out += t.num_rows
    dateien += 1
    puffer = []


for batch in pf.iter_batches(batch_size=1_000_000):
    t = pa.Table.from_batches([batch])
    b = t["b_code"].to_numpy()
    start = 0
    for i in range(1, len(b) + 1):
        if i == len(b) or b[i] != b[start]:
            code = int(b[start])
            if aktuell is not None and code != aktuell:
                schreibe()
            aktuell = code
            puffer.append(t.slice(start, i - start))
            start = i
schreibe()
print(f"Quelle {n_quelle} Zeilen, geschrieben {n_out} Zeilen in {dateien} Dateien")
sys.exit(0 if n_out == n_quelle else 3)
