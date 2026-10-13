"""Dispatcher: python -m tsjobs.run --config jobs/current.json --shard i --nshards n --out DIR"""
import argparse, importlib, json, os, platform, sys, time


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
    # Teil-Shard (Wächter/Gesamtfrist, desi_laser): Ausgaben sind geschrieben, aber unvollständig -> Job rot, damit
    # die Nachlauf-Liste (alle work-Jobs != success) ihn mechanisch erfasst; Upload und gather laufen mit always()
    part = {k: stats[k] for k in ('pool_timeouts', 'shard_deadline') if stats.get(k)}
    if part:
        print(f"::error title=Teil-Shard {a.shard}::Ausgaben geschrieben, aber unvollstaendig: {json.dumps(part)}",
              flush=True)
        sys.exit(3)


if __name__ == '__main__':
    main()
