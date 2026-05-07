from pathlib import Path

from cp2graph.normalize import normalize_model
from cp2graph.parser import FlatZincParser


def test_parse_20_models() -> None:
    parser = FlatZincParser()
    model_dir = Path(__file__).parent / "models"
    files = sorted(model_dir.glob("*.fzn"))
    assert len(files) >= 20
    for f in files:
        model = parser.parse_file(f)
        assert len(model.variables) >= 1
        norm = normalize_model(model)
        assert all(c.semantic_hash for c in norm.constraints)


def test_deterministic_parse_graph_counts() -> None:
    parser = FlatZincParser()
    content = (Path(__file__).parent / "models" / "m12_array_reuse.fzn").read_text(encoding="utf-8")
    m1 = normalize_model(parser.parse_text(content))
    m2 = normalize_model(parser.parse_text(content))
    assert len(m1.variables) == len(m2.variables)
    assert len(m1.constraints) == len(m2.constraints)
    assert [c.semantic_hash for c in m1.constraints] == [c.semantic_hash for c in m2.constraints]
