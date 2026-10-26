"""Eigener HF-Lesehelfer (nur Lesen). Token wird zur Laufzeit aus der Umgebungsvariable HF_TOKEN gelesen,
nie ausgegeben oder gespeichert. Range-Requests auf die signierte CDN-URL (ohne Auth-Header).
Was tut die Schicht darunter im Fehlerfall schon selbst? requests wirft bei Netzfehlern; HTTP-Fehler
werden hier fail-closed als Ausnahme (ohne Header) gemeldet."""
import io
import os
import time
import requests

REPO = "aims-foundations/measurement-db"
BASE = "https://huggingface.co"


def _token():
    t = os.environ.get("HF_TOKEN", "").strip()
    if not t:  # fail-closed: ohne Token kein Zugriff auf den gated Datensatz
        raise HFError("HF_TOKEN is not set; accept the dataset's access conditions on Hugging Face and export HF_TOKEN")
    return t


def session(auth=True):
    s = requests.Session()
    s.headers["User-Agent"] = "paiec-datacheck/0.1"
    if auth:
        s.headers["Authorization"] = "Bearer " + _token()
    return s


class HFError(Exception):
    pass


def get_json(s, path, params=None, tries=4):
    url = BASE + path
    for i in range(tries):
        r = s.get(url, params=params, timeout=120)
        if r.status_code == 200:
            return r.json(), r.headers
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 * (i + 1))
            continue
        raise HFError(f"GET {path} -> HTTP {r.status_code}")
    raise HFError(f"GET {path} -> retries exhausted")


def resolve_url(rev, path):
    return f"{BASE}/datasets/{REPO}/resolve/{rev}/{path}"


class RangeFile(io.RawIOBase):
    """Seekbares Datei-Objekt über HTTP-Range. Merkt sich die signierte Ziel-URL nach dem Redirect."""

    def __init__(self, s, rev, path, size=None, block=1 << 20):
        self.s = s
        self.rev = rev
        self.path = path
        self.pos = 0
        self.block = block
        self.cache = {}
        self.bytes_fetched = 0
        self.n_requests = 0
        self.n_reresolve = 0
        self._resolve()
        if size is None:
            r2 = self._get(0, 0)
            cr = r2.headers.get("Content-Range", "")
            size = int(cr.split("/")[-1])
        self.size = size

    def _resolve(self):
        s, rev, path = self.s, self.rev, self.path
        r = s.get(resolve_url(rev, path), headers={"Range": "bytes=0-0"}, allow_redirects=False, timeout=120)
        if r.status_code in (301, 302, 303, 307, 308):
            self.url = r.headers["Location"]
            if self.url.startswith("/"):
                self.url = BASE + self.url
            self.signed = True
        elif r.status_code in (200, 206):
            self.url = resolve_url(rev, path)
            self.signed = False
        else:
            raise HFError(f"resolve {path} -> HTTP {r.status_code}")

    def _get(self, a, b, tries=5):
        for i in range(tries):
            hdr = {"Range": f"bytes={a}-{b}"}
            if self.signed:
                r = requests.get(self.url, headers=hdr, timeout=300)
            else:
                r = self.s.get(self.url, headers=hdr, timeout=300)
            if r.status_code == 206:
                self.n_requests += 1
                self.bytes_fetched += len(r.content)
                return r
            if r.status_code == 200 and a == 0:
                self.n_requests += 1
                self.bytes_fetched += len(r.content)
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            if r.status_code in (401, 403) and self.signed and self.n_reresolve < 20:
                # signierte CDN-URL abgelaufen -> neu auflösen
                self.n_reresolve += 1
                self._resolve()
                continue
            raise HFError(f"range {self.path} -> HTTP {r.status_code}")
        raise HFError(f"range {self.path} -> retries exhausted")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        if whence == 0:
            self.pos = off
        elif whence == 1:
            self.pos += off
        else:
            self.pos = self.size + off
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b""
        a = self.pos
        b = a + n - 1
        if n >= self.block:
            data = self._get(a, b).content[:n]
        else:
            bi = a // self.block
            bj = b // self.block
            parts = []
            for k in range(bi, bj + 1):
                if k not in self.cache:
                    lo = k * self.block
                    hi = min(self.size - 1, lo + self.block - 1)
                    if len(self.cache) >= getattr(self, "max_cache_blocks", 64):
                        self.cache.clear()
                    self.cache[k] = self._get(lo, hi).content
                parts.append(self.cache[k])
            buf = b"".join(parts)
            off = a - bi * self.block
            data = buf[off:off + n]
        self.pos += len(data)
        return data

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)
