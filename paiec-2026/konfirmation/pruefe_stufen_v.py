"""pruefe_stufen_v.py — mechanische Prüfung der Phase-2-Läufe für v2.0-core (cv_K_A2v/cv_K_B2v):
(1) status.json fertig == 10, platt_stufen == ''; (2) je Falte: im log.txt benutzte Platt-Stufenmenge == verschachtelt_je_falte der
kern-Auswertung (cv_K_Av/cv_K_Bv auswertung.json); (3) Sätze je Falte: in Falten, deren Menge == {0,1,3,7}, sind hier_item/hier_kal
bitgleich zum Lauf mit erzwungenen Stufen {0,1,3,7} (cv_K_*2p); in anderen Falten ungleich. Baselines in allen Falten bitgleich.
rc 0 nur, wenn alles zutrifft (fail-closed). Aufruf: python3 -I pruefe_stufen_v.py A|B
"""
import json, os, sys
from pathlib import Path
import pandas as pd

W = Path(os.environ["PAIEC_WORK"]) / "modell"
d = sys.argv[1]
v, p1v = W / f"cv_K_{d}2v", W / f"cv_K_{d}v"
p = W / f"cv_K_{d}2p"
st = json.loads((v / "status.json").read_text())
ok = st["fertig"] == 10 and st["platt_stufen"] == ""
print("status:", st, "ok" if ok else "FEHLT")
soll = json.loads((p1v / "auswertung.json").read_text())["platt_stufenwahl_verschachtelt"]["verschachtelt_je_falte"]
ist = {}
for l in (v / "log.txt").read_text().splitlines():
    if "Platt-Stufen" in l and "Falte " in l:
        f = l.split("Falte ")[1].split(":")[0]
        ist[f] = sorted(int(x) for x in l.split("Platt-Stufen ")[1].strip().split(","))
gleich = all(sorted(soll[str(f)]) == ist.get(str(f)) for f in range(10))
ok &= gleich
print("Stufenmenge je Falte log == kern-Auswertung:", gleich, ist)
keys = ["saat", "S", "praediktor", "budget", "b_code", "s_code"]
res = {}
for f in range(10):
    a = pd.read_parquet(v / f"saetze_f{f}.parquet"); b = pd.read_parquet(p / f"saetze_f{f}.parquet")
    m = a.merge(b, on=keys, suffixes=("_v", "_p"))
    assert len(m) == len(a) == len(b), (f, len(m), len(a), len(b))
    dq = (m.q_v - m.q_p).abs()
    base = dq[~m.praediktor.str.startswith("hier")].max()
    hier = dq[m.praediktor.str.startswith("hier")].max()
    erwartet_gleich = sorted(soll[str(f)]) == [0, 1, 3, 7]
    passt = (base == 0) and ((hier == 0) if erwartet_gleich else (hier > 0))
    ok &= passt
    res[f] = {"stufen": soll[str(f)], "max_dq_baselines": float(base), "max_dq_hier": float(hier), "erwartet_gleich_2p": erwartet_gleich, "passt": bool(passt)}
    print(f"Falte {f}: {res[f]}")
out = {"design": d, "status": st, "stufen_log": ist, "stufen_soll": soll, "falten": res, "ok": bool(ok)}
Path(__file__).resolve().parent.joinpath("ergebnisse", f"pruefe_stufen_{d}2v.json").write_text(json.dumps(out, indent=1))
print("GESAMT", "ok" if ok else "VERFEHLT")
sys.exit(0 if ok else 1)
