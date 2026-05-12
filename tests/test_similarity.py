from pathlib import Path

import pytest

from cp2graph.api import parse_and_build_graph, parse_model_text_to_graph
from cp2graph.similarity import (
    GraphSimilarityConfig,
    GraphSimilarityIndex,
    GraphSummary,
    passes_structural_filter,
    score_graph_pair,
)


def _graph(name: str):
    return parse_and_build_graph(Path(__file__).parent / "models" / name)


def test_score_graph_pair_is_perfect_on_identical_graphs() -> None:
    graph = _graph("m01_arith.fzn")
    score = score_graph_pair(graph, graph)

    assert pytest.approx(score.wl_similarity, rel=1e-6) == 1.0
    assert pytest.approx(score.jaccard_similarity, rel=1e-6) == 1.0
    assert pytest.approx(score.fusion_score, rel=1e-6) == score.structure_score
    assert score.passed_filter is True


def test_similarity_index_ranks_self_first() -> None:
    left = _graph("m01_arith.fzn")
    middle = _graph("m03_all_diff.fzn")
    right = _graph("m04_element.fzn")
    index = GraphSimilarityIndex({"left": left, "middle": middle, "right": right})

    results = index.rank(middle, top_k=1)

    assert results
    assert results[0].candidate_id == "middle"
    assert results[0].fusion_score >= 0.0


def test_structural_filter_rejects_large_shape_gap() -> None:
    small = parse_model_text_to_graph(
        """
        var 0..1: x;
        constraint int_le(x, 1);
        solve satisfy;
        """.strip(),
        normalize=True,
    )
    large = parse_model_text_to_graph(
        """
        var 0..10: x;
        var 0..10: y;
        var 0..10: z;
        var 0..10: w;
        constraint int_lin_eq([1,1,1,1],[x,y,z,w],10);
        constraint int_le(x, 1);
        constraint int_le(y, 2);
        constraint int_le(z, 3);
        constraint int_le(w, 4);
        solve satisfy;
        """.strip(),
        normalize=True,
    )

    config = GraphSimilarityConfig(min_node_ratio=0.8, min_edge_ratio=0.8, min_type_ratio=0.8, max_node_gap=0, max_edge_gap=0)
    small_summary = GraphSummary.from_graph(small, wl_iterations=config.wl_iterations)
    large_summary = GraphSummary.from_graph(large, wl_iterations=config.wl_iterations)

    assert passes_structural_filter(small_summary, large_summary, config) is False

