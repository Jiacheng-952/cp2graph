from pathlib import Path

from cp2graph.api import graph_fingerprint, parse_and_build_graph, parse_model_text_to_graph


def test_parse_and_build_graph_from_fzn(tmp_path: Path) -> None:
    src = Path(__file__).parent / "models" / "m01_arith.fzn"
    target = tmp_path / "m.fzn"
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    g = parse_and_build_graph(target)
    assert g.number_of_nodes() > 0
    assert graph_fingerprint(g)


def test_parse_and_build_graph_from_mzn_via_compile(monkeypatch) -> None:
    fake_fzn = "var 0..3: x;\nconstraint int_le(x,2);\nsolve satisfy;\n"

    monkeypatch.setattr("cp2graph.api.compile_minizinc_to_fzn", lambda _: fake_fzn)
    g = parse_and_build_graph("dummy.mzn")
    assert g.number_of_nodes() >= 2


def test_parse_model_text_without_normalize() -> None:
    text = "var 0..3: x;\nconstraint int_le(x,2);\nsolve satisfy;\n"
    g = parse_model_text_to_graph(text, normalize=False)
    assert g.number_of_edges() >= 2
