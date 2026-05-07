from __future__ import annotations

import argparse
import random

from cp2graph.api import graph_fingerprint, parse_model_text_to_graph
from cp2graph.serialize import graph_to_json_obj


def random_model(rng: random.Random) -> str:
    lo = 0
    hi = rng.randint(3, 20)
    rhs = rng.randint(lo, hi)
    ctype = rng.choice(["int_eq", "int_le", "int_ne"])
    return (
        f"var {lo}..{hi}: x;\n"
        f"var {lo}..{hi}: y;\n"
        f"constraint {ctype}(x,{rhs});\n"
        f"constraint int_le(y,{rng.randint(lo, hi)});\n"
        "solve satisfy;\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    seen = {}
    collisions = 0
    for _ in range(args.samples):
        g = parse_model_text_to_graph(random_model(rng))
        h = graph_fingerprint(g)
        payload = str(graph_to_json_obj(g))
        if h in seen and seen[h] != payload:
            collisions += 1
        else:
            seen[h] = payload

    print(f"samples={args.samples} collisions={collisions}")
    if collisions > 0:
        raise SystemExit(f"Detected {collisions} hash collisions")


if __name__ == "__main__":
    main()
