from __future__ import annotations

import argparse
from pathlib import Path

from .api import graph_fingerprint, parse_and_build_graph
from .serialize import write_graph_graphml, write_graph_json


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cp2graph", description="Convert CP model (FlatZinc/MiniZinc) to constraint bipartite graph")
    parser.add_argument("model", help="Path to .fzn or .mzn model file")
    parser.add_argument("-o", "--output", required=True, help="Output graph file path")
    parser.add_argument("--format", choices=["json", "graphml"], default=None, help="Output format; inferred from extension if omitted")
    parser.add_argument("--hash", action="store_true", help="Print final graph semantic hash")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    model_path = Path(args.model)
    output = Path(args.output)
    fmt = args.format or output.suffix.lower().lstrip(".")
    if fmt not in {"json", "graphml"}:
        raise SystemExit("Unsupported output format. Use --format json|graphml or output extension .json/.graphml")

    graph = parse_and_build_graph(model_path)
    if fmt == "json":
        write_graph_json(graph, output)
    else:
        write_graph_graphml(graph, output)

    if args.hash:
        print(graph_fingerprint(graph))


if __name__ == "__main__":
    main()
