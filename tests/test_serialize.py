import json
from pathlib import Path

from cp2graph.normalize import normalize_model
from cp2graph.parser import FlatZincParser
from cp2graph.graph_builder import build_constraint_graph
from cp2graph.serialize import write_graph_graphml, write_graph_json


def test_write_json_and_graphml(tmp_path: Path) -> None:
    parser = FlatZincParser()
    model = normalize_model(parser.parse_file(Path(__file__).parent / "models" / "m12_array_reuse.fzn"))
    g = build_constraint_graph(model)

    json_path = tmp_path / "g.json"
    graphml_path = tmp_path / "g.graphml"
    write_graph_json(g, json_path)
    write_graph_graphml(g, graphml_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["nodes"]
    assert graphml_path.exists()
