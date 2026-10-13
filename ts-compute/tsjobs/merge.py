"""Fasst Shard-Artefakte zusammen: '<name>_<shard>.csv' wird je Name aneinandergehängt, Meta-JSONs gesammelt."""
import csv, glob, json, os, sys

src, dest = sys.argv[1], sys.argv[2]
os.makedirs(dest, exist_ok=True)
groups = {}
for path in sorted(glob.glob(os.path.join(src, 'shard-*', '*.csv'))):
    name = os.path.basename(path).rsplit('_', 1)[0] + '.csv'
    groups.setdefault(name, []).append(path)
for name, paths in groups.items():
    with open(os.path.join(dest, name), 'w', newline='') as out:
        w = csv.writer(out)
        header_done = False
        for p in paths:
            with open(p, newline='') as f:
                rows = list(csv.reader(f))
            if not rows:
                continue
            if not header_done:
                w.writerow(rows[0])
                header_done = True
            w.writerows(rows[1:])
metas = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(src, 'shard-*', 'meta_*.json')))]
json.dump(metas, open(os.path.join(dest, 'shards_meta.json'), 'w'), indent=1)
# Diagnose abgebrochener Shards (desi_laser abort_<s>.json) sonst nur 7 Tage im Artefakt; Datei nur, wenn vorhanden
aborts = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(src, 'shard-*', 'abort_*.json')))]
if aborts:
    json.dump(aborts, open(os.path.join(dest, 'shards_abort.json'), 'w'), indent=1)
print(f'merged {sum(len(v) for v in groups.values())} csv files into {len(groups)}, {len(metas)} shard metas')
