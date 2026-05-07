from pathlib import Path

from cp2graph.api import graph_fingerprint, parse_model_text_to_graph


def _load(name: str) -> str:
    return (Path(__file__).parent / "models" / name).read_text(encoding="utf-8")


def test_equivalent_models_same_hash() -> None:
    g1 = parse_model_text_to_graph(_load("m13_sym_a.fzn"), normalize=True)
    g2 = parse_model_text_to_graph(_load("m14_sym_b.fzn"), normalize=True)
    assert graph_fingerprint(g1) == graph_fingerprint(g2)


def test_non_equivalent_models_diff_hash() -> None:
    g1 = parse_model_text_to_graph(_load("m15_diff_hash_1.fzn"), normalize=True)
    g2 = parse_model_text_to_graph(_load("m16_diff_hash_2.fzn"), normalize=True)
    assert graph_fingerprint(g1) != graph_fingerprint(g2)
