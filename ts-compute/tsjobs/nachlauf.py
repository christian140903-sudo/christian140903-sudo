"""Nachlauf-Regel W1 (vor dem Nachlauf festgelegt, prereg/COMMITMENTS.md): welche Shards eines Laufs werden
nachgerechnet, und wie werden Erstlauf und Nachlauf zusammengeführt. Liest nur Ausführungs-Metadaten (Job-Status
und -Zeiten; aus shards_meta.json nur shard, pool_timeouts, shard_deadline und die Form der errors-Einträge), nie
Detektionen; gibt nur Shard-Nummern, Gründe und Zählungen aus.

  liste     python -m tsjobs.nachlauf liste --jobs JOBS.json --nshards N [--metas shards_meta.json] [--limit-min 120]
            JOBS.json = Ausgabe von `gh api repos/<o>/<r>/actions/runs/<id>/jobs --paginate` (eine oder mehrere
            Seiten hintereinander). Bricht ab, solange ein work-Job nicht beendet ist: die Liste entsteht erst nach
            dem Ende des Laufs, mechanisch, vor jedem Blick auf Ergebnisse.
  zusammen  python -m tsjobs.nachlauf zusammen ERST NACH OUT
            ERST, NACH = runs/<id>-Ordner aus ts-results (merge.py-Ausgabe + job.json); NACH ist mit only_shards
            gelaufen. Je Shard genau EINE Quelle: Shards aus NACH.only_shards kommen vollständig aus NACH (nie
            petalweise gemischt), alle übrigen aus ERST. Ein nachgerechneter Shard ohne meta in NACH fällt ganz weg
            (keine Zeile aus ERST, keine aus NACH). spectragg.csv hat keine Kachel-Spalte und wird weggelassen
            (welleA_eval.py liest sie nicht).

Regel `liste`: Shard s wird genau einmal nachgerechnet, wenn
  J1  kein work-Job 'work (s)' existiert oder seine conclusion nicht 'success' ist;
  J2  sein work-Job länger als --limit-min (120) lief, auch bei success (unter dem 120-min-Limit des Wächter-Codes
      wäre er abgebrochen oder ein Teil-Shard gewesen);
  M1  (--metas) seine meta fehlt, obwohl der Job success meldet;
  M2  (--metas) seine meta pool_timeouts oder shard_deadline enthält (Teil-Shard: ein Pass-1-Ausfall ändert die
      Bibliothek und damit alle Zeilen des Shards, ein Pass-3-Ausfall macht bekannte Artefakte zu ungeprüften
      Überlebenden);
  M3  (--metas) meta.errors mindestens einen Pass-2-Eintrag 'p_<tile>_<petal>.npz: …' enthält (Code-Fassung
      8493efd5… führt solche Petals als ok im Nenner; meta.errors ist auf 5 gekappt, darum der ganze Shard).
Petals mit gewöhnlichem Pass-1-Fehler (fail mit Netz-/HTTP-Fehler, wie in allen früheren Läufen) lösen nichts aus.
Das Ergebnis des Nachlaufs ersetzt die Erstfassung vollständig, unabhängig von seinem Inhalt, auch wenn es selbst
wieder Teil-Shard ist (dann zählen dessen Petals/Kandidaten fail-closed); es gibt keinen zweiten Nachlauf.
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, sys

P2_ERR = re.compile(r'^p_\d+_\d+\.npz: ')
# Betriebsknöpfe ohne Wirkung auf die Ausgaben eines fehlerfreien Laufs (dürfen sich in ERST und NACH unterscheiden)
OPS_ARGS = {'pool_timeout_s', 'pool_timeout_s_pass1', 'pool_timeout_s_lib', 'pool_timeout_s_pass2',
            'pool_timeout_s_pass3', 'shard_deadline_s', 'heartbeat_s', 'workers', 'threads'}
WORK = re.compile(r'^work \((\d+)\)$')
TILES_SHA = '2039434085b74c26126a01899766a7bc93a739d9e59a4f081645b8337c85a61c'   # ts-compute/meta/tiles-iron.csv


def _json_stream(path):
    """Eine oder mehrere JSON-Dokumente hintereinander (gh api --paginate) -> Liste der Dokumente."""
    txt, dec, docs, k = open(path, encoding='utf-8').read(), json.JSONDecoder(), [], 0
    while True:
        while k < len(txt) and txt[k].isspace():
            k += 1
        if k >= len(txt):
            return docs
        d, k = dec.raw_decode(txt, k)
        docs.extend(d if isinstance(d, list) else [d])


def _ts(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


def liste(jobs_path, nshards, metas_path=None, limit_min=120.0):
    jobs = []
    for d in _json_stream(jobs_path):
        jobs.extend(d.get('jobs', []) if isinstance(d, dict) else [])
    work = {}
    for j in jobs:
        m = WORK.match(str(j.get('name', '')))
        if not m:
            continue
        s = int(m.group(1))
        if s in work:
            raise SystemExit(f'Job work ({s}) doppelt in {jobs_path} (nur den letzten Versuch übergeben)')
        work[s] = j
    open_ = sorted(s for s, j in work.items() if j.get('status') != 'completed')
    if open_:
        raise SystemExit(f'Lauf nicht beendet: work-Jobs {open_} nicht completed -> Liste erst nach Laufende')
    if any(s < 0 or s >= nshards for s in work):
        raise SystemExit(f'Shard-Nummern außerhalb 0..{nshards - 1}: {sorted(work)}')
    why = {}
    for s in range(nshards):
        j = work.get(s)
        if j is None:
            why.setdefault(s, []).append('J1:kein_job')
            continue
        if j.get('conclusion') != 'success':
            why.setdefault(s, []).append(f"J1:{j.get('conclusion')}")
        if j.get('started_at') and j.get('completed_at'):
            mins = (_ts(j['completed_at']) - _ts(j['started_at'])).total_seconds() / 60
            if mins > limit_min:
                why.setdefault(s, []).append(f'J2:{mins:.0f}min')
        else:
            why.setdefault(s, []).append('J2:zeit_fehlt')
    n_meta = None
    if metas_path:
        metas = json.load(open(metas_path, encoding='utf-8'))
        by = {}
        for m in metas:
            by.setdefault(int(m['shard']), []).append(m)
        n_meta = len(metas)
        for s in range(nshards):
            ms = by.get(s, [])
            if len(ms) > 1:
                why.setdefault(s, []).append('M0:meta_doppelt')
            if not ms:
                if work.get(s) is not None and work[s].get('conclusion') == 'success':
                    why.setdefault(s, []).append('M1:meta_fehlt')
                continue
            m = ms[0]
            if m.get('pool_timeouts') or m.get('shard_deadline'):
                why.setdefault(s, []).append('M2:teil_shard')
            n2 = sum(1 for e in (m.get('errors') or []) if P2_ERR.match(str(e)))
            if n2:
                why.setdefault(s, []).append(f'M3:pass2_fehler={n2}')
    out = dict(only_shards=sorted(why), gruende={str(s): why[s] for s in sorted(why)}, n_work_jobs=len(work),
               nshards=nshards, limit_min=limit_min, metas_geprueft=metas_path is not None, n_metas=n_meta)
    if not metas_path:
        out['hinweis'] = 'M1-M3 nicht geprüft (ohne --metas); die Regel verlangt sie vor dem Nachlauf'
    return out


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _rows(p):
    with open(p, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        head = next(r, None)
        return head, list(r)


def zusammen(erst, nach, out):
    jE = json.load(open(os.path.join(erst, 'job.json'), encoding='utf-8'))
    jN = json.load(open(os.path.join(nach, 'job.json'), encoding='utf-8'))
    def strip(j):
        j = {k: v for k, v in j.items() if k not in ('only_shards', 'note')}
        j['args'] = {k: v for k, v in j.get('args', {}).items() if k not in OPS_ARGS}
        return json.dumps(j, sort_keys=True)
    if strip(jE) != strip(jN):
        raise SystemExit('job.json von ERST und NACH unterscheiden sich außer only_shards/note/Betriebsknöpfen '
                         '-> nicht zusammenführbar')
    R = jN.get('only_shards')
    if not isinstance(R, list) or not R or any(type(s) is not int for s in R):
        raise SystemExit(f'NACH ohne gültige only_shards: {R!r}')
    R, n = set(R), int(jE['nshards'])
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from tsjobs.desi_laser import tile_list, META
    tab = os.path.join(META, 'tiles-iron.csv')   # Shard-Zuordnung hängt an dieser Tabelle (COMMITMENTS: 2039434…)
    if _sha(tab) != TILES_SHA:
        raise SystemExit(f'{tab}: SHA-256 {_sha(tab)[:16]}… ist nicht die verpflichtete Kacheltabelle')
    tiles = tile_list(jE['args'])
    shard_of = {t['tile']: s for s in range(n) for t in tiles[s::n]}
    mE = json.load(open(os.path.join(erst, 'shards_meta.json'), encoding='utf-8'))
    mN = json.load(open(os.path.join(nach, 'shards_meta.json'), encoding='utf-8'))
    if any(int(m['shard']) not in R for m in mN):
        raise SystemExit('NACH enthält meta für Shards außerhalb only_shards')
    got = [int(m['shard']) for m in mN]
    if len(got) != len(set(got)):
        raise SystemExit('NACH enthält doppelte meta')
    delivered = set(got)
    metas = sorted([m for m in mE if int(m['shard']) not in R] + mN, key=lambda m: int(m['shard']))
    os.makedirs(out, exist_ok=True)
    info = dict(erst=os.path.abspath(erst), nach=os.path.abspath(nach), ersetzt=sorted(R),
                geliefert=sorted(delivered), ohne_ausgabe=sorted(R - delivered), dateien={}, weggelassen=[],
                tiles_iron_sha256=TILES_SHA, sha256_eingang={})
    names = sorted({os.path.basename(p) for d in (erst, nach) for p in glob.glob(os.path.join(d, '*.csv'))})
    for name in names:
        pE, pN = os.path.join(erst, name), os.path.join(nach, name)
        hE, rE = _rows(pE) if os.path.exists(pE) else (None, [])
        hN, rN = _rows(pN) if os.path.exists(pN) else (None, [])
        for p in (pE, pN):
            if os.path.exists(p):
                info['sha256_eingang'][p] = _sha(p)
        head = hE or hN
        if not head or 'tile' not in head:
            info['weggelassen'].append(name)
            continue
        if hE and hN and hE != hN:
            raise SystemExit(f'{name}: Kopfzeilen von ERST und NACH verschieden')
        it = head.index('tile')

        def sh(r, src):
            t = int(float(r[it]))
            if t not in shard_of:
                raise SystemExit(f'{name} ({src}): Kachel {t} gehört zu keinem Shard dieses Jobs')
            return shard_of[t]
        keepE = [r for r in rE if sh(r, 'ERST') not in R]
        bad = sorted({sh(r, 'NACH') for r in rN} - R)
        if bad:
            raise SystemExit(f'{name}: NACH enthält Zeilen der nicht nachgerechneten Shards {bad}')
        keepN = [r for r in rN if sh(r, 'NACH') in delivered]
        with open(os.path.join(out, name), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(head)
            w.writerows(keepE)
            w.writerows(keepN)
        info['dateien'][name] = dict(aus_erst=len(keepE), aus_nach=len(keepN), erst_verworfen=len(rE) - len(keepE),
                                     nach_ohne_meta_verworfen=len(rN) - len(keepN))
    json.dump(metas, open(os.path.join(out, 'shards_meta.json'), 'w', encoding='utf-8'), indent=1)
    aborts = []
    for d, keep in ((erst, lambda s: s not in R), (nach, lambda s: s in R)):
        p = os.path.join(d, 'shards_abort.json')
        if os.path.exists(p):
            aborts += [a for a in json.load(open(p, encoding='utf-8')) if keep(int(a.get('shard', -1)))]
    if aborts:
        json.dump(aborts, open(os.path.join(out, 'shards_abort.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(jE, open(os.path.join(out, 'job.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(info, open(os.path.join(out, 'nachlauf.json'), 'w', encoding='utf-8'), indent=1)
    return {k: v for k, v in info.items() if k != 'sha256_eingang'}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    a1 = sub.add_parser('liste')
    a1.add_argument('--jobs', required=True)
    a1.add_argument('--nshards', type=int, required=True)
    a1.add_argument('--metas')
    a1.add_argument('--limit-min', type=float, default=120.0)
    a2 = sub.add_parser('zusammen')
    a2.add_argument('erst')
    a2.add_argument('nach')
    a2.add_argument('out')
    a = ap.parse_args()
    if a.cmd == 'liste':
        print(json.dumps(liste(a.jobs, a.nshards, a.metas, a.limit_min), ensure_ascii=False))
    else:
        print(json.dumps(zusammen(a.erst, a.nach, a.out), ensure_ascii=False))


if __name__ == '__main__':
    main()
