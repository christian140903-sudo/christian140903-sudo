"""Dispatcher: python -m tsjobs.run --config jobs/current.json --shard i --nshards n --out DIR"""
import argparse, importlib, json, os, platform, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--shard', type=int, required=True)
    ap.add_argument('--nshards', type=int, required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    mod = importlib.import_module(f"tsjobs.{cfg['job']}")
    stats = mod.run(cfg.get('args', {}), a.shard, a.nshards, a.out) or {}
    stats.update(shard=a.shard, nshards=a.nshards, seconds=round(time.time() - t0, 1),
                 cpus=os.cpu_count(), python=platform.python_version())
    with open(os.path.join(a.out, f'meta_{a.shard:04d}.json'), 'w') as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
