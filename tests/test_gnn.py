from pathlib import Path

import pytest

pytest.importorskip("torch")

from cp2graph.api import parse_and_build_graph
from cp2graph.gnn import GraphEncoder, GraphPair, compare_graphs, graph_to_tensors, train_encoder


def _graph(name: str):
    return parse_and_build_graph(Path(__file__).parent / "models" / name)


def test_graph_to_tensors_has_expected_shape() -> None:
    graph = _graph("m01_arith.fzn")
    tensors = graph_to_tensors(graph)

    assert tensors.x.shape[0] == graph.number_of_nodes()
    assert tensors.x.shape[1] == 44
    assert tensors.edge_index.shape[0] == 2
    assert len(tensors.node_ids) == graph.number_of_nodes()


def test_graph_encoder_outputs_normalized_embedding() -> None:
    graph = _graph("m01_arith.fzn")
    model = GraphEncoder(hidden_dim=16, num_layers=1, dropout=0.0)
    embedding = model.encode_graph(graph)

    assert embedding.shape == (1, 16)
    assert pytest.approx(float(embedding.norm().item()), rel=1e-5) == 1.0


def test_train_encoder_returns_similarity_model() -> None:
    import torch

    torch.manual_seed(0)
    left = _graph("m01_arith.fzn")
    right = _graph("m03_all_diff.fzn")
    pairs = [GraphPair(left, left, 1.0), GraphPair(left, right, 0.0)]

    model, history = train_encoder(pairs, hidden_dim=16, num_layers=1, dropout=0.0, lr=0.01, epochs=3)

    assert len(history) == 3
    assert all(loss >= 0.0 for loss in history)
    assert history[-1] <= history[0]
    assert compare_graphs(model, left, left) > compare_graphs(model, left, right)
    assert -1.0 <= compare_graphs(model, left, right) <= 1.0
