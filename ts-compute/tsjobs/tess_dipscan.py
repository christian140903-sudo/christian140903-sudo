"""Sektorweiter Scan von TESS-SPOC-Lichtkurven (2 min) nach einzelnen, aperiodischen Einbrüchen.

Pro Lichtkurve: Rauschmaß und alle signifikanten Einbrüche, definiert als mindestens
`min_run` aufeinanderfolgende Kadenzen unter -k·σ nach Entfernen langsamer Trends
(gleitender Median). Ergebnis ist eine Rohliste für die Suche nach HD-139139-artigen
"Zufalls-Transitern"; zeitgleiche Ereignisse in vielen Sternen derselben Kamera
werden später als Systematik verworfen. Kein Befund an sich.

args: sector (int), k (float, Standard 4), min_run (int, Standard 3),
      window (int Kadenzen, Standard 361 ≈ 12 h), threads (int, Standard 16),
      max_files (int, optional, für Tests)
"""
import csv, io, os, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from astropy.io import fits
from scipy.ndimage import median_filter

LIST_URL = 'https://archive.stsci.edu/missions/tess/download_scripts/sector/tesscurl_sector_{s}_lc.sh'
STAR_COLS = ['tic', 'sector', 'camera', 'ccd', 'tmag', 'teff', 'ra', 'dec', 'n_good',
             'sigma_ppm', 'rms_1h_ppm', 'n_events', 'max_depth_ppm', 'max_snr']
EVENT_COLS = ['tic', 'sector', 'camera', 'ccd', 't_mid_btjd', 'dur_h', 'n_cad',
              'depth_ppm', 'snr']


def urls_for_sector(sector):
    txt = requests.get(LIST_URL.format(s=sector), timeout=120).text
    return sorted(set(re.findall(r'https://\S+?_lc\.fits', txt)))


def find_events(t, r, sigma, k, min_run, max_events=20):
    """Zusammenhängende Läufe r < -k·σ (Lücken ≤ 2 Kadenzen werden überbrückt)."""
    below = r < -k * sigma
    idx = np.flatnonzero(below)
    if idx.size == 0:
        return []
    splits = np.flatnonzero(np.diff(idx) > 3) + 1
    events = []
    for run in np.split(idx, splits):
        if run.size < min_run:
            continue
        seg = r[run[0]:run[-1] + 1]
        depth = -float(np.median(seg))
        snr = depth / sigma * np.sqrt(seg.size)
        events.append((float(0.5 * (t[run[0]] + t[run[-1]])),
                       float((t[run[-1]] - t[run[0]]) * 24 + 2 / 60), int(seg.size),
                       depth * 1e6, float(snr)))
    events.sort(key=lambda e: -e[4])
    return events[:max_events]


def process(url, k, min_run, window):
    raw = requests.get(url, timeout=120).content
    with fits.open(io.BytesIO(raw), memmap=False) as hd:
        h0 = hd[0].header
        d = hd[1].data
        t = np.asarray(d['TIME'], float)
        f = np.asarray(d['PDCSAP_FLUX'], float)
        q = np.asarray(d['QUALITY'])
    ok = np.isfinite(t) & np.isfinite(f) & (q == 0)
    t, f = t[ok], f[ok]
    meta = dict(tic=h0.get('TICID'), sector=h0.get('SECTOR'), camera=h0.get('CAMERA'),
                ccd=h0.get('CCD'), tmag=h0.get('TESSMAG'), teff=h0.get('TEFF'),
                ra=h0.get('RA_OBJ'), dec=h0.get('DEC_OBJ'), n_good=int(t.size))
    if t.size < 2 * window:
        return meta | dict(sigma_ppm=None, rms_1h_ppm=None, n_events=0,
                           max_depth_ppm=None, max_snr=None), [], len(raw)
    f = f / np.median(f)
    r = f - median_filter(f, size=window, mode='nearest')
    sigma = 1.4826 * float(np.median(np.abs(r - np.median(r))))
    nb = r.size // 30
    rms_1h = float(np.std(r[:nb * 30].reshape(nb, 30).mean(axis=1)))
    ev = find_events(t, r, sigma, k, min_run)
    meta |= dict(sigma_ppm=sigma * 1e6, rms_1h_ppm=rms_1h * 1e6, n_events=len(ev),
                 max_depth_ppm=max((e[3] for e in ev), default=None),
                 max_snr=max((e[4] for e in ev), default=None))
    rows = [[meta['tic'], meta['sector'], meta['camera'], meta['ccd'], *e] for e in ev]
    return meta, rows, len(raw)


def run(args, shard, nshards, out):
    sector = int(args['sector'])
    k, min_run = float(args.get('k', 4.0)), int(args.get('min_run', 3))
    window, threads = int(args.get('window', 361)), int(args.get('threads', 16))
    urls = urls_for_sector(sector)
    n_total = len(urls)
    urls = urls[shard::nshards]
    if args.get('max_files'):
        urls = urls[:int(args['max_files'])]
    t0 = time.time()
    n_ok = n_fail = nbytes = 0
    errors = []
    star_path = os.path.join(out, f'stars_{shard:04d}.csv')
    event_path = os.path.join(out, f'events_{shard:04d}.csv')
    with open(star_path, 'w', newline='') as fs, open(event_path, 'w', newline='') as fe, \
            ThreadPoolExecutor(threads) as pool:
        ws, we = csv.writer(fs), csv.writer(fe)
        ws.writerow(STAR_COLS)
        we.writerow(EVENT_COLS)
        futs = {pool.submit(process, u, k, min_run, window): u for u in urls}
        for fut in as_completed(futs):
            try:
                meta, rows, nb = fut.result()
            except Exception as exc:  # Einzelfehler zählen, Lauf nicht abbrechen
                n_fail += 1
                if len(errors) < 5:
                    errors.append(f'{futs[fut].rsplit("/", 1)[-1]}: {exc!r}'[:200])
                continue
            n_ok += 1
            nbytes += nb
            ws.writerow([meta[c] for c in STAR_COLS])
            we.writerows(rows)
    dt = time.time() - t0
    return dict(job='tess_dipscan', sector=sector, n_sector=n_total, n_shard=len(urls),
                n_ok=n_ok, n_fail=n_fail, mbytes=round(nbytes / 1e6, 1),
                files_per_s=round(n_ok / dt, 2) if dt else None, errors=errors)
