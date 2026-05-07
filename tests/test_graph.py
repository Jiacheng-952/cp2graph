from pathlib import Path

from cp2graph.graph_builder import build_constraint_graph
from cp2graph.normalize import normalize_model
from cp2graph.parser import FlatZincParser
from cp2graph.serialize import graph_to_json_obj


def _model(name: str):
    parser = FlatZincParser()
    p = Path(__file__).parent / "models" / name
    return normalize_model(parser.parse_file(p))


def test_graph_has_required_fields() -> None:
    g = build_constraint_graph(_model("m01_arith.fzn"))
    payload = graph_to_json_obj(g)
    assert "nodes" in payload and "edges" in payload
    assert payload["nodes"]
    assert payload["edges"]
    node = payload["nodes"][0]
    assert {"id", "type", "domain", "size", "semantic_hash"} <= set(node.keys())


def test_element_has_write_role() -> None:
    g = build_constraint_graph(_model("m04_element.fzn"))
    write_edges = [d for _, _, _, d in g.edges(keys=True, data=True) if d.get("role") == "write"]
    assert write_edges, "element约束应至少包含一个write角色边"


def test_redundant_constraint_merged() -> None:
    m = _model("m11_redundant.fzn")
    assert len(m.constraints) == 1
