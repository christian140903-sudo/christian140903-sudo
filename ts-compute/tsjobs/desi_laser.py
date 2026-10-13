"""W1: Suche nach unaufgelösten Emissionslinien (optische Laser) in DESI-DR1-Sternspektren.

Einheit: Kachel-Petal-Coadd (ein Spektrograph, 500 Fasern inkl. Himmelsfasern), per HTTP-Range nur
FIBERMAP, EXP_FIBERMAP, FLUX/IVAR/MASK (b, r, z) und wenige RESOLUTION-Zeilen. Ablauf je Shard:

  Pass 1  Laden + Reduzieren je Petal (Sterne/Himmelsfasern als Arrays auf Platte, übrige Fasern nur als
          Bitkarte "S/N > 4"), Kontinuum-Normierung.
  Biblio  Sterne hoher S/N des Shards, PCA-Vorauswahl.
  Pass 2  Je Stern: K beste Nachbarn (exaktes chi2 nach Verschiebung ins Beobachtungsgitter des Sterns),
          Referenz = Median, lokale Regression gegen Tiefen-/RV-/LSF-Fehlpassung, LSF-Matched-Filter,
          Detektionen >= t_pre mit Merkmalen; Injektion unaufgelöster Linien durch dieselbe Kette;
          Himmelsfasern durch denselben Detektor (Null ohne Stern); Faser-übergreifende Zählung.

Was die Schicht darunter im Fehlerfall selbst tut: requests wiederholt nicht von selbst -> eigene Retries
(3x, Backoff); der DESI-Server liefert bei falschem Range HTTP 416 -> Petal wird als Fehler gezählt, Lauf
läuft weiter (fail-closed: fehlende Petals erscheinen in meta.n_fail, nie als 0 Detektionen).

Ausgaben (CSV je Shard; Rohliste, kein Befund):
  detections_<s>.csv  alle Detektionen (kind = real | inj | sky) mit Merkmalen
  injections_<s>.csv  jede Injektion (auch nicht gefundene)
  spectra_<s>.csv     je Sternspektrum (mode full) bzw. Aggregat (mode agg)
  skyfibers_<s>.csv   je Himmelsfaser (Nenner der Himmelsfaser-Null)
  petals_<s>.csv      je Petal: Status, Zählungen

args: survey ('main'), program ('bright' oder Liste), tiles (Liste TILEID, optional), max_tiles, seed,
      t_pre (5.0), k_nn (25), m_pre (60), lib_snr (15), lib_max (30000), inj_frac (1.0),
      rows ('all'|'select'), cache (Pfad, optional, Pass-1-Cache), workers (4), threads (8),
      table ('full'|'agg'), tune_frac (0.3)
"""
import csv, hashlib, io, json, os, re, shutil, time, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from astropy.io import fits

BASE = 'https://data.desi.lbl.gov/public/dr1/spectro/redux/iron'
CAMS = ('B', 'R', 'Z')
NPIX = {'B': 2751, 'R': 2326, 'Z': 2881}
W0 = {'B': 3600.0, 'R': 5760.0, 'Z': 7520.0}
DW = 0.8
OFF = {'B': 0, 'R': 2751, 'Z': 2751 + 2326}
NTOT = 2751 + 2326 + 2881
C_KMS = 299792.458
KPNO = (-111.5997, 31.9634, 2120.0)  # Mayall, geodätisch (Grad, Grad, m)

# Bekannte Linien im Ruhesystem, Vakuum, Å (Werte aus Standardtabellen, im Bericht als FROM MEMORY
# markiert; Fenster großzügig; datengetriebene Häufungs-Vetos fangen Fehler dieser Liste ab).
STELLAR_LINES = [
    3671.5, 3673.8, 3676.4, 3679.4, 3682.8, 3686.8, 3691.6, 3697.2, 3704.0, 3712.0, 3722.0, 3735.4,
    3751.2, 3771.7, 3798.98, 3836.47, 3890.15, 3971.20, 4102.89, 4341.68, 4862.68, 6564.61,  # Balmer
    3934.78, 3969.59,                                    # Ca II K, H
    8500.36, 8544.44, 8664.52,                           # Ca II IRT
    3889.75, 4027.33, 4472.73, 4923.30, 5017.08, 5877.25, 6679.99, 7067.14, 7283.36,  # He I
    4687.02, 5413.0,                                     # He II
    5891.58, 5897.56,                                    # Na D
    7774.1, 8448.7, 6158.2,                              # O I
    4925.0, 5019.8, 5170.5, 5318.0, 4235.9, 4585.0, 5236.0, 5277.0,  # Fe II (Emission in Be/aktiven)
    5168.8, 5174.1, 5185.0, 4482.6, 4572.4,              # Mg I b, Mg II, Mg I
    3727.09, 3729.88, 3870.16, 3968.91, 4364.44, 4960.30, 5008.24, 5756.2, 6302.05, 6365.54,
    6549.86, 6585.27, 6718.29, 6732.67, 7137.8, 7322.0, 7332.2, 9071.1, 9533.2,  # nebular
    8469.6, 8504.8, 8547.7, 8600.8, 8667.4, 8752.9, 8865.2, 9017.4, 9231.5, 9548.6,  # Paschen
    6709.6, 7667.0, 7701.1, 6347.1, 6373.1, 4078.9, 4216.7,  # Li, K I, Si II, Sr II
]
GAL = {'lya': 1215.67, 'nv': 1240.8, 'civ': 1549.06, 'heii': 1640.4, 'ciii': 1908.73, 'mgii': 2799.12,
       'oii': 3728.48, 'neiii': 3870.16, 'hd': 4102.89, 'hg': 4341.68, 'hb': 4862.68, 'oiii4': 4960.30,
       'oiii5': 5008.24, 'oi': 6302.05, 'nii4': 6549.86, 'ha': 6564.61, 'nii5': 6585.27, 'sii1': 6718.29,
       'sii2': 6732.67, 'siii1': 9071.1, 'siii2': 9533.2}
PARTNERS = {
    'ha': ['nii5', 'nii4', 'sii1', 'sii2', 'hb', 'oiii5'], 'nii5': ['ha', 'nii4'],
    'hb': ['oiii5', 'oiii4', 'ha', 'oii'], 'oiii5': ['oiii4', 'hb', 'ha', 'oii'], 'oiii4': ['oiii5', 'hb'],
    'oii': ['neiii', 'hb', 'oiii5', 'hg', 'hd'], 'sii1': ['sii2', 'ha'], 'sii2': ['sii1', 'ha'],
    'siii2': ['siii1', 'ha'], 'oi': ['ha', 'oiii5'], 'neiii': ['oii', 'hb'],
    'mgii': ['oii', 'ciii'], 'civ': ['lya', 'ciii', 'heii'], 'ciii': ['civ', 'mgii'], 'lya': ['nv', 'civ'],
}

S = requests.Session()
S.headers['User-Agent'] = 'ts-compute-w1/1.0 (open research; range reads)'


# ---------------------------------------------------------------- HTTP / FITS-Range-Zugriff
def _get(url, rng=None, timeout=180):
    h = {'Range': rng} if rng else {}
    err = None
    for a in range(4):
        try:
            r = S.get(url, headers=h, timeout=timeout)
            if r.status_code in (200, 206):
                return r
            err = f'HTTP {r.status_code}'
            if r.status_code in (404, 416):
                break
        except Exception as exc:  # Netzfehler: erneut versuchen
            err = repr(exc)
        time.sleep(2 * (a + 1))
    raise IOError(f'{url}: {err}')


def get_range(url, a, b):
    """Bytes [a, b) per Range-Request."""
    return _get(url, f'bytes={a}-{b - 1}').content


def get_ranges(url, ranges):
    """Mehrere Bereiche [(a,b),...] in einem Request (multipart/byteranges); Rückgabe in Eingabereihenfolge."""
    if not ranges:
        return []
    if len(ranges) == 1:
        return [get_range(url, *ranges[0])]
    spec = 'bytes=' + ','.join(f'{a}-{b - 1}' for a, b in ranges)
    r = _get(url, spec)
    ct = r.headers.get('content-type', '')
    if 'multipart/byteranges' not in ct:
        raise IOError('kein multipart: ' + ct)
    bnd = ct.split('boundary=')[1].strip().strip('"').encode()
    parts = {}
    for chunk in r.content.split(b'--' + bnd):
        if b'Content-Range' not in chunk and b'content-range' not in chunk:
            continue
        head, _, body = chunk.partition(b'\r\n\r\n')
        m = re.search(rb'bytes (\d+)-(\d+)/', head, re.I)
        a, b = int(m.group(1)), int(m.group(2)) + 1
        parts[a] = body[:b - a]
    return [parts[a] for a, _ in ranges]


def _parse_header(buf):
    cards, n = {}, 0
    for i in range(0, len(buf), 80):
        c = buf[i:i + 80].decode('ascii', 'replace')
        if c[:8].strip() == 'END':
            return cards, (i // 2880 + 1) * 2880
        if c[8:10] == '= ':
            v = c[10:].strip()
            if v.startswith("'"):
                v = v[1:].split("'")[0].strip()
            else:
                v = v.split('/')[0].strip()
            cards[c[:8].strip()] = v
    return cards, None


def fits_index(url):
    """Liste der HDUs: name, Header-Bytes, Datenstart, Datengröße, dims, bitpix (sequentiell per Range)."""
    off, out = 0, []
    while True:
        hb = b''
        while True:
            try:
                blk = get_range(url, off + len(hb), off + len(hb) + 2880 * 6)
            except IOError:
                return out
            if not blk:
                return out
            hb += blk
            cards, hlen = _parse_header(hb)
            if hlen:
                break
        bitpix = int(cards.get('BITPIX', 8))
        naxis = int(cards.get('NAXIS', 0))
        dims = [int(cards[f'NAXIS{i}']) for i in range(1, naxis + 1)]
        size = abs(bitpix) // 8 * (int(np.prod(dims)) if dims else 0) + int(cards.get('PCOUNT', 0) or 0)
        out.append(dict(name=cards.get('EXTNAME', 'PRIMARY'), hdr=hb[:hlen], cards=cards, dstart=off + hlen,
                        size=size, dims=dims, bitpix=bitpix))
        off = off + hlen + ((size + 2879) // 2880) * 2880


def table_from_bytes(hdr, data):
    prim = fits.PrimaryHDU().header.tostring().encode()
    pad = (-len(data)) % 2880
    hl = fits.open(io.BytesIO(prim + hdr + data + b'\0' * pad), memmap=False)
    return hl[1].data


def image_rows(url, h, rows):
    """Zeilen eines 2D/3D-Bildes (FITS big-endian) für Zeilenindizes rows; dims = [npix, (ndiag,) nrow]."""
    dt = {-32: '>f4', -64: '>f8', 32: '>i4', 16: '>i2', 8: 'u1'}[h['bitpix']]
    rowlen = int(np.prod(h['dims'][:-1])) * abs(h['bitpix']) // 8
    rows = np.asarray(rows)
    # zusammenhängende Läufe zusammenfassen
    runs, start = [], None
    for i, r in enumerate(rows):
        if start is None:
            start, prev = r, r
        elif r == prev + 1:
            prev = r
        else:
            runs.append((start, prev)); start, prev = r, r
    if start is not None:
        runs.append((start, prev))
    rngs = [(h['dstart'] + a * rowlen, h['dstart'] + (b + 1) * rowlen) for a, b in runs]
    out = []
    for i in range(0, len(rngs), 60):  # Server-Grenze für Teilbereiche je Request vorsichtig
        out += get_ranges(url, rngs[i:i + 60])
    buf = b''.join(out)
    shape = [len(rows)] + h['dims'][:-1][::-1]
    return np.frombuffer(buf, dtype=dt).reshape(shape).astype(np.dtype(dt).newbyteorder('='))


# ---------------------------------------------------------------- Hilfsfunktionen Spektren
def heliocor(ra, dec, mjd):
    from astropy.coordinates import SkyCoord, EarthLocation
    from astropy.time import Time
    import astropy.units as u
    loc = EarthLocation.from_geodetic(KPNO[0] * u.deg, KPNO[1] * u.deg, KPNO[2] * u.m)
    v = SkyCoord(ra * u.deg, dec * u.deg).radial_velocity_correction(
        kind='heliocentric', obstime=Time(mjd, format='mjd'), location=loc)
    return 1.0 + v.to(u.km / u.s).value / C_KMS


def block_median_interp(y, good, block):
    """Glattes Kontinuum: Median in Blöcken, linear interpoliert (robust gegen schmale Linien)."""
    n = y.size
    nb = max(2, int(np.ceil(n / block)))
    edges = np.linspace(0, n, nb + 1).astype(int)
    xc, yc = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        g = good[a:b]
        if g.sum() >= max(5, 0.2 * (b - a)):
            xc.append(0.5 * (a + b - 1)); yc.append(np.median(y[a:b][g]))
    if len(xc) < 2:
        return np.full(n, np.nan)
    return np.interp(np.arange(n), xc, yc)


def lsf_sigma_from_res(R):
    """R: (ndiag, npix) Auflösungsmatrix-Zeile -> sigma in Pixeln je Pixel."""
    nd = R.shape[0]
    d = np.arange(nd // 2, -(nd // 2) - 1, -1, dtype=float)
    s = R.sum(0)
    s = np.where(s > 0, s, np.nan)
    m1 = (R * d[:, None]).sum(0) / s
    m2 = (R * d[:, None] ** 2).sum(0) / s
    sig = np.sqrt(np.clip(m2 - m1 ** 2, 0.1, 9))
    if not np.isfinite(sig).any():
        return sig  # bleibt NaN -> lsf_for_fiber ersetzt durch Nachbarn/Standard
    return np.nan_to_num(sig, nan=np.nanmedian(sig))


def gauss_kernel(sig, half=4):
    x = np.arange(-half, half + 1, dtype=float)
    k = np.exp(-0.5 * (x / sig) ** 2)
    return k / k.sum()


def pix_gauss(n, center, sig, a=0, b=None):
    """Pixel-integriertes Gaußprofil um center (Pixelkoordinate), ausgewertet auf Pixeln [a, b)."""
    from scipy.special import erf
    x = np.arange(a, n if b is None else b, dtype=float)
    a = (x - 0.5 - center) / (np.sqrt(2) * sig)
    b = (x + 0.5 - center) / (np.sqrt(2) * sig)
    return 0.5 * (erf(b) - erf(a))


try:
    import numba

    @numba.njit(cache=True, fastmath=False)
    def _keys_nb(F, pos):
        m, n = F.shape
        k = pos.shape[1]
        out = np.empty((m, k))
        for r in range(m):
            for q in range(k):
                x = pos[r, q]
                i0 = int(np.floor(x))
                t = x - i0
                w0 = ((-0.5 * (t + 1) + 2.5) * (t + 1) - 4.0) * (t + 1) + 2.0
                w1 = (1.5 * t - 2.5) * t * t + 1
                u = 1 - t
                w2 = (1.5 * u - 2.5) * u * u + 1
                w3 = 1 - w0 - w1 - w2
                if i0 - 1 < 0 or i0 + 2 >= n:
                    out[r, q] = np.nan
                    continue
                v0 = F[r, i0 - 1]; v1 = F[r, i0]; v2 = F[r, i0 + 1]; v3 = F[r, i0 + 2]
                if np.isnan(v0) or np.isnan(v1) or np.isnan(v2) or np.isnan(v3):
                    out[r, q] = np.nan
                else:
                    out[r, q] = w0 * v0 + w1 * v1 + w2 * v2 + w3 * v3
        return out
    HAVE_NUMBA = True
except Exception:  # pragma: no cover
    HAVE_NUMBA = False


def keys_resample(F, pos):
    """Kubische Keys-Interpolation (a = -0.5) von F (m, n) an Positionen pos (m, k) in Pixeleinheiten; NaN-tolerant."""
    if HAVE_NUMBA:
        return _keys_nb(np.ascontiguousarray(F, dtype=np.float64), np.ascontiguousarray(pos, dtype=np.float64))
    m, n = F.shape
    i0 = np.floor(pos).astype(int)
    t = pos - i0
    a = -0.5
    w = [((a * (t + 1) - 5 * a) * (t + 1) + 8 * a) * (t + 1) - 4 * a,
         ((a + 2) * t - (a + 3)) * t * t + 1,
         ((a + 2) * (1 - t) - (a + 3)) * (1 - t) * (1 - t) + 1]
    w.append(1 - w[0] - w[1] - w[2])
    out = np.zeros(pos.shape)
    rows = np.arange(m)[:, None]
    bad = np.zeros(pos.shape, bool)
    for k, wk in zip(range(-1, 3), w):
        idx = i0 + k
        ok = (idx >= 0) & (idx < n)
        v = F[rows, np.clip(idx, 0, n - 1)]
        bad |= ~ok | ~np.isfinite(v)
        out += wk * np.nan_to_num(v)
    out[bad] = np.nan
    return out


# ---------------------------------------------------------------- Pass 1: Laden + Reduzieren
def tile_list(args):
    t = np.genfromtxt(io.StringIO(_get(BASE + '/tiles-iron.csv').text), delimiter=',', names=True,
                      dtype=None, encoding='utf-8')
    progs = args.get('program', 'bright')
    progs = [progs] if isinstance(progs, str) else list(progs)
    sel = (t['SURVEY'] == args.get('survey', 'main')) & np.isin(t['PROGRAM'], progs)
    t = t[sel]
    if args.get('tiles'):
        want = set(int(x) for x in args['tiles'])
        t = t[np.isin(t['TILEID'], list(want))]
    rng = np.random.default_rng(int(args.get('seed', 42)))
    t = t[rng.permutation(len(t))]
    if args.get('max_tiles'):
        t = t[:int(args['max_tiles'])]
    return [dict(tile=int(r['TILEID']), night=int(r['LASTNIGHT']), ra=float(r['TILERA']),
                 dec=float(r['TILEDEC']), nexp=int(r['NEXP'])) for r in t]


def split_of(tile, tune_frac):
    h = int(hashlib.sha256(str(tile).encode()).hexdigest()[:8], 16) / 16 ** 8
    return 'tune' if h < tune_frac else 'test'


_STRUCT = {}


def petal_index(url):
    """HDU-Index. Die Struktur der ersten Datei wird wiederverwendet, wenn alle Kopfblöcke an den erwarteten
    Positionen dieselbe EXTNAME und dieselben NAXISn tragen (EXP_FIBERMAP wächst mit der Belichtungszahl)."""
    ref = _STRUCT.get('coadd')
    if ref is not None:
        try:
            heads = get_ranges(url, [(h['dstart'] - len(h['hdr']), h['dstart'] - len(h['hdr']) + 2880)
                                     for h in ref])
            same = True
            for hb, h in zip(heads, ref):
                cards = _parse_header(hb)[0]
                if h['name'] != 'PRIMARY' and cards.get('EXTNAME') != h['name']:
                    same = False; break
                for i, dm in enumerate(h['dims']):
                    if int(cards.get(f'NAXIS{i + 1}', -1)) != dm:
                        same = False; break
                if not same:
                    break
            if same:
                return ref
        except Exception:
            pass
    idx = fits_index(url)
    if len(idx) >= 18 and ref is None:
        _STRUCT['coadd'] = idx
    return idx


def load_petal(ti, petal, rows_mode='all'):
    tile, night = ti['tile'], ti['night']
    d = f'{BASE}/tiles/cumulative/{tile}/{night}'
    url = f'{d}/coadd-{petal}-{tile}-thru{night}.fits'
    rr = fits.open(io.BytesIO(_get(f'{d}/redrock-{petal}-{tile}-thru{night}.fits').content), memmap=False)
    z = rr['REDSHIFTS'].data
    idx = petal_index(url)
    H = {h['name']: h for h in idx}
    fmh, efh = H['FIBERMAP'], H['EXP_FIBERMAP']
    fm_b, ef_b = get_ranges(url, [(fmh['dstart'], fmh['dstart'] + fmh['size']),
                                  (efh['dstart'], efh['dstart'] + efh['size'])])
    fm = table_from_bytes(fmh['hdr'], fm_b)
    ef = table_from_bytes(efh['hdr'], ef_b)
    assert np.all(fm['TARGETID'] == z['TARGETID']), 'Reihenfolge redrock/coadd verschieden'
    n = len(fm)
    spectype = np.char.strip(np.asarray(z['SPECTYPE']).astype(str))
    objtype = np.char.strip(np.asarray(fm['OBJTYPE']).astype(str))
    fstat = np.asarray(fm['COADD_FIBERSTATUS'])
    is_star = (spectype == 'STAR') & (objtype == 'TGT') & (fstat == 0)
    is_sky = (objtype == 'SKY') & (fstat == 0)
    if rows_mode == 'all':
        rows = np.arange(n)
    else:  # Sterne, Himmel und Nachbarn +-2
        keep = is_star | is_sky
        for s in (-2, -1, 1, 2):
            keep |= np.roll(is_star, s)
        rows = np.flatnonzero(keep)
    out = dict(tile=tile, night=night, petal=petal, fm=fm, ef=ef, z=z, rows=rows, is_star=is_star,
               is_sky=is_sky)
    for c in CAMS:
        out[c + '_FLUX'] = image_rows(url, H[c + '_FLUX'], rows).astype(np.float32)
        out[c + '_IVAR'] = image_rows(url, H[c + '_IVAR'], rows).astype(np.float32)
        out[c + '_MASK'] = image_rows(url, H[c + '_MASK'], rows) != 0
        # LSF aus 5 Stützfasern
        sup = np.unique(np.linspace(0, n - 1, 5).astype(int))
        R = image_rows(url, H[c + '_RESOLUTION'], sup)
        out[c + '_LSF'] = (sup, np.array([lsf_sigma_from_res(R[i]) for i in range(len(sup))], np.float32))
    mjd = float(np.nanmean(ef['MJD'])) if len(ef) else np.nan
    out['mjd'] = mjd
    out['heliocor'] = heliocor(ti['ra'], ti['dec'], float(np.nanmin(ef['MJD']))) if len(ef) else 1.0
    return out


LSF_DEFAULT = {'B': 0.83, 'R': 0.79, 'Z': 1.0}  # gemessen an Coadd 6369 / Kachel 21184 (Pixel)


def lsf_for_fiber(P, c, frow):
    sup, sig = P[c + '_LSF']
    good = np.isfinite(sig).all(1)
    sup, sig = sup[good], sig[good]
    if len(sup) == 0:
        return np.full(NPIX[c], LSF_DEFAULT[c], np.float32)
    if len(sup) == 1:
        return sig[0]
    j = np.searchsorted(sup, frow)
    j = np.clip(j, 1, len(sup) - 1)
    a, b = sup[j - 1], sup[j]
    t = (frow - a) / max(b - a, 1)
    return (1 - t) * sig[j - 1] + t * sig[j]


def reduce_petal(P, ti, split):
    """Sterne/Himmel als Arrays (obs-Gitter), übrige Fasern als Bitkarte; Rückgabe dict für npz."""
    rows = P['rows']
    fm, z = P['fm'], P['z']
    n_rows = len(rows)
    flux = np.concatenate([P[c + '_FLUX'] for c in CAMS], 1)
    ivar = np.concatenate([P[c + '_IVAR'] for c in CAMS], 1)
    mask = np.concatenate([P[c + '_MASK'] for c in CAMS], 1) | ~(ivar > 0) | ~np.isfinite(flux)
    lsf = np.zeros((n_rows, NTOT), np.float32)
    for c in CAMS:
        for i, r in enumerate(rows):
            lsf[i, OFF[c]:OFF[c] + NPIX[c]] = lsf_for_fiber(P, c, r)
    # Bitkarte "S/N > 4" für Nicht-Stern-/Nicht-Himmel-Fasern (Galaxien, QSO, ...): Hochpass + Matched Filter
    hot_other = np.zeros((n_rows, NTOT), bool)
    oth = np.flatnonzero(~(P['is_star'][rows] | P['is_sky'][rows]))
    if oth.size:
        snr, _, _ = hp_snr_2d(flux[oth], ivar[oth], mask[oth], lsf[oth])
        hot_other[oth] = snr > 4.0
    fiber = np.asarray(fm['FIBER'])[rows]
    st = P['is_star'][rows]
    sk = P['is_sky'][rows]

    def g(col, dflt=np.nan):
        return np.asarray(fm[col])[rows] if col in fm.columns.names else np.full(n_rows, dflt)
    meta = dict(
        targetid=np.asarray(fm['TARGETID'])[rows], fiber=fiber, z=np.asarray(z['Z'])[rows],
        zerr=np.asarray(z['ZERR'])[rows], zwarn=np.asarray(z['ZWARN'])[rows],
        subtype=np.char.strip(np.asarray(z['SUBTYPE']).astype(str))[rows],
        spectype=np.char.strip(np.asarray(z['SPECTYPE']).astype(str))[rows],
        ra=g('TARGET_RA'), dec=g('TARGET_DEC'), gmag=g('GAIA_PHOT_G_MEAN_MAG'), parallax=g('PARALLAX'),
        flux_r=g('FLUX_R'), fiberflux_r=g('FIBERFLUX_R'), fibertotflux_r=g('FIBERTOTFLUX_R'),
        numexp=g('COADD_NUMEXP'), exptime=g('COADD_EXPTIME'), mws=g('MWS_TARGET', 0), ebv=g('EBV'),
        pmra=g('PMRA'), pmdec=g('PMDEC'), ref_cat=np.char.strip(g('REF_CAT', '').astype(str)),
        ref_id=g('REF_ID', -1),
    )
    expids = ';'.join(str(int(e)) for e in np.unique(P['ef']['EXPID'])) if len(P['ef']) else ''
    keep = np.flatnonzero(st | sk)                 # nur Stern- und Himmelsfasern als Arrays speichern
    kpos = np.full(n_rows, -1, np.int32)
    kpos[keep] = np.arange(keep.size)
    return dict(flux=flux[keep], ivar=ivar[keep], mask=mask[keep], lsf=lsf[keep].astype(np.float16),
                kpos=kpos, hot_other=np.packbits(hot_other, axis=1), is_star=st, is_sky=sk,
                tile=ti['tile'], night=ti['night'], petal=P['petal'], mjd=P['mjd'], heliocor=P['heliocor'],
                expids=expids, split=split, **{'m_' + k: v for k, v in meta.items()})


def block_median_2d(F, G, block):
    """Wie block_median_interp, aber für viele Zeilen gleichzeitig (F, G: (n, npix))."""
    n, npix = F.shape
    nb = int(np.ceil(npix / block))
    pad = nb * block - npix
    X = np.where(G, F, np.nan)
    X = np.pad(X, ((0, 0), (0, pad)), constant_values=np.nan).reshape(n, nb, block)
    with np.errstate(all='ignore'):
        cnt = np.isfinite(X).sum(2)
        med = np.nanmedian(X, 2)
    med[cnt < max(5, block // 5)] = np.nan
    xc = (np.arange(nb) * block + 0.5 * (block - 1)).astype(float)
    xc[-1] = min(xc[-1], npix - 1)
    out = np.full((n, npix), np.nan)
    xs = np.arange(npix)
    for i in range(n):
        ok = np.isfinite(med[i])
        if ok.sum() >= 2:
            out[i] = np.interp(xs, xc[ok], med[i][ok])
    return out


def hp_snr_2d(flux, ivar, mask, lsf, block=32, rescale=True):
    """Hochpass-Matched-Filter-S/N für viele Fasern (obs-Gitter); Rückgabe snr, x (Residuum), w."""
    from scipy.ndimage import correlate1d
    n = flux.shape[0]
    SNR = np.zeros((n, NTOT))
    X = np.zeros((n, NTOT))
    Wt = np.zeros((n, NTOT))
    for c in CAMS:
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        f, iv, m = flux[:, sl].astype(float), ivar[:, sl].astype(float), mask[:, sl]
        good = ~m & (iv > 0)
        cont = block_median_2d(f, good, block)
        good &= np.isfinite(cont)
        x = np.where(good, f - np.nan_to_num(cont), 0.0)
        w = np.where(good, iv, 0.0)
        sig = float(np.median(lsf[:, sl]))
        k = gauss_kernel(sig, half=max(3, int(np.ceil(4 * sig))))
        num = correlate1d(w * x, k, axis=1, mode='constant')
        den = correlate1d(w, k * k, axis=1, mode='constant')
        snr = num / np.sqrt(np.where(den > 0, den, np.inf))
        if rescale:
            for i in range(n):
                v = snr[i][good[i]]
                if v.size > 100:
                    snr[i] /= max(1.0, 1.4826 * np.median(np.abs(v - np.median(v))))
        SNR[:, sl], X[:, sl], Wt[:, sl] = snr, x, w
    return SNR, X, Wt


def matched_filter(x, w, sig):
    """x: Residuum, w: Gewicht 1/sigma^2. Rückgabe snr, amp(je Pixel-Summe), var(amp)."""
    from scipy.ndimage import correlate1d
    k = gauss_kernel(sig, half=max(3, int(np.ceil(4 * sig))))
    num = correlate1d(w * x, k, mode='constant')
    den = correlate1d(w, k * k, mode='constant')
    den_safe = np.where(den > 0, den, np.inf)
    snr = num / np.sqrt(den_safe)
    amp = num / den_safe
    return snr, amp, 1.0 / den_safe


# ---------------------------------------------------------------- Normierung, Bibliothek
def normalize(flux, ivar, mask):
    """Kontinuum je Kamera (Block-Median 64 px); Rückgabe fn (NaN maskiert), en, cont."""
    fn = np.full(NTOT, np.nan)
    en = np.full(NTOT, np.nan)
    cont = np.full(NTOT, np.nan)
    for c in CAMS:
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        good = ~mask[sl]
        if good.sum() < 200:
            continue
        cc = block_median_interp(flux[sl].astype(float), good, 64)
        cc = np.where(cc > 0, cc, np.nan)
        cont[sl] = cc
        fn[sl] = np.where(good, flux[sl] / cc, np.nan)
        en[sl] = np.where(good, 1 / np.sqrt(np.where(ivar[sl] > 0, ivar[sl], np.inf)) / cc, np.nan)
    return fn, en, cont


def snr_cam(flux, ivar, mask):
    out = []
    for c in CAMS:
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        g = ~mask[sl]
        out.append(float(np.median(flux[sl][g] * np.sqrt(ivar[sl][g]))) if g.sum() > 100 else 0.0)
    return out


class Library:
    def __init__(self, FN, Z, TID, ncomp=40, seed=0):
        from sklearn.decomposition import PCA
        self.FN = FN.astype(np.float32)          # (L, NTOT) normierter Fluss, obs-Gitter, NaN maskiert
        self.Z = Z
        self.TID = TID
        X = np.nan_to_num(FN, nan=1.0)
        rng = np.random.default_rng(seed)
        sub = rng.choice(len(X), min(len(X), 15000), replace=False)
        self.pca = PCA(n_components=min(ncomp, len(sub) - 1), svd_solver='randomized', random_state=seed)
        self.pca.fit(X[sub])
        self.P = self.pca.transform(X).astype(np.float32)

    def candidates(self, fn, m, tid):
        p = self.pca.transform(np.nan_to_num(fn, nan=1.0)[None])[0]
        d = ((self.P - p) ** 2).sum(1)
        d[self.TID == tid] = np.inf
        idx = np.argpartition(d, m)[:m]
        return idx[np.isfinite(d[idx])]


def shifted_library(lib, idx, z_t):
    """Bibliothekssterne idx ins obs-Gitter eines Sterns mit Rotverschiebung z_t verschieben (je Kamera)."""
    out = np.full((len(idx), NTOT), np.nan)
    F = lib.FN[idx]
    for c in CAMS:
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        lam = W0[c] + DW * np.arange(NPIX[c])
        lam_rest = lam / (1 + z_t)
        pos = (lam_rest[None, :] * (1 + lib.Z[idx])[:, None] - W0[c]) / DW
        out[:, sl] = keys_resample(F[:, sl].astype(float), pos)
    return out


# ---------------------------------------------------------------- Residuen + Detektion je Stern
def residual_snr(fn, en, z_t, tid, lib, k_nn, m_pre, lsf, eps_sys=0.03, floor=0.002):
    """Rückgabe dict mit snr, ew(Å), ew_err, x (korr. Residuum), sig, r, S, corr, nnb."""
    from scipy.ndimage import correlate1d
    cand = lib.candidates(fn, m_pre, tid)
    if len(cand) < k_nn:
        return None
    Rc = shifted_library(lib, cand, z_t)
    good = np.isfinite(fn)
    wt = np.where(good, 1 / np.maximum(en, 0.01) ** 2, 0)          # S/N-Deckel 100 je Pixel für die Auswahl
    # Skalierung je Kandidat (glatter Faktor ignoriert; Normierung ist schon kontinuumsbezogen)
    fin = np.isfinite(Rc) & good[None, :]
    D = np.where(fin, Rc - np.nan_to_num(fn)[None, :], 0.0)
    W = np.where(fin, wt[None, :], 0.0)
    chi = (W * D * D).sum(1) / np.maximum(W.sum(1), 1e-9)
    best = np.argsort(chi)[:k_nn]
    NB = Rc[best]
    nvalid = np.isfinite(NB).sum(0)
    with np.errstate(all='ignore'):
        r = np.nanmedian(NB, 0)
        mad = np.nanmedian(np.abs(NB - r[None, :]), 0)
    rsc = 1.2533 * 1.4826 * mad / np.sqrt(np.maximum(nvalid, 1))
    ok = good & np.isfinite(r) & (nvalid >= max(8, k_nn // 3))
    out = dict(snr=np.zeros(NTOT), ew=np.zeros(NTOT), ew_err=np.full(NTOT, np.inf), x=np.zeros(NTOT),
               sig=np.full(NTOT, np.inf), r=np.where(ok, r, np.nan), S=np.full(NTOT, np.nan),
               corr=np.zeros(NTOT), ok=ok, chi_nn=float(np.median(chi[best])), rob=[1.0, 1.0, 1.0], fn=fn)
    win = np.ones(81)
    win[40 - 4:40 + 5] = 0
    for ci, c in enumerate(CAMS):
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        o = ok[sl]
        if o.sum() < 300:
            continue
        f, rr, e, rs = fn[sl], np.where(o, r[sl], 1.0), np.where(o, en[sl], np.inf), rsc[sl]
        ratio = np.where(o, f / np.where(rr != 0, rr, 1), np.nan)
        Sm = block_median_interp(np.nan_to_num(ratio, nan=1.0), o & np.isfinite(ratio), 48)
        m = rr * Sm
        x = np.where(o, f - m, 0.0)
        a = (rr - 1) * Sm
        b = np.gradient(m)
        cc = np.gradient(b)
        sig2 = e ** 2 + (Sm * rs) ** 2 + (eps_sys * a) ** 2 + floor ** 2
        w = np.where(o, 1 / sig2, 0.0)
        # lokale Regression x ~ al*a + be*b + ga*cc (Fenster +-40, Zentrum +-4 ausgespart)
        Rg = [a, b, cc]
        M = np.zeros((NPIX[c], 3, 3))
        V = np.zeros((NPIX[c], 3))
        for p in range(3):
            V[:, p] = correlate1d(w * x * Rg[p], win, mode='constant')
            for q in range(p, 3):
                M[:, p, q] = M[:, q, p] = correlate1d(w * Rg[p] * Rg[q], win, mode='constant')
        tr = np.trace(M, axis1=1, axis2=2)
        M += (1e-3 * tr + 1e-12)[:, None, None] * np.eye(3)[None]
        coef = np.linalg.solve(M, V[:, :, None])[:, :, 0]
        corr = coef[:, 0] * a + coef[:, 1] * b + coef[:, 2] * cc
        xc = np.where(o, x - corr, 0.0)
        lsf_sig = float(np.median(lsf[sl]))
        snr, amp, var = matched_filter(xc, w, lsf_sig)
        # robuste Nachskalierung (nur nach oben)
        v = snr[o]
        rob = 1.4826 * np.median(np.abs(v - np.median(v))) if v.size > 100 else 1.0
        rob = max(1.0, rob)
        out['rob'][ci] = rob
        out['snr'][sl] = np.where(o, snr / rob, 0.0)
        # amp = Summe des Linienprofils in normierten Flusseinheiten je Pixel -> EW = amp * DW
        out['ew'][sl] = amp * DW
        out['ew_err'][sl] = np.sqrt(var) * DW * rob
        out['x'][sl] = xc
        out['sig'][sl] = np.sqrt(sig2)
        out['S'][sl] = Sm
        out['corr'][sl] = corr
    return out


def width_fit(x, sig, j, lsf_sig, half=5):
    """Gaußfit auf Gitter (sigma, Zentrum) um Pixel j; Rückgabe best_sigma, dchi2(LSF vs best), chi2_lsf/dof."""
    n = x.size
    a, b = max(0, j - half), min(n, j + half + 1)
    xx = x[a:b]
    ww = 1 / np.maximum(sig[a:b], 1e-9) ** 2
    ww[~np.isfinite(ww)] = 0
    best = (np.inf, None)
    chis = {}
    for s in (0.35, 0.5, 0.65, 0.8, 1.0, 1.25, 1.6, 2.0, 2.6, 3.4, 4.5):
        for dc in (-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75):
            p = pix_gauss(n, j + dc, s * lsf_sig, a, b)
            den = (ww * p * p).sum()
            if den <= 0:
                continue
            amp = (ww * xx * p).sum() / den
            chi = (ww * (xx - amp * p) ** 2).sum()
            chis[(s, dc)] = chi
            if chi < best[0]:
                best = (chi, s)
    if best[1] is None:
        return np.nan, np.nan, np.nan
    chi_lsf = min(v for (s, dc), v in chis.items() if s == 1.0)
    dof = max(1, (b - a) - 3)
    return best[1], chi_lsf - best[0], chi_lsf / dof


def peaks(snr, ok, t):
    v = np.where(ok, snr, -np.inf)
    i = np.flatnonzero((v[1:-1] >= t) & (v[1:-1] >= v[:-2]) & (v[1:-1] > v[2:])) + 1
    return i[np.argsort(-v[i])][:30]


def cam_of(j):
    return 'B' if j < OFF['R'] else ('R' if j < OFF['Z'] else 'Z')


def lam_obs_of(j):
    c = cam_of(j)
    return W0[c] + DW * (j - OFF[c])


def pix_of(lam, c):
    return int(round((lam - W0[c]) / DW)) + OFF[c]


def other_cam_pix(j):
    lam = lam_obs_of(j)
    c = cam_of(j)
    for oc in CAMS:
        if oc != c and W0[oc] + 10 * DW <= lam <= W0[oc] + DW * (NPIX[oc] - 11):
            return pix_of(lam, oc)
    return None


def edge_dist(j):
    c = cam_of(j)
    k = j - OFF[c]
    return min(k, NPIX[c] - 1 - k)


STELLAR = np.array(sorted(STELLAR_LINES))


def det_features(j, res, snr_arr, z_t, cont, mask, star_meta, lsf_sig, helio, sky_tpl):
    lam = lam_obs_of(j)
    lam_rest = lam / (1 + z_t)
    lam_topo = lam / helio
    c = cam_of(j)
    bs, dchi, chil = width_fit(res['x'], res['sig'], j, lsf_sig)
    oj = other_cam_pix(j)
    if oj is not None and res['ok'][oj]:
        snr_o = float(np.max(snr_arr[max(0, oj - 1):oj + 2]))
        ew_o, ewe_o = float(res['ew'][oj]), float(res['ew_err'][oj])
    else:
        snr_o, ew_o, ewe_o = np.nan, np.nan, np.nan
    nm = int(mask[max(0, j - 2):j + 3].sum())
    # Partnerlinien-Test (Hintergrundquelle)
    best_h, best_p, best_n = '', 0.0, 0
    for k, lk in GAL.items():
        if k not in PARTNERS:
            continue
        zz = lam / lk - 1
        if not (-0.002 <= zz <= 7.0):
            continue
        pm, npk = 0.0, 0
        for pk in PARTNERS[k]:
            lp = GAL[pk] * (1 + zz)
            for cc in CAMS:
                if W0[cc] + 5 * DW <= lp <= W0[cc] + DW * (NPIX[cc] - 6):
                    pj = pix_of(lp, cc)
                    if res['ok'][pj]:
                        v = float(np.max(snr_arr[max(0, pj - 1):pj + 2]))
                        pm = max(pm, v)
                        npk += int(v >= 3.0)
        if (npk, pm) > (best_n, best_p):
            best_p, best_h, best_n = pm, k, npk
    d_known = float(np.min(np.abs(STELLAR - lam_rest)))
    st, sl_c, sl_l = sky_tpl
    sky_line = float(np.interp(lam_topo, st, sl_l))
    sky_cont = float(np.interp(lam_topo, st, sl_c))
    return dict(
        cam=c, pix=j, lam_obs=round(lam, 3), lam_rest=round(lam_rest, 3), lam_topo=round(lam_topo, 3),
        snr=round(float(snr_arr[j]), 3), ew=float(res['ew'][j]), ew_err=float(res['ew_err'][j]),
        line_flux=float(res['ew'][j] * cont[j]), cont=float(cont[j]),
        width_ratio=bs, dchi2_width=dchi, chi2_lsf=chil, lsf_sig=lsf_sig,
        peak_excess=float((res['fn'][j] - res['S'][j]) / res['sig'][j]) if np.isfinite(res['sig'][j]) else np.nan,
        ref_depth=float(1 - res['r'][j]) if np.isfinite(res['r'][j]) else np.nan,
        corr_rel=float(res['corr'][j] / res['sig'][j]) if np.isfinite(res['sig'][j]) else np.nan,
        nmask2=nm, edge=edge_dist(j), snr_other=snr_o, ew_other=ew_o, ew_err_other=ewe_o,
        gal_hyp=best_h, gal_partner_snr=round(best_p, 3), gal_npartner=best_n, d_known=round(d_known, 3),
        sky_line=sky_line, sky_cont=sky_cont, rob=res['rob'][CAMS.index(c)], chi_nn=res['chi_nn'],
    )


# ---------------------------------------------------------------- Himmelsmodell (Template)
def sky_template(cache=None):
    """Mittleres DESI-Himmelsspektrum (topozentrisch) aus einer Belichtung; Linien- und Kontinuumsanteil."""
    p = os.path.join(cache, 'sky_template.npz') if cache else None
    if p and os.path.exists(p):
        d = np.load(p)
        return d['lam'], d['cont'], d['line']
    lam_all, cont_all, line_all = [], [], []
    for cam in 'brz':
        r = _get(f'{BASE}/exposures/20210514/00088365/sky-{cam}0-00088365.fits.gz')
        import gzip
        h = fits.open(io.BytesIO(gzip.decompress(r.content)), memmap=False)
        sky = np.median(h['SKY'].data, 0).astype(float)
        lam = h['WAVELENGTH'].data.astype(float) / float(h[0].header['HELIOCOR'])
        cont = block_median_interp(sky, np.isfinite(sky), 24)
        lam_all.append(lam); cont_all.append(cont); line_all.append(np.clip(sky - cont, 0, None))
    lam = np.concatenate(lam_all); o = np.argsort(lam)
    out = lam[o], np.concatenate(cont_all)[o], np.concatenate(line_all)[o]
    if p:
        np.savez(p, lam=out[0], cont=out[1], line=out[2])
    return out


# ---------------------------------------------------------------- Pass 2 je Petal
DET_COLS = ['kind', 'inj_id', 'split', 'tile', 'petal', 'fiber', 'targetid', 'z', 'zwarn', 'subtype', 'gmag',
            'snr_b', 'snr_r', 'snr_z', 'cam', 'pix', 'lam_obs', 'lam_rest', 'lam_topo', 'snr', 'ew', 'ew_err',
            'line_flux', 'cont', 'width_ratio', 'dchi2_width', 'chi2_lsf', 'lsf_sig', 'peak_excess',
            'ref_depth', 'corr_rel', 'nmask2', 'edge', 'snr_other', 'ew_other', 'ew_err_other', 'gal_hyp',
            'gal_partner_snr', 'gal_npartner', 'd_known', 'sky_line', 'sky_cont', 'rob', 'chi_nn', 'n_cross4', 'n_cross4_sky',
            'adj1', 'adj2', 'numexp', 'mjd', 'cross_excess', 'n_sky_petal', 'expids', 'chi_nexp', 'chi_rel_max',
            'chi_rel_min', 'chi_nhi', 'chi_frac_fibers_min', 'chi_fmask', 'chi_err', 'vetoes']
INJ_COLS = ['inj_id', 'split', 'tile', 'petal', 'fiber', 'targetid', 'gmag', 'snr_r', 'cam', 'pix_true',
            'lam_obs', 'ew_true', 'flux_true', 'snr_exp', 'found', 'snr_found', 'z', 'subtype', 'parallax',
            'cont', 'ew_err_pix']
SPEC_COLS = ['split', 'tile', 'petal', 'fiber', 'targetid', 'ra', 'dec', 'z', 'zerr', 'zwarn', 'subtype', 'gmag',
             'parallax', 'pmra', 'pmdec', 'ref_cat', 'ref_id', 'flux_r', 'fiberflux_r', 'fibertotflux_r', 'ebv',
             'mws', 'numexp', 'exptime', 'snr_b', 'snr_r', 'snr_z', 'n_ok', 'chi_nn', 'rob_b', 'rob_r', 'rob_z',
             'ewerr_med_b', 'ewerr_med_r', 'ewerr_med_z', 'cont_med_b', 'cont_med_r', 'cont_med_z', 'n_det',
             'mjd', 'expids', 'heliocor', 'status']
SKY_COLS = ['split', 'tile', 'petal', 'fiber', 'n_ok', 'n_det', 'mjd']


def process_petal(D, lib, args, sky_tpl, seed):
    """D: reduziertes Petal (dict). Rückgabe (det_rows, inj_rows, spec_rows, sky_rows)."""
    t_pre = float(args.get('t_pre', 5.0))
    k_nn, m_pre = int(args.get('k_nn', 25)), int(args.get('m_pre', 60))
    inj_frac = float(args.get('inj_frac', 1.0))
    rng = np.random.default_rng(seed)
    n = len(D['m_fiber'])
    star_idx = np.flatnonzero(D['is_star'])
    sky_idx = np.flatnonzero(D['is_sky'])
    hot = np.unpackbits(D['hot_other'], axis=1, count=NTOT).astype(bool)   # S/N>4-Karte aller Fasern
    kp = D['kpos']
    hot3 = np.zeros_like(hot)
    det_rows, inj_rows, spec_rows, sky_rows = [], [], [], []
    pending = []                                      # (kind, row-index, dict) -> Querzählung danach
    base = dict(split=str(D['split']), tile=int(D['tile']), petal=int(D['petal']), expids=str(D['expids']))
    helio = float(D['heliocor'])
    mjd = float(D['mjd'])
    expids = str(D['expids'])
    # --- Sterne
    for i in star_idx:
        meta = {k[2:]: D[k][i] for k in D if k.startswith('m_')}
        flux, ivar, mask = D['flux'][kp[i]].astype(float), D['ivar'][kp[i]].astype(float), D['mask'][kp[i]]
        LSF = D['lsf'][kp[i]].astype(float)
        snrs = snr_cam(flux, ivar, mask)
        fn, en, cont = normalize(flux, ivar, mask)
        row = dict(base, fiber=meta['fiber'], targetid=meta['targetid'], ra=meta['ra'], dec=meta['dec'],
                   z=meta['z'], zerr=meta['zerr'], zwarn=meta['zwarn'], subtype=meta['subtype'],
                   gmag=meta['gmag'], parallax=meta['parallax'], pmra=meta['pmra'], pmdec=meta['pmdec'],
                   ref_cat=meta['ref_cat'], ref_id=meta['ref_id'], flux_r=meta['flux_r'],
                   fiberflux_r=meta['fiberflux_r'], fibertotflux_r=meta['fibertotflux_r'], ebv=meta['ebv'],
                   mws=meta['mws'], numexp=meta['numexp'], exptime=meta['exptime'], snr_b=snrs[0],
                   snr_r=snrs[1], snr_z=snrs[2], mjd=mjd, expids=expids, heliocor=helio)
        res = residual_snr(fn, en, float(meta['z']), meta['targetid'], lib, k_nn, m_pre, LSF) \
            if np.isfinite(fn).sum() > 1000 else None
        if res is None:
            spec_rows.append(dict(row, n_ok=0, n_det=0, status='no_model'))
            continue
        ok = res['ok']
        valid = ok.copy()
        for c in CAMS:  # Kamerakanten nicht detektieren
            valid[OFF[c]:OFF[c] + 10] = False
            valid[OFF[c] + NPIX[c] - 10:OFF[c] + NPIX[c]] = False
        snr = res['snr']
        hot[i] = snr > 4.0
        hot3[i] = snr > 3.0
        pk = peaks(snr, valid, t_pre)
        sm = dict(snr_b=snrs[0], snr_r=snrs[1], snr_z=snrs[2])
        for j in pk:
            f = det_features(j, res, snr, float(meta['z']), cont, mask, meta, float(LSF[j]), helio, sky_tpl)
            pending.append(('real', i, dict(base, kind='real', inj_id=-1, fiber=meta['fiber'],
                                            targetid=meta['targetid'], z=meta['z'], zwarn=meta['zwarn'],
                                            subtype=meta['subtype'], gmag=meta['gmag'], numexp=meta['numexp'],
                                            mjd=mjd, **sm, **f)))
        ewe = {c: float(np.median(res['ew_err'][OFF[c]:OFF[c] + NPIX[c]][ok[OFF[c]:OFF[c] + NPIX[c]]]))
               if ok[OFF[c]:OFF[c] + NPIX[c]].sum() > 100 else np.nan for c in CAMS}
        cm = {c: float(np.nanmedian(cont[OFF[c]:OFF[c] + NPIX[c]])) for c in CAMS}
        spec_rows.append(dict(row, n_ok=int(ok.sum()), chi_nn=res['chi_nn'], rob_b=res['rob'][0],
                              rob_r=res['rob'][1], rob_z=res['rob'][2], ewerr_med_b=ewe['B'],
                              ewerr_med_r=ewe['R'], ewerr_med_z=ewe['Z'], cont_med_b=cm['B'],
                              cont_med_r=cm['R'], cont_med_z=cm['Z'], n_det=len(pk), status='ok'))
        # --- Injektion (Beobachtungsgitter, LSF der Faser, pixelintegriert)
        if rng.random() < inj_frac:
            cand = np.flatnonzero(valid & np.isfinite(res['ew_err']) & (res['ew_err'] > 0))
            if cand.size > 100:
                jt = int(rng.choice(cand))
                c = cam_of(jt)
                snr_exp = float(rng.uniform(2.0, 16.0))
                ew_true = snr_exp * float(res['ew_err'][jt])
                center = jt + float(rng.uniform(-0.5, 0.5))
                sl = slice(OFF[c], OFF[c] + NPIX[c])
                prof = pix_gauss(NPIX[c], center - OFF[c], float(LSF[jt]))
                lf = ew_true * float(cont[jt])                 # 1e-17 erg/s/cm2
                fi = flux.copy()
                fi[sl] = fi[sl] + lf * prof / DW
                # Im Kamera-Überlapp erscheint eine echte Linie in BEIDEN Detektoren -> auch dort injizieren
                lam_c = W0[c] + DW * (center - OFF[c])
                for oc in CAMS:
                    if oc != c and W0[oc] <= lam_c <= W0[oc] + DW * (NPIX[oc] - 1):
                        po = (lam_c - W0[oc]) / DW
                        jo = OFF[oc] + int(round(po))
                        slo = slice(OFF[oc], OFF[oc] + NPIX[oc])
                        fi[slo] = fi[slo] + lf * pix_gauss(NPIX[oc], po, float(LSF[min(jo, NTOT - 1)])) / DW
                fn2, en2, cont2 = normalize(fi, ivar, mask)
                res2 = residual_snr(fn2, en2, float(meta['z']), meta['targetid'], lib, k_nn, m_pre, LSF)
                inj_id = int(rng.integers(1, 2 ** 31))
                found, snr_found = 0, np.nan
                if res2 is not None:
                    pk2 = peaks(res2['snr'], valid & res2['ok'], t_pre)
                    near = [j for j in pk2 if abs(j - jt) <= 2]
                    if near:
                        j = max(near, key=lambda q: res2['snr'][q])
                        found, snr_found = 1, float(res2['snr'][j])
                        f = det_features(j, res2, res2['snr'], float(meta['z']), cont2, mask, meta,
                                         float(LSF[j]), helio, sky_tpl)
                        pending.append(('inj', i, dict(base, kind='inj', inj_id=inj_id, fiber=meta['fiber'],
                                                       targetid=meta['targetid'], z=meta['z'],
                                                       zwarn=meta['zwarn'], subtype=meta['subtype'],
                                                       gmag=meta['gmag'], numexp=meta['numexp'], mjd=mjd,
                                                       **sm, **f)))
                inj_rows.append(dict(base, inj_id=inj_id, fiber=meta['fiber'], targetid=meta['targetid'],
                                     gmag=meta['gmag'], snr_r=snrs[1], cam=c, pix_true=jt,
                                     lam_obs=round(lam_obs_of(jt), 3), ew_true=ew_true, flux_true=lf,
                                     snr_exp=snr_exp, found=found, snr_found=snr_found, z=meta['z'],
                                     subtype=meta['subtype'], parallax=meta['parallax'], cont=float(cont[jt]),
                                     ew_err_pix=float(res['ew_err'][jt])))
    # --- Himmelsfasern (Null ohne Stern): Hochpass-Matched-Filter im obs-Gitter, gleiche Schwelle
    if sky_idx.size:
        ks = kp[sky_idx]
        SS, SX, SW = hp_snr_2d(D['flux'][ks], D['ivar'][ks], D['mask'][ks], D['lsf'][ks].astype(float))
        st, sl_c, sl_l = sky_tpl
        for q, i in enumerate(sky_idx):
            s_, x_, w_ = SS[q], SX[q], SW[q]
            good = w_ > 0
            hot[i] = s_ > 4.0
            hot3[i] = s_ > 3.0
            valid = good.copy()
            for c in CAMS:
                valid[OFF[c]:OFF[c] + 10] = False
                valid[OFF[c] + NPIX[c] - 10:OFF[c] + NPIX[c]] = False
            pk = peaks(s_, valid, t_pre)
            sig_ = 1 / np.sqrt(np.where(good, w_, 1e-30))
            mask = D['mask'][kp[i]]
            for j in pk:
                lam = lam_obs_of(j)
                lsf_j = float(D['lsf'][kp[i]][j])
                bs, dchi, chil = width_fit(x_, sig_, j, lsf_j)
                oj = other_cam_pix(j)
                snr_o = float(np.max(s_[max(0, oj - 1):oj + 2])) if (oj is not None and good[oj]) else np.nan
                pending.append(('sky', i, dict(base, kind='sky', inj_id=-1, fiber=int(D['m_fiber'][i]),
                                               targetid=int(D['m_targetid'][i]), cam=cam_of(j), pix=int(j),
                                               lam_obs=round(lam, 3), lam_topo=round(lam / helio, 3),
                                               snr=round(float(s_[j]), 3), line_flux=float(x_[j:j + 1].sum()),
                                               width_ratio=bs, dchi2_width=dchi, chi2_lsf=chil, lsf_sig=lsf_j,
                                               nmask2=int(mask[max(0, j - 2):j + 3].sum()), edge=edge_dist(j),
                                               snr_other=snr_o,
                                               sky_line=float(np.interp(lam / helio, st, sl_l)),
                                               sky_cont=float(np.interp(lam / helio, st, sl_c)), mjd=mjd)))
            sky_rows.append(dict(base, fiber=int(D['m_fiber'][i]), n_ok=int(good.sum()), n_det=len(pk), mjd=mjd))
    # --- Faser-übergreifende Zählung (gleiches Spektrograph/Belichtung, obs-Gitter +-1 px)
    from scipy.ndimage import maximum_filter1d
    hd = maximum_filter1d(hot.astype(np.uint8), 3, axis=1).astype(bool)
    hd3 = maximum_filter1d(hot3.astype(np.uint8), 3, axis=1).astype(bool)
    cnt = hd.sum(0).astype(float)
    cnt_sky = hd[D['is_sky']].sum(0)
    # Überschuss der Zählkarte gegenüber ihrer Umgebung (+-40 px, Zentrum +-3 ausgespart, Median):
    # Instrument/Himmel erzeugt Spitzen bei derselben beobachteten Wellenlänge, Sternmerkmale streuen über RV
    from scipy.ndimage import median_filter
    loc = np.zeros(NTOT)
    for c in CAMS:
        sl = slice(OFF[c], OFF[c] + NPIX[c])
        fp = np.ones(81, bool); fp[37:44] = False
        loc[sl] = median_filter(cnt[sl], footprint=fp, mode='nearest')
    order = np.argsort(D['m_fiber'])
    pos = {int(D['m_fiber'][k]): k for k in range(n)}
    for kind, i, rowd in pending:
        j = int(rowd['pix'])
        # andere Fasern desselben Spektrographen (die eigene Faser zählt nie mit; bei Injektionen ist hd[i]
        # die echte, uninjizierte Karte)
        rowd['n_cross4'] = int(cnt[j] - int(hd[i, j]))
        rowd['n_cross4_sky'] = int(cnt_sky[j] - (int(hd[i, j]) if D['is_sky'][i] else 0))
        rowd['cross_excess'] = float(cnt[j] - int(hd[i, j]) - loc[j])
        rowd['n_sky_petal'] = int(D['is_sky'].sum())
        fb = int(D['m_fiber'][i])
        a1 = [pos[q] for q in (fb - 1, fb + 1) if q in pos]
        a2 = [pos[q] for q in (fb - 2, fb + 2) if q in pos]
        rowd['adj1'] = int(any(hd3[k, j] for k in a1))
        rowd['adj2'] = int(any(hd3[k, j] for k in a2))
        det_rows.append(rowd)
    return det_rows, inj_rows, spec_rows, sky_rows




# ---------------------------------------------------------------- Stufe A (eingefrorene Regeln aus dem Pilot)
def _in_windows(lam, centers, half):
    if not centers:
        return False
    c = np.asarray(centers)
    return bool(np.min(np.abs(c - lam)) <= half)


def stage_a_flags(d, R):
    """Vetos der Stufe A für eine Detektion (dict). Spiegelbild von analysis/W1-laser/gate.py:veto_flags
    (ohne chi2pix, das erst Pass 3 liefert). Rückgabe: Liste der greifenden Vetos (leer = überlebt)."""
    f = []
    g = lambda k, dflt=np.nan: d.get(k, dflt) if d.get(k, dflt) is not None else dflt
    num = lambda k: float(g(k)) if g(k) == g(k) and g(k) != '' else np.nan
    if num('snr') < R['T']: f.append('snr')
    if num('nmask2') > 0: f.append('mask')
    if num('d_known') <= R['known_half']: f.append('known')
    if num('sky_line') / max(num('sky_cont'), 1e-3) > R['sky_ratio']: f.append('sky')
    if num('n_cross4_sky') >= R['cross_sky_max'] + 1 or num('cross_excess') >= R['cross_excess']: f.append('cross')
    if num('adj1') > 0 or num('adj2') > 0: f.append('adjacent')
    so, eo = num('snr_other'), num('ew_err_other')
    if so == so and eo == eo and eo > 0 and num('ew') / eo >= 3 and so < R['overlap_min']: f.append('overlap')
    w = num('width_ratio')
    if w < R['w_lo'] or w > R['w_hi']: f.append('width')
    if num('gal_partner_snr') >= R['gal_partner'] or num('gal_npartner') >= R['gal_npartner']: f.append('galaxy')
    if abs(num('corr_rel')) > R['corr_max']: f.append('mismatch')
    if _in_windows(num('lam_rest'), R['clus_rest'], R['clus_half']): f.append('clus_rest')
    if _in_windows(num('lam_topo'), R['clus_topo'], R['clus_half']): f.append('clus_topo')
    if num('peak_excess') < R['peak_excess_min']: f.append('emission_shape')
    if num('edge') < R['edge_min']: f.append('edge')
    if w < 1 and num('dchi2_width') > R['narrow_dchi2']: f.append('narrow')
    return f

# ---------------------------------------------------------------- Pass 3: Extraktions-chi2 der Einzelbelichtungen
def exposure_nights():
    """EXPID -> NIGHT aus der öffentlichen Belichtungstabelle."""
    t = np.genfromtxt(io.StringIO(_get(BASE + '/exposures-iron.csv').text), delimiter=',', names=True,
                      usecols=(0, 1, 2), dtype=None, encoding='utf-8')
    return {int(e): int(n) for n, e in zip(t['NIGHT'], t['EXPID'])}


def chi_features(chi, wl, fib, msk, cands):
    """CHI2PIX-Merkmale je Kandidat (cid, fiber, lam) aus einer Einzelbelichtung (chi, msk: (nfib, npix))."""
    out = []
    pos = {int(f): k for k, f in enumerate(fib)}
    for cid, fiber, lam in cands:
        if int(fiber) not in pos:
            out.append((cid, dict(chi_err='fiber'))); continue
        r = pos[int(fiber)]
        jj = int(np.argmin(np.abs(wl - lam)))
        c = chi[r].astype(float)
        loc = np.r_[c[max(0, jj - 30):max(0, jj - 4)], c[jj + 5:jj + 31]]
        loc = loc[loc > 0]
        cm = float(np.max(c[max(0, jj - 2):jj + 3]))
        cl = float(np.median(loc)) if loc.size > 5 else np.nan
        allc = chi[:, max(0, jj - 2):jj + 3].astype(float).max(1)
        out.append((cid, dict(chi_max=cm, chi_loc=cl, chi_rel=cm / max(cl, 0.05) if np.isfinite(cl) else np.nan,
                              chi_frac_fibers=float((allc >= cm).mean()),
                              fmask=int((msk[r, max(0, jj - 2):jj + 3] != 0).sum()))))
    return out


def _chi2_file(task):
    """Ein frame-File (Kamera, Petal, Belichtung): CHI2PIX-Merkmale für alle Kandidaten darin."""
    import gzip
    night, expid, cam, petal, cands = task
    url = f'{BASE}/exposures/{night}/{expid:08d}/frame-{cam.lower()}{petal}-{expid:08d}.fits.gz'
    try:
        h = fits.open(io.BytesIO(gzip.decompress(_get(url, timeout=600).content)), memmap=False)
        chi = h['CHI2PIX'].data
        wl = h['WAVELENGTH'].data
        fib = np.asarray(h['FIBERMAP'].data['FIBER'])
        msk = h['MASK'].data
    except Exception as exc:
        return [(c[0], expid, dict(chi_err=repr(exc)[:80])) for c in cands]
    return [(cid, expid, v) for cid, v in chi_features(chi, wl, fib, msk, cands)]


def aggregate_chi(dets, per):
    for cid, vals in per.items():
        good = [v for v in vals if 'chi_rel' in v and np.isfinite(v['chi_rel'])]
        d = dets[cid]
        d['chi_nexp'] = len(good)
        if good:
            rel = [v['chi_rel'] for v in good]
            d['chi_rel_max'], d['chi_rel_min'] = float(max(rel)), float(min(rel))
            d['chi_nhi'] = int(sum(x > 3 for x in rel))
            d['chi_frac_fibers_min'] = float(min(v['chi_frac_fibers'] for v in good))
            d['chi_fmask'] = int(max(v['fmask'] for v in good))
        else:
            d['chi_err'] = ';'.join(v.get('chi_err', '') for v in vals)[:80]


def chi_groups(dets, nights, tmin):
    groups = {}
    for k, d in enumerate(dets):
        d['cid'] = k
        if d['kind'] not in ('real', 'sky') or d['snr'] < tmin or d.get('nmask2', 0) > 0:
            continue
        for e in str(d.get('expids', '')).split(';'):
            if not e:
                continue
            e = int(e)
            if e not in nights:
                continue
            groups.setdefault((nights[e], e, d['cam'], int(d['petal'])), []).append((k, int(d['fiber']), float(d['lam_obs'])))
    return groups


def chi2pix_pass(dets, nights, threads=8, tmin=5.0, log_args=None):
    """Ergänzt Detektionen (kind real/sky, S/N >= tmin, ohne Maske) um CHI2PIX aus allen Einzelbelichtungen.
    Spalten: chi_rel_max, chi_rel_min, chi_nexp, chi_nhi (Belichtungen mit chi_rel > 3), chi_frac_fibers_min."""
    groups = chi_groups(dets, nights, tmin)
    tasks = [(n, e, c, p, cands) for (n, e, c, p), cands in groups.items()]
    per = {}
    with ThreadPoolExecutor(threads) as pool:
        for m, res in enumerate(pool.map(_chi2_file, tasks)):
            for cid, e, v in res:
                per.setdefault(cid, []).append(v)
            if log_args is not None and m % 50 == 0:
                _log(log_args, f'pass3 {m + 1}/{len(tasks)}')
    aggregate_chi(dets, per)
    return len(tasks)


# ---------------------------------------------------------------- Shard-Steuerung
def _load_petal(path):
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}


def _p1_one(task):
    ti, p, args, cache = task
    path = os.path.join(cache, f"p_{ti['tile']}_{p}.npz")
    if os.path.exists(path):
        return path, dict(tile=ti['tile'], petal=p, status='cached', n_star=-1, error='')
    try:
        P = load_petal(ti, p, args.get('rows', 'all'))
        D = reduce_petal(P, ti, split_of(ti['tile'], float(args.get('tune_frac', 0.3))))
        tmp = path[:-4] + '.tmp.npz'
        np.savez(tmp, **D)
        os.replace(tmp, path)
        return path, dict(tile=ti['tile'], petal=p, status='ok', n_star=int(D['is_star'].sum()), error='')
    except Exception as exc:
        return None, dict(tile=ti['tile'], petal=p, status='fail', n_star=0, error=repr(exc)[:200])


def pass1(tiles, args, cache, nproc):
    """Laden + Reduzieren in Prozessen (Download und CPU überlappen; GIL umgangen)."""
    import multiprocessing as mp
    tasks = [(ti, p, args, cache) for ti in tiles for p in range(10)]
    paths, stat = [], []
    log = args.get('log')
    with mp.get_context('fork').Pool(nproc) as pool:
        for k, (path, st) in enumerate(pool.imap_unordered(_p1_one, tasks, chunksize=1)):
            stat.append(st)
            if path:
                paths.append(path)
            if log and st['status'] == 'fail':
                with open(log, 'a') as f:
                    f.write(f"{time.strftime('%H:%M:%S')} FAIL {st['tile']}/{st['petal']}: {st['error']}\n")
            if log and (k % 20 == 0 or k == len(tasks) - 1):
                with open(log, 'a') as f:
                    f.write(f"{time.strftime('%H:%M:%S')} pass1 {k + 1}/{len(tasks)} "
                            f"fail={sum(1 for x in stat if x['status'] == 'fail')}\n")
    return sorted(paths), stat


def _lib_one(task):
    path, lib_snr = task
    D = _load_petal(path)
    FN, Z, TID, SN = [], [], [], []
    kp = D['kpos']
    for i in np.flatnonzero(D['is_star']):
        if D['m_zwarn'][i] != 0:
            continue
        q = kp[i]
        sn = snr_cam(D['flux'][q], D['ivar'][q], D['mask'][q])
        if min(sn) < lib_snr:
            continue
        fn, en, cont = normalize(D['flux'][q].astype(float), D['ivar'][q].astype(float), D['mask'][q])
        if np.isfinite(fn).sum() < 0.8 * NTOT:
            continue
        FN.append(fn.astype(np.float32)); Z.append(float(D['m_z'][i])); TID.append(int(D['m_targetid'][i]))
        SN.append(min(sn))
    return FN, Z, TID, SN


def build_library(paths, args):
    """Sterne hoher S/N (alle Kameras >= lib_snr, ZWARN = 0) des Shards; bei Überzahl zufällige Auswahl."""
    import multiprocessing as mp
    lib_snr, lib_max = float(args.get('lib_snr', 15)), int(args.get('lib_max', 30000))
    FN, Z, TID, SN = [], [], [], []
    with mp.get_context('fork').Pool(int(args.get('workers', 4))) as pool:
        for f, z, t, sn in pool.imap(_lib_one, [(p, lib_snr) for p in paths], chunksize=4):
            FN += f; Z += z; TID += t; SN += sn
    FN, Z, TID = np.array(FN), np.array(Z), np.array(TID)
    if len(FN) > lib_max:
        keep = np.random.default_rng(1).choice(len(FN), lib_max, replace=False)
        FN, Z, TID = FN[keep], Z[keep], TID[keep]
    return Library(FN, Z, TID)


_LIB = None
_ARGS = None
_SKY = None


def _work(task):
    """Ein Petal; Ergebnis sofort als Checkpoint (pickle) neben den Cache, Neustart überspringt Fertiges."""
    import pickle
    path, seed = task
    part = path[:-4] + '.part.pkl'
    if os.path.exists(part):
        try:
            return pickle.load(open(part, 'rb')), None
        except Exception:
            pass
    try:
        D = _load_petal(path)
        res = process_petal(D, _LIB, _ARGS, _SKY, seed)
        pickle.dump(res, open(part + '.tmp', 'wb'))
        os.replace(part + '.tmp', part)
        return res, None
    except Exception as exc:
        import traceback
        return None, f'{os.path.basename(path)}: {traceback.format_exc()[-400:]}'


def _log(args, msg):
    if args.get('log'):
        with open(args['log'], 'a') as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def _write(path, cols, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 6) if isinstance(v, (float, np.floating)) and np.isfinite(v) else v)
                        for k, v in r.items()})


def run(args, shard, nshards, out):
    global _LIB, _ARGS, _SKY
    t0 = time.time()
    threads, workers = int(args.get('threads', 8)), int(args.get('workers', 4))
    tiles = tile_list(args)
    n_all = len(tiles)
    tiles = tiles[shard::nshards]
    import tempfile
    cache = args.get('cache') or os.path.join(tempfile.gettempdir(), f'w1cache_{shard:04d}')
    os.makedirs(cache, exist_ok=True)
    paths, pstat = pass1(tiles, args, cache, threads)
    _log(args, f'pass1 fertig: {len(paths)} Petals, {time.time() - t0:.0f} s')
    t1 = time.time()
    _SKY = sky_template(cache)
    _LIB = build_library(paths, args)
    _ARGS = args
    t2 = time.time()
    _log(args, f'Bibliothek: {len(_LIB.TID)} Sterne, {t2 - t1:.0f} s')
    dets, injs, specs, skys, errors = [], [], [], [], []
    # Tuning-Petals zuerst (Regeln können eingefroren werden, während Test-Petals rechnen)
    tf = float(args.get('tune_frac', 0.3))
    paths_o = sorted(paths, key=lambda p: (split_of(int(os.path.basename(p).split('_')[1]), tf) != 'tune', p))
    tasks = [(p, int(hashlib.sha256(os.path.basename(p).encode()).hexdigest()[:8], 16)) for p in paths_o]
    if workers > 1:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(workers) as pool:
            for k, (res, err) in enumerate(pool.imap_unordered(_work, tasks, chunksize=1)):
                if k % 20 == 0:
                    _log(args, f'pass2 {k + 1}/{len(tasks)} dets={len(dets)} injs={len(injs)}')
                if err:
                    errors.append(err); continue
                d, i, s, k = res
                dets += d; injs += i; specs += s; skys += k
    else:
        for tk in tasks:
            res, err = _work(tk)
            if err:
                errors.append(err); continue
            d, i, s, k = res
            dets += d; injs += i; specs += s; skys += k
    t3 = time.time()
    sfx = f'{shard:04d}'
    n_det_raw = sum(1 for d in dets if d['kind'] == 'real')
    pf = args.get('prefilter')
    if pf:  # Volllauf: nur Zeilen schreiben, die die harten, billigen Vetos überleben (Größe von ts-results)
        tw, kh = float(pf.get('t_write', 5.5)), float(pf.get('known_half', 4.0))

        def keep(d):
            if d['kind'] == 'inj':
                return True
            if d['snr'] < tw or d.get('nmask2', 0) > 0:
                return False
            if d['kind'] == 'real' and d.get('d_known', 99) <= kh:
                return False
            return True
        dets = [d for d in dets if keep(d)]
    R = args.get('rules')
    if R:  # eingefrorene Stufe-A-Regeln: echte Detektionen nur behalten, wenn sie alle Coadd-Vetos überstehen
        for d in dets:
            d['vetoes'] = ','.join(stage_a_flags(d, R)) if d['kind'] != 'inj' else ''
        dets = [d for d in dets if d['kind'] == 'inj' or d['vetoes'] == '']
    n_chi_files = 0
    if args.get('chi2pix', False):
        n_chi_files = chi2pix_pass(dets, exposure_nights(), threads=threads, tmin=float(args.get('chi_tmin', 5.0)),
                                   log_args=args)
        _log(args, f'pass3 fertig: {n_chi_files} frame-Dateien, {time.time() - t3:.0f} s')
    t4 = time.time()
    _write(os.path.join(out, f'detections_{sfx}.csv'), DET_COLS, dets)
    _write(os.path.join(out, f'injections_{sfx}.csv'), INJ_COLS, injs)
    _write(os.path.join(out, f'skyfibers_{sfx}.csv'), SKY_COLS, skys)
    _write(os.path.join(out, f'petals_{sfx}.csv'), ['tile', 'petal', 'status', 'n_star', 'error'], pstat)
    if args.get('table', 'full') == 'full':
        _write(os.path.join(out, f'spectra_{sfx}.csv'), SPEC_COLS, specs)
    else:  # Aggregat: Zählungen je (split, S/N-Bin, G-Bin) -> Nenner und Empfindlichkeit
        agg = {}
        for r in specs:
            if r.get('status') != 'ok':
                continue
            k = (r['split'], int(np.clip(np.floor(2 * np.log10(max(r['snr_r'], 0.1))), -2, 8)),
                 int(np.clip(np.floor(r['gmag']) if np.isfinite(r['gmag']) else 99, 0, 99)))
            a = agg.setdefault(k, [0, 0, []])
            a[0] += 1; a[1] += r['n_det']; a[2].append(r['ewerr_med_r'])
        rows = [dict(split=k[0], snr_bin=k[1], gbin=k[2], n_spec=v[0], n_det=v[1],
                     ewerr_r_med=float(np.nanmedian(v[2]))) for k, v in agg.items()]
        _write(os.path.join(out, f'spectragg_{sfx}.csv'), ['split', 'snr_bin', 'gbin', 'n_spec', 'n_det',
                                                           'ewerr_r_med'], rows)
        # Detektionen mit Sternmetadaten: nur Sterne mit Detektion
        tid = set((d['tile'], d['petal'], d['fiber']) for d in dets if d['kind'] == 'real')
        _write(os.path.join(out, f'spectra_{sfx}.csv'), SPEC_COLS,
               [r for r in specs if (r['tile'], r['petal'], r['fiber']) in tid])
    if not args.get('cache') and not args.get('keep_cache'):
        shutil.rmtree(cache, ignore_errors=True)
    n_fail = sum(1 for s in pstat if s['status'] == 'fail')
    return dict(job='desi_laser', n_tiles_all=n_all, n_tiles=len(tiles), n_petals=len(pstat), n_fail=n_fail,
                n_star_spec=sum(1 for r in specs if r.get('status') == 'ok'), n_sky=len(skys),
                n_det_real=n_det_raw, n_det_written=sum(1 for d in dets if d['kind'] == 'real'), n_inj=len(injs),
                n_lib=int(len(_LIB.TID)), t_pass1=round(t1 - t0, 1), t_lib=round(t2 - t1, 1),
                t_pass2=round(t3 - t2, 1), t_pass3=round(t4 - t3, 1), n_chi_files=n_chi_files, errors=errors[:5] + [s['error'] for s in pstat if s['error']][:5])
