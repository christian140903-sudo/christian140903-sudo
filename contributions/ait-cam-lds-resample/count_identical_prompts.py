"""
Count identical prompts among the repetitions of each attack step.

create_llm_prompt.py samples log lines only once per scenario variant and step,
so selecting the same variant in several repetitions results in identical
prompts (see README, section "Creating LLM Prompts"). This script counts for
every attack step how many of its prompts are distinct. If the log data and the
LLM responses are available, it also splits the steps with identical prompts by
log file length and splits the Same-Top-1 stability (column
percent_steps_all_runs_same_top1 of get_statistics.py) into steps with
identical and steps with varying prompts.

The script only reads files and uses nothing but the Python standard library.

Usage (from the repository root):

    python3 count_identical_prompts.py
    python3 count_identical_prompts.py --queries llm_queries_resampled.json
    python3 count_identical_prompts.py --csv prompt_repetitions.csv

Inputs:
    --queries    prompt file of create_llm_prompt.py or create_llm_prompt_resample.py
                 (default: llm_queries.json)
    --root       manifestations_filtered/steps; if the directory exists, the steps
                 with identical prompts are split into steps where all log files of
                 the selected variant have at most --max-lines lines (then all
                 lines are included and identical prompts cannot be avoided) and
                 steps with at least one longer log file
    --responses  llm_responses.json; if the file exists, Same-Top-1 is computed per
                 model as in get_statistics.py, for all steps and separately for
                 steps whose prompts in the response file are identical or vary

With the provided llm_queries.json and llm_responses.json and version 1 of
manifestations_filtered.zip (record 18390561, see "Getting the data"), the
output includes:

    Steps: 198, prompts: 990, distinct prompts: 393
    Steps with identical prompts in all repetitions: 89
      all log files of the selected variant have at most 10 lines: 21
      at least one log file of the selected variant has more than 10 lines: 68
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path):
    """Yield one JSON object per non-empty line."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def step_sort_key(key):
    """Sort (scenario, step) numerically where possible."""
    return tuple((0, int(x)) if x.isdigit() else (1, x) for x in key)


def group_prompts(queries_path):
    """Group prompts by attack step: {(scenario, step): [(variant, prompt), ...]}."""
    steps = defaultdict(list)
    for j in read_jsonl(queries_path):
        steps[(j["scenario"], j["step"])].append((j["variant"], j["prompt"]))
    return steps


def count_lines(path):
    """Count lines like sample_log_file() in create_llm_prompt.py reads them."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError as e:
        print(f"WARNING: Could not read file {path}: {e}")
        return 0


def longest_log_files(root_dir):
    """
    Length of the longest log file per attack step and scenario variant,
    considering the same files as collect_logs() in create_llm_prompt.py
    (no attacker hosts, no collectd.log, no empty files):
    {(scenario, step): {variant: lines}}
    """
    result = defaultdict(dict)
    for simulation_dir in sorted(d for d in root_dir.iterdir() if d.is_dir()):
        parts = simulation_dir.name.split("-")
        scenario_variant_parts = parts[0].split("_")
        scenario = scenario_variant_parts[0]
        variant = "_".join(scenario_variant_parts[1:])
        step = parts[1]
        longest = 0
        for host_dir in sorted(d for d in simulation_dir.iterdir() if d.is_dir()):
            if "attacker" in host_dir.name:
                continue
            for file_path in host_dir.rglob("*"):
                if not file_path.is_file() or file_path.name == "collectd.log":
                    continue
                longest = max(longest, count_lines(file_path))
        if longest > 0:
            result[(scenario, step)][variant] = longest
    return result


def top_level_techniques(response):
    """Predicted techniques as top-level IDs without duplicates, as in get_statistics.py."""
    techniques = response.get("techniques", []) if isinstance(response, dict) else []
    result = []
    for t in techniques or []:
        if t is None:
            continue
        t = str(t).strip().upper()
        if not t:
            continue
        t = t.split(".")[0]
        if t not in result:
            result.append(t)
    return result


def same_top1_by_step(responses_path):
    """
    For each model and step with at least two responses:
    {model_id: {(scenario, step): (all_runs_same_top1, prompts_identical)}}
    Runs are grouped by (model_id, scenario, step) as in get_statistics.py.
    """
    groups = defaultdict(list)
    for j in read_jsonl(responses_path):
        preds = top_level_techniques(j.get("response", {}))
        top1 = preds[0] if preds else "__MISSING__"
        groups[(j["canonical_slug"], j["scenario"], j["step"])].append((top1, j["prompt"]))
    result = defaultdict(dict)
    for (model_id, scenario, step), runs in groups.items():
        if len(runs) < 2:
            continue
        all_same = len(set(top1 for top1, _ in runs)) == 1
        identical = len(set(prompt for _, prompt in runs)) == 1
        result[model_id][(scenario, step)] = (all_same, identical)
    return result


def share(count, total):
    return f"{count}/{total} ({100.0 * count / total:.1f}%)" if total else "-"


def main():
    parser = argparse.ArgumentParser(
        description="Count identical prompts among the repetitions of each attack step."
    )
    parser.add_argument(
        "--queries",
        default="llm_queries.json",
        help="Prompt file (default: llm_queries.json)",
    )
    parser.add_argument(
        "--root",
        default="manifestations_filtered/steps",
        help="Root directory of steps, used if it exists (default: manifestations_filtered/steps)",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=10,
        help="Max number of lines per log file used for the prompts (default: 10)",
    )
    parser.add_argument(
        "--responses",
        default="llm_responses.json",
        help="LLM responses, used if the file exists (default: llm_responses.json)",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Write one row per step to this CSV file (default: None)",
    )
    args = parser.parse_args()

    steps = group_prompts(args.queries)
    keys = sorted(steps, key=step_sort_key)
    rows = []
    for key in keys:
        variants = [v for v, _ in steps[key]]
        prompts = [p for _, p in steps[key]]
        rows.append({
            "scenario": key[0],
            "step": key[1],
            "prompts": len(prompts),
            "distinct_prompts": len(set(prompts)),
            "distinct_variants_selected": len(set(variants)),
            "identical_prompts": int(len(prompts) >= 2 and len(set(prompts)) == 1),
        })
    identical = [r for r in rows if r["identical_prompts"]]

    print(f"Prompt file: {args.queries}")
    print(f"Steps: {len(rows)}, prompts: {sum(r['prompts'] for r in rows)}, "
          f"distinct prompts: {sum(r['distinct_prompts'] for r in rows)}")
    dist = Counter(r["distinct_prompts"] for r in rows)
    print("Distinct prompts per step: " + ", ".join(f"{k}: {dist[k]}" for k in sorted(dist)))
    print("Steps with as many distinct prompts as distinct variants selected: "
          f"{sum(1 for r in rows if r['distinct_prompts'] == r['distinct_variants_selected'])}")
    print(f"Steps with identical prompts in all repetitions: {len(identical)}")

    root_dir = Path(args.root).expanduser()
    if root_dir.is_dir() and args.max_lines > 0:
        longest = longest_log_files(root_dir)
        for r, key in zip(rows, keys):
            selected = set(v for v, _ in steps[key])
            r["variants_with_logs"] = len(longest.get(key, {}))
            r["longest_log_file_lines"] = max(longest.get(key, {}).get(v, 0) for v in selected)
            r["identical_although_longer_file"] = int(
                r["identical_prompts"] == 1 and r["longest_log_file_lines"] > args.max_lines
            )
        single = sum(1 for r in identical if r["variants_with_logs"] == 1)
        longer = sum(r["identical_although_longer_file"] for r in identical)
        print(f"  logs from a single scenario variant: {single}")
        print(f"  all log files of the selected variant have at most {args.max_lines} lines: "
              f"{len(identical) - longer}")
        print(f"  at least one log file of the selected variant has more than {args.max_lines} lines: "
              f"{longer}")
    else:
        print(f"  (log file lengths not counted: {args.root} not found or --max-lines < 1)")

    if Path(args.responses).is_file():
        stability = same_top1_by_step(args.responses)
        print()
        print(f"Same-Top-1 per model ({args.responses})")
        header = ["model_id", "all steps", "identical prompts", "varying prompts"]
        table = []
        for model_id in sorted(stability):
            values = stability[model_id].values()
            same_ident = [s for s, i in values if i]
            same_vary = [s for s, i in values if not i]
            table.append([
                model_id,
                share(sum(s for s, _ in values), len(values)),
                share(sum(same_ident), len(same_ident)),
                share(sum(same_vary), len(same_vary)),
            ])
            for r, key in zip(rows, keys):
                if key in stability[model_id]:
                    r["same_top1:" + model_id] = int(stability[model_id][key][0])
        widths = [max(len(str(x[c])) for x in [header] + table) for c in range(len(header))]
        for line in [header] + table:
            print(" | ".join(str(x).ljust(w) for x, w in zip(line, widths)).rstrip())

    if args.csv:
        fieldnames = []
        for r in rows:
            fieldnames += [k for k in r if k not in fieldnames]
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nWrote {len(rows)} rows to {args.csv}")


if __name__ == "__main__":
    main()
