from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import networkx as nx

from .hash_utils import semantic_hash

__all__ = [
    "GraphSimilarityConfig",
    "GraphSimilarityIndex",
    "GraphSimilarityResult",
    "GraphSummary",
    "label_jaccard_similarity",
    "passes_structural_filter",
    "score_graph_pair",
    "structural_compatibility_score",
    "wl_feature_counter",
    "wl_kernel_similarity",
]


def _safe_ratio(left: int, right: int) -> float:
    if left == 0 and right == 0:
        return 1.0
    if left == 0 or right == 0:
        return 0.0
    return min(left, right) / max(left, right)


def _bucket_degree(value: int) -> str:
    if value <= 1:
        return "d1"
    if value <= 3:
        return "d2_3"
    if value <= 7:
        return "d4_7"
    return "d8p"


def _bucket_size(value: float | int | None) -> str:
    if value is None:
        return "na"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "na"
    if num <= 1:
        return "s1"
    if num <= 4:
        return "s2_4"
    if num <= 16:
        return "s5_16"
    return "s17p"


def _undirected_neighbors(graph: nx.MultiDiGraph) -> Dict[str, List[Tuple[str, str]]]:
    neighbors: Dict[str, List[Tuple[str, str]]] = {node_id: [] for node_id in graph.nodes()}
    seen: set[Tuple[frozenset[str], str]] = set()
    for src, dst, data in graph.edges(data=True):
        role = str(data.get("role", "read"))
        key = (frozenset({str(src), str(dst)}), role)
        if key in seen:
            continue
        seen.add(key)
        neighbors[str(src)].append((role, str(dst)))
        neighbors[str(dst)].append((role, str(src)))
    for node_id in neighbors:
        neighbors[node_id].sort(key=lambda item: (item[0], item[1]))
    return neighbors


def _add_value_atoms(value: Any, atoms: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        atoms.add(f"bool:{str(value).lower()}")
        return
    if isinstance(value, (int, float)):
        atoms.add(f"num:{value}")
        return
    if isinstance(value, str):
        atoms.add(f"str:{value}")
        return
    if isinstance(value, list):
        for item in value:
            _add_value_atoms(item, atoms)
        return
    if isinstance(value, tuple):
        for item in value:
            _add_value_atoms(item, atoms)
        return
    if isinstance(value, dict):
        if "var" in value:
            return
        if "symbol" in value:
            atoms.add(f"symbol:{value['symbol']}")
        if "call" in value:
            atoms.add(f"call:{value['call']}")
            _add_value_atoms(value.get("args", []), atoms)
            return
        if "range" in value:
            rng = value.get("range")
            if isinstance(rng, list) and len(rng) == 2:
                atoms.add(f"range:{rng[0]}:{rng[1]}")
        for key, inner in value.items():
            if key in {"var", "symbol", "call", "args", "range"}:
                continue
            atoms.add(f"key:{key}")
            _add_value_atoms(inner, atoms)
        return
    atoms.add(f"repr:{value!r}")


def _node_atoms(data: Mapping[str, Any]) -> set[str]:
    atoms: set[str] = set()
    node_type = str(data.get("type") or "unknown")
    atoms.add(f"type:{node_type}")

    if node_type == "variable":
        domain = data.get("domain")
        if isinstance(domain, dict):
            kind = domain.get("kind")
            if kind:
                atoms.add(f"domain:{kind}")
            if domain.get("lower") is not None:
                atoms.add(f"lower:{domain['lower']}")
            if domain.get("upper") is not None:
                atoms.add(f"upper:{domain['upper']}")
            if domain.get("values") is not None:
                atoms.add(f"values:{semantic_hash(domain['values'])}")
        if data.get("is_objective"):
            atoms.add("objective:1")
        atoms.add(f"size:{_bucket_size(data.get('size'))}")
    elif node_type == "constraint":
        constraint_type = data.get("constraint_type")
        if constraint_type:
            atoms.add(f"constraint_type:{constraint_type}")
        params = data.get("params")
        _add_value_atoms(params, atoms)

    return atoms


def _node_seed_label(data: Mapping[str, Any], degree: int) -> str:
    node_type = str(data.get("type") or "unknown")
    parts = [f"type:{node_type}", f"degree:{_bucket_degree(degree)}"]
    if node_type == "variable":
        domain = data.get("domain")
        if isinstance(domain, dict) and domain.get("kind"):
            parts.append(f"domain:{domain['kind']}")
        if data.get("is_objective"):
            parts.append("objective:1")
    elif node_type == "constraint":
        constraint_type = data.get("constraint_type")
        if constraint_type:
            parts.append(f"constraint_type:{constraint_type}")
    return "|".join(parts)


def _cosine_counter(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(dot / (left_norm * right_norm))


@dataclass(frozen=True)
class GraphSimilarityConfig:
    wl_iterations: int = 2
    coarse_top_k: int = 64
    min_node_ratio: float = 0.45
    min_edge_ratio: float = 0.35
    min_type_ratio: float = 0.4
    max_node_gap: int = 30
    max_edge_gap: int = 80


@dataclass
class GraphSummary:
    node_count: int
    edge_count: int
    variable_count: int
    constraint_count: int
    atoms: frozenset[str]
    wl_features: Counter[str]

    @classmethod
    def from_graph(cls, graph: nx.MultiDiGraph, *, wl_iterations: int = 2) -> "GraphSummary":
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        variable_count = 0
        constraint_count = 0
        atoms: set[str] = set()
        for _node_id, data in graph.nodes(data=True):
            atoms.update(_node_atoms(data))
            if data.get("type") == "variable":
                variable_count += 1
            elif data.get("type") == "constraint":
                constraint_count += 1
        wl_features = wl_feature_counter(graph, iterations=wl_iterations)
        return cls(
            node_count=node_count,
            edge_count=edge_count,
            variable_count=variable_count,
            constraint_count=constraint_count,
            atoms=frozenset(atoms),
            wl_features=wl_features,
        )


@dataclass(frozen=True)
class GraphSimilarityResult:
    candidate_id: str
    structure_score: float
    wl_similarity: float
    jaccard_similarity: float
    fusion_score: float
    passed_filter: bool


def wl_feature_counter(graph: nx.MultiDiGraph, *, iterations: int = 2) -> Counter[str]:
    if iterations < 0:
        raise ValueError("iterations must be >= 0")

    neighbors = _undirected_neighbors(graph)
    labels: Dict[str, str] = {}
    for node_id, data in graph.nodes(data=True):
        degree = len(neighbors[str(node_id)])
        labels[str(node_id)] = _node_seed_label(data, degree)

    features: Counter[str] = Counter()
    for label in labels.values():
        features[label] += 1

    for _ in range(iterations):
        next_labels: Dict[str, str] = {}
        for node_id in graph.nodes():
            node_id = str(node_id)
            signature_parts = [labels[node_id]]
            for role, neighbor_id in neighbors[node_id]:
                signature_parts.append(f"{role}:{labels[neighbor_id]}")
            signature = "||".join(signature_parts)
            refined = semantic_hash(signature)
            next_labels[node_id] = refined
            features[refined] += 1
        labels = next_labels
    return features


def wl_kernel_similarity(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    return _cosine_counter(left, right)


def label_jaccard_similarity(left: GraphSummary, right: GraphSummary) -> float:
    if not left.atoms and not right.atoms:
        return 1.0
    union = left.atoms | right.atoms
    if not union:
        return 1.0
    intersection = left.atoms & right.atoms
    return len(intersection) / len(union)


def structural_compatibility_score(left: GraphSummary, right: GraphSummary) -> float:
    node_ratio = _safe_ratio(left.node_count, right.node_count)
    edge_ratio = _safe_ratio(left.edge_count, right.edge_count)
    variable_ratio = _safe_ratio(left.variable_count, right.variable_count)
    constraint_ratio = _safe_ratio(left.constraint_count, right.constraint_count)
    return float(0.35 * node_ratio + 0.20 * edge_ratio + 0.225 * variable_ratio + 0.225 * constraint_ratio)


def passes_structural_filter(left: GraphSummary, right: GraphSummary, config: GraphSimilarityConfig) -> bool:
    node_ratio = _safe_ratio(left.node_count, right.node_count)
    edge_ratio = _safe_ratio(left.edge_count, right.edge_count)
    variable_ratio = _safe_ratio(left.variable_count, right.variable_count)
    constraint_ratio = _safe_ratio(left.constraint_count, right.constraint_count)
    if node_ratio < config.min_node_ratio:
        return False
    if edge_ratio < config.min_edge_ratio:
        return False
    if variable_ratio < config.min_type_ratio:
        return False
    if constraint_ratio < config.min_type_ratio:
        return False
    if abs(left.node_count - right.node_count) > config.max_node_gap:
        return False
    if abs(left.edge_count - right.edge_count) > config.max_edge_gap:
        return False
    return True


def _fusion_score(structure_score: float, wl_score: float, jaccard_score: float) -> float:
    wl_weight = 0.55 + 0.25 * structure_score
    jaccard_weight = 1.0 - wl_weight
    return structure_score * (wl_weight * wl_score + jaccard_weight * jaccard_score)


def _score_summaries(
    left: GraphSummary,
    right: GraphSummary,
    config: GraphSimilarityConfig,
) -> GraphSimilarityResult:
    structure_score = structural_compatibility_score(left, right)
    wl_score = wl_kernel_similarity(left.wl_features, right.wl_features)
    jaccard_score = label_jaccard_similarity(left, right)
    fusion_score = _fusion_score(structure_score, wl_score, jaccard_score)
    return GraphSimilarityResult(
        candidate_id="",
        structure_score=structure_score,
        wl_similarity=wl_score,
        jaccard_similarity=jaccard_score,
        fusion_score=fusion_score,
        passed_filter=passes_structural_filter(left, right, config),
    )


def score_graph_pair(
    left: nx.MultiDiGraph,
    right: nx.MultiDiGraph,
    *,
    config: GraphSimilarityConfig | None = None,
) -> GraphSimilarityResult:
    config = config or GraphSimilarityConfig()
    left_summary = GraphSummary.from_graph(left, wl_iterations=config.wl_iterations)
    right_summary = GraphSummary.from_graph(right, wl_iterations=config.wl_iterations)
    return _score_summaries(left_summary, right_summary, config)


class GraphSimilarityIndex:
    def __init__(
        self,
        graphs: Mapping[str, nx.MultiDiGraph] | Sequence[Tuple[str, nx.MultiDiGraph]],
        *,
        config: GraphSimilarityConfig | None = None,
    ) -> None:
        self.config = config or GraphSimilarityConfig()
        if isinstance(graphs, Mapping):
            items = list(graphs.items())
        else:
            items = list(graphs)
        self._summaries: Dict[str, GraphSummary] = {
            key: GraphSummary.from_graph(graph, wl_iterations=self.config.wl_iterations)
            for key, graph in items
        }

    @property
    def keys(self) -> List[str]:
        return list(self._summaries.keys())

    def rank(
        self,
        query: nx.MultiDiGraph,
        *,
        top_k: int | None = None,
        coarse_top_k: int | None = None,
        candidate_keys: Sequence[str] | None = None,
    ) -> List[GraphSimilarityResult]:
        query_summary = GraphSummary.from_graph(query, wl_iterations=self.config.wl_iterations)
        if candidate_keys is None:
            candidate_keys = list(self._summaries.keys())

        coarse_limit = self.config.coarse_top_k if coarse_top_k is None else coarse_top_k
        scored: List[GraphSimilarityResult] = []
        for key in candidate_keys:
            summary = self._summaries[key]
            if not passes_structural_filter(query_summary, summary, self.config):
                continue
            result = _score_summaries(query_summary, summary, self.config)
            scored.append(
                GraphSimilarityResult(
                    candidate_id=key,
                    structure_score=result.structure_score,
                    wl_similarity=result.wl_similarity,
                    jaccard_similarity=result.jaccard_similarity,
                    fusion_score=result.fusion_score,
                    passed_filter=result.passed_filter,
                )
            )

        scored.sort(key=lambda item: item.wl_similarity, reverse=True)
        shortlisted = scored[:coarse_limit] if coarse_limit is not None else scored
        shortlisted.sort(key=lambda item: item.fusion_score, reverse=True)
        if top_k is not None:
            shortlisted = shortlisted[:top_k]
        return shortlisted
