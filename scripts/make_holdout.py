#!/usr/bin/env python3
"""Generate reproducible disjoint MultiHop query indices; run BEFORE algorithm tuning."""
import argparse
import json
import random
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=2556)
    p.add_argument("--seed", type=int, default=20261014)
    p.add_argument("--output", default="configs/multihop_split_indices.json")
    args = p.parse_args()
    ids = list(range(args.n))
    random.Random(args.seed).shuffle(ids)
    a = int(args.n * .60)
    b = int(args.n * .80)
    obj = {"seed": args.seed, "n": args.n, "dev_indices": sorted(ids[:a]),
           "validation_indices": sorted(ids[a:b]), "test_indices": sorted(ids[b:])}
    path = Path(args.output)
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print(f"wrote {path}: dev={a}, validation={b-a}, test={args.n-b}")


if __name__ == "__main__":
    main()
