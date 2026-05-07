from pathlib import Path

from cp2graph import graph_fingerprint, parse_model_text_to_graph
from cp2graph.serialize import write_graph_json


def main() -> None:
    fzn_text = """
var 0..10: x;
var 0..10: y;
constraint int_lin_eq([1,2],[x,y],7);
solve satisfy;
""".strip()

    graph = parse_model_text_to_graph(fzn_text, normalize=True)
    out = Path("examples") / "minimal_graph.json"
    write_graph_json(graph, out)

    print("nodes =", graph.number_of_nodes())
    print("edges =", graph.number_of_edges())
    print("hash  =", graph_fingerprint(graph))
    print("json  =", out.resolve())


if __name__ == "__main__":
    main()
