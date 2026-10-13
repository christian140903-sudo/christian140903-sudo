"""Gaia-DR3-XP-Koeffizienten fuer eine feste Liste von source_ids aus dem ESA-CDN herausfiltern (Streaming) und daraus
auf dem Runner synthetische Photometrie im System Hipparcos_Tycho (Hp, BT, VT) mit GaiaXPy rechnen.

Zweck: Linse W3 (graues Verblassen 1991 -> 2016, Hipparcos-Hp gegen XP-synthetisches Hp). Das Gaia-Archiv (DataLink)
liefert vor DR4 nur ~8 s/Quelle; das CDN liefert ganze HEALPix-Bloecke. Kein Befund an sich: Rohdaten fuer W3.

Ablauf je Shard:
  1. Liste aller CDN-Dateien des Datensatzes (S3-kompatible Liste gaia.eu-1.cdn77-storage.com, paginiert).
  2. Ziel-IDs -> HEALPix-8-Index (source_id // 2**35 // 4**4) -> nur Dateien, deren Bereich Ziel-IDs enthaelt.
     Diese Dateien werden auf die Shards verteilt (files[shard::nshards]).
  3. Jede Datei wird gestreamt und on-the-fly entpackt; Zeilen, deren source_id in der Zielmenge liegt, werden
     behalten. Sind die Zeilen aufsteigend sortiert (wird laufend geprueft), bricht der Download nach der groessten
     Ziel-ID der Datei ab (spart im Mittel ~40 % der Bytes).
  4. continuous + photometry=True: GaiaXPy 2.1.4 generate(..., Hipparcos_Tycho) auf den gefundenen Zeilen.

Ausgaben (OUT):
  xpphot_<shard>.csv   synthetische Photometrie (klein; wird von merge.py zusammengefuehrt)
  xpfound_<shard>.csv  je Ziel-ID in den Shard-Dateien: gefunden ja/nein, Datei
  xpraw_<shard>.csv.gz Rohzeilen inkl. Kopfzeilen (nur im Actions-Artefakt; merge.py fasst *.csv.gz nicht an)

args:
  ids_file     Pfad (relativ zu ts-compute/) einer Textdatei mit einer source_id je Zeile (Pflicht)
  dataset      "continuous" (Standard) oder "sampled"
  photometry   bool, Standard True (nur bei continuous)
  threads      parallele Dateien je Shard, Standard 4
  max_files    int, optional, nur fuer Tests
  only_file    Dateiname, optional, nur fuer Tests (eine bestimmte Datei)
  early_stop   bool, Standard True; Abbruch nach der groessten Ziel-ID (setzt aufsteigende Sortierung voraus; im
               lokalen Test 2026-10-12 an einer ganz gelesenen Datei geprueft, siehe BERICHT-W3 §7)

Was tut die Schicht darunter im Fehlerfall schon selbst? requests wiederholt nichts; deshalb hier 4 Versuche mit
Backoff je Datei. Eine Datei, die nach 4 Versuchen scheitert, wird in meta.errors gezaehlt und ihre Ziel-IDs stehen in
xpfound mit found=0, reason=download_failed (fail-closed: fehlend heisst unbekannt, nie "kein Spektrum").
GaiaXPy wird bei Bedarf zur Laufzeit in fester Version installiert (requirements.txt der anderen Jobs bleibt unberuehrt).
"""
import csv, gzip, io, os, re, subprocess, sys, tempfile, time, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

LIST_URL = 'https://gaia.eu-1.cdn77-storage.com/?prefix=Gaia/gdr3/Spectroscopy/{d}/&delimiter=/'
CDN = 'https://cdn.gea.esac.esa.int/'
DIRS = {'continuous': 'xp_continuous_mean_spectrum', 'sampled': 'xp_sampled_mean_spectrum'}
HPX8 = 2 ** 35 * 4 ** 4
GAIAXPY_VERSION = '2.1.4'


def list_files(dataset):
    d = DIRS[dataset]
    files, marker = [], None
    for _ in range(50):
        url = LIST_URL.format(d=d) + (f'&marker={marker}' if marker else '')
        x = requests.get(url, timeout=120).text
        keys = re.findall(r'<Key>([^<]+)</Key>', x)
        files += [k for k in keys if k.endswith('.csv.gz')]
        if '<IsTruncated>true</IsTruncated>' not in x or not keys:
            break
        marker = keys[-1]
    out = []
    for k in files:
        a, b = re.search(r'_(\d+)-(\d+)\.csv\.gz$', k).groups()
        out.append((int(a), int(b), k))
    return sorted(out)


def assign(ids, files):
    """Ziel-IDs den Dateien zuordnen (HEALPix-8-Bereich im Dateinamen)."""
    import bisect
    starts = [f[0] for f in files]
    per = {}
    for sid in ids:
        h = sid // HPX8
        i = bisect.bisect_right(starts, h) - 1
        if i >= 0 and files[i][0] <= h <= files[i][1]:
            per.setdefault(files[i][2], set()).add(sid)
    return per


def stream_filter(key, targets, early_stop=True, tries=4):
    """Datei streamen, Zeilen mit Ziel-IDs behalten. Rueckgabe: (kopfzeilen, treffer, bytes, early, sortiert)."""
    last_exc = None
    for attempt in range(tries):
        try:
            return _stream_once(key, targets, early_stop)
        except Exception as exc:  # Netzfehler: erneut versuchen
            last_exc = exc
            time.sleep(2 ** (attempt + 1))
    raise last_exc


def _stream_once(key, targets, early_stop):
    maxid = max(targets)
    header, hits = [], []
    nbytes, early, sorted_ok, prev = 0, False, True, -1
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf = b''
    with requests.get(CDN + key, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1 << 20):
            nbytes += len(chunk)
            buf += d.decompress(chunk)
            lines = buf.split(b'\n')
            buf = lines.pop()
            stop = False
            for ln in lines:
                if not ln:
                    continue
                c0 = ln[:1]
                if c0 == b'#' or c0 == b's':          # ECSV-Kommentar oder Spaltenkopf (source_id,...)
                    if not hits:
                        header.append(ln)
                    continue
                j = ln.find(b',')
                try:
                    sid = int(ln[:j])
                except ValueError:
                    continue
                if sid < prev:
                    sorted_ok = False
                prev = sid
                if sid in targets:
                    hits.append(ln)
                if early_stop and sorted_ok and sid > maxid:
                    stop = True
                    break
            if stop:
                early = True
                break
    return header, hits, nbytes, early, sorted_ok


def ensure_gaiaxpy():
    try:
        import gaiaxpy  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', f'gaiaxpy=={GAIAXPY_VERSION}'])


def photometry(header, rows):
    """GaiaXPy auf den Rohzeilen (ueber eine temporaere Datei im Originalformat, damit GaiaXPys Parser greift)."""
    ensure_gaiaxpy()
    from gaiaxpy import generate, PhotometricSystem
    is_ecsv = any(h.startswith(b'# %ECSV') for h in header)
    suffix = '.ecsv' if is_ecsv else '.csv'
    with tempfile.NamedTemporaryFile('wb', suffix=suffix, delete=False) as f:
        f.write(b'\n'.join(header + rows) + b'\n')
        path = f.name
    try:
        ph = generate(path, photometric_system=PhotometricSystem.Hipparcos_Tycho, save_file=False)
    finally:
        os.unlink(path)
    return ph


def run(args, shard, nshards, out):
    dataset = args.get('dataset', 'continuous')
    want_phot = bool(args.get('photometry', True)) and dataset == 'continuous'
    threads = int(args.get('threads', 4))
    early_stop = bool(args.get('early_stop', True))
    ids = [int(x) for x in open(args['ids_file']).read().split() if x.strip()]
    files = list_files(dataset)
    per = assign(ids, files)
    keys = sorted(per)
    if args.get('only_file'):
        keys = [k for k in keys if k.endswith(args['only_file'])]
    if args.get('only_files'):  # Nachlauf: nur diese Dateinamen (z. B. abgebrochene Downloads)
        wanted = set(args['only_files'])
        keys = [k for k in keys if k.rsplit('/', 1)[-1] in wanted]
    keys = keys[shard::nshards]
    if args.get('max_files'):
        keys = keys[:int(args['max_files'])]
    t0 = time.time()
    header_all, rows_all, found, errors = None, [], {}, []
    nbytes = n_early = n_fail = n_unsorted = 0
    with ThreadPoolExecutor(threads) as pool:
        tries = int(args.get('tries', 4))
        futs = {pool.submit(stream_filter, k, per[k], early_stop, tries): k for k in keys}
        for fut in as_completed(futs):
            k = futs[fut]
            try:
                header, hits, nb, early, srt = fut.result()
            except Exception as exc:
                n_fail += 1
                if len(errors) < 10:
                    errors.append(f'{k.rsplit("/", 1)[-1]}: {exc!r}'[:200])
                for sid in per[k]:
                    found[sid] = (0, k.rsplit('/', 1)[-1], 'download_failed')
                continue
            nbytes += nb
            n_early += int(early)
            n_unsorted += int(not srt)
            if header_all is None and header:
                header_all = header
            rows_all += hits
            got = {int(h[:h.find(b',')]) for h in hits}
            for sid in per[k]:
                found[sid] = (int(sid in got), k.rsplit('/', 1)[-1], '' if sid in got else 'not_in_file')
    with open(os.path.join(out, f'xpfound_{shard:04d}.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['source_id', 'found', 'file', 'reason'])
        for sid, (ok, fn, why) in sorted(found.items()):
            w.writerow([sid, ok, fn, why])
    if rows_all:
        with gzip.open(os.path.join(out, f'xpraw_{shard:04d}.csv.gz'), 'wb') as f:
            f.write(b'\n'.join((header_all or []) + rows_all) + b'\n')
    n_phot = 0
    phot_err = None
    if want_phot and rows_all:
        try:
            ph = photometry(header_all or [], rows_all)
            ph.to_csv(os.path.join(out, f'xpphot_{shard:04d}.csv'), index=False)
            n_phot = len(ph)
        except Exception as exc:  # Photometrie-Fehler melden, Rohzeilen bleiben im Artefakt
            phot_err = repr(exc)[:300]
    dt = time.time() - t0
    return dict(job='gaia_xp_extract', dataset=dataset, n_ids=len(ids), n_files_total=len(files),
                n_files_needed=len(per), n_files_shard=len(keys), n_targets_shard=sum(len(per[k]) for k in keys),
                n_found=len(rows_all), n_phot=n_phot, phot_error=phot_err, n_fail=n_fail, n_early_stop=n_early, n_unsorted=n_unsorted,
                gbytes=round(nbytes / 1e9, 3), mbytes_per_s=round(nbytes / 1e6 / dt, 1) if dt else None, errors=errors)
