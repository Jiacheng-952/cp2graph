from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Sequence

import networkx as nx

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise RuntimeError("cp2graph.gnn requires PyTorch. Install cp2graph[ml] or torch.") from exc

__all__ = [
    "GraphEncoder",
    "GraphPair",
    "GraphTensor",
    "compare_graphs",
    "cosine_similarity",
    "graph_to_tensors",
    "train_encoder",
]

def _stable_bucket(value: str, buckets: int) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % buckets


def _float_size(value: object) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class GraphTensor:
    x: object
    edge_index: object
    node_ids: List[str]


def graph_to_tensors(graph: nx.MultiDiGraph, *, bucket_dim: int = 32):
    node_ids = list(graph.nodes())
    index = {node_id: i for i, node_id in enumerate(node_ids)}

    feature_dim = 12 + bucket_dim
    x = torch.zeros((len(node_ids), feature_dim), dtype=torch.float32)

    for node_id, data in graph.nodes(data=True):
        row = index[node_id]
        node_type = data.get("type")
        domain = data.get("domain") or {}
        size = _float_size(data.get("size"))
        semantic_hash = str(data.get("semantic_hash") or "")
        constraint_type = str(data.get("constraint_type") or "")

        if node_type == "variable":
            x[row, 0] = 1.0
        elif node_type == "constraint":
            x[row, 1] = 1.0

        domain_kind = domain.get("kind") if isinstance(domain, dict) else None
        domain_kinds = {"bool": 0, "int-set": 1, "int-bounds": 2, "float-bounds": 3}
        if domain_kind in domain_kinds:
            x[row, 2 + domain_kinds[domain_kind]] = 1.0

        bucket_source = constraint_type if constraint_type else semantic_hash
        x[row, 6] = 1.0 if data.get("is_objective") else 0.0
        x[row, 7] = size
        x[row, 8] = float(size) ** 0.5 if size > 0.0 else 0.0
        x[row, 9] = float(len(graph.in_edges(node_id)))
        x[row, 10] = float(len(graph.out_edges(node_id)))
        x[row, 11] = 1.0 if bucket_source else 0.0
        if bucket_source:
            x[row, 12 + _stable_bucket(bucket_source, bucket_dim)] = 1.0

    edge_pairs: List[List[int]] = []
    for src, dst, _key in graph.edges(keys=True):
        edge_pairs.append([index[src], index[dst]])
    if edge_pairs:
        edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)

    return GraphTensor(x=x, edge_index=edge_index, node_ids=node_ids)


class GCNLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)

    def forward(self, x, edge_index):
        num_nodes = x.size(0)
        if edge_index.numel() == 0:
            out = self.linear(x)
            return out

        self_loops = torch.arange(num_nodes, device=x.device)
        loop_index = torch.stack([self_loops, self_loops], dim=0)
        edge_index = torch.cat([edge_index, loop_index], dim=1)

        row, col = edge_index
        deg = torch.bincount(row, minlength=num_nodes).float()
        deg_inv_sqrt = deg.clamp(min=1.0).pow(-0.5)
        norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]

        agg = x.new_zeros((num_nodes, x.size(1)))
        agg.index_add_(0, row, x[col] * norm.unsqueeze(-1))
        return self.linear(agg)


class GraphEncoder(nn.Module):
    def __init__(
        self,
        bucket_dim: int = 32,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()

        if num_layers < 1:
            raise ValueError("num_layers must be >= 1")
        self.bucket_dim = bucket_dim
        input_dim = 12 + bucket_dim
        self.hidden_dim = hidden_dim
        self.dropout = dropout
        self.activation = F.relu
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.layers = nn.ModuleList([GCNLayer(hidden_dim, hidden_dim) for _ in range(num_layers)])
        self.output_proj = nn.Linear(hidden_dim * 2, hidden_dim)

    def _pool(self, x):
        mean_pool = x.mean(dim=0, keepdim=True)
        max_pool = x.max(dim=0, keepdim=True).values
        return torch.cat([mean_pool, max_pool], dim=-1)

    def forward(self, x, edge_index):
        h = self.input_proj(x)
        h = self.activation(h)
        for layer in self.layers:
            h = layer(h, edge_index)
            h = self.activation(h)
            if self.dropout:
                h = torch.nn.functional.dropout(h, p=self.dropout, training=self.training)
        pooled = self._pool(h)
        emb = self.output_proj(pooled)
        return torch.nn.functional.normalize(emb, dim=-1)

    def encode_graph(self, graph: nx.MultiDiGraph):
        tensors = graph_to_tensors(graph, bucket_dim=self.bucket_dim)
        device = next(self.parameters()).device
        return self.forward(tensors.x.to(device), tensors.edge_index.to(device))


@dataclass(frozen=True)
class GraphPair:
    left: nx.MultiDiGraph
    right: nx.MultiDiGraph
    label: float


def cosine_similarity(a, b):
    return torch.nn.functional.cosine_similarity(a, b)


def compare_graphs(model: GraphEncoder, left: nx.MultiDiGraph, right: nx.MultiDiGraph) -> float:
    was_training = model.training
    model.eval()
    with torch.no_grad():
        emb_left = model.encode_graph(left)
        emb_right = model.encode_graph(right)
        score = torch.nn.functional.cosine_similarity(emb_left, emb_right).item()
    if was_training:
        model.train(True)
    return float(score)


def train_encoder(
    pairs: Sequence[GraphPair],
    *,
    bucket_dim: int = 32,
    hidden_dim: int = 64,
    num_layers: int = 2,
    dropout: float = 0.1,
    lr: float = 1e-3,
    epochs: int = 20,
    temperature: float = 0.1,
    device: str = "cpu",
):
    model = GraphEncoder(bucket_dim=bucket_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout)
    model.to(device)

    optimizer = torch.optim.Adam(list(model.parameters()), lr=lr)
    criterion = nn.BCEWithLogitsLoss()
    history: List[float] = []

    for _epoch in range(epochs):
        model.train(True)
        total = 0.0
        count = 0
        for pair in pairs:
            left = graph_to_tensors(pair.left, bucket_dim=bucket_dim)
            right = graph_to_tensors(pair.right, bucket_dim=bucket_dim)
            x_left = left.x.to(device)
            e_left = left.edge_index.to(device)
            x_right = right.x.to(device)
            e_right = right.edge_index.to(device)
            y = torch.tensor([float(pair.label)], dtype=torch.float32, device=device)

            z_left = model.forward(x_left, e_left)
            z_right = model.forward(x_right, e_right)
            logit = cosine_similarity(z_left, z_right) / temperature
            loss = criterion(logit.view_as(y), y)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total += float(loss.item())
            count += 1
        history.append(total / max(count, 1))

    model.eval()
    return model, history
