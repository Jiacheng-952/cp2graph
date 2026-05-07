from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

import networkx as nx

from .graph_builder import build_constraint_graph
from .models import CPModelIR


@dataclass
class IncrementalState:
    graph: nx.MultiDiGraph
    constraint_hash_to_id: Dict[str, str]


def create_state(model: CPModelIR) -> IncrementalState:
    graph = build_constraint_graph(model)
    mapping = {c.semantic_hash: c.id for c in model.constraints}
    return IncrementalState(graph=graph, constraint_hash_to_id=mapping)


def update_state(prev: IncrementalState, new_model: CPModelIR) -> IncrementalState:
    next_graph = prev.graph.copy()
    new_map = {c.semantic_hash: c.id for c in new_model.constraints}

    prev_hashes: Set[str] = set(prev.constraint_hash_to_id.keys())
    next_hashes: Set[str] = set(new_map.keys())
    removed = prev_hashes - next_hashes
    added = next_hashes - prev_hashes

    for h in removed:
        cid = prev.constraint_hash_to_id[h]
        if cid in next_graph:
            next_graph.remove_node(cid)

    rebuilt = build_constraint_graph(new_model)
    for h in added:
        cid = new_map[h]
        next_graph.add_node(cid, **rebuilt.nodes[cid])
        for src, _dst, _k, data in rebuilt.in_edges(cid, data=True, keys=True):
            next_graph.add_edge(src, cid, **data)
        for _src, dst, _k, data in rebuilt.out_edges(cid, data=True, keys=True):
            next_graph.add_edge(cid, dst, **data)

    for vid in list(next_graph.nodes()):
        if next_graph.nodes[vid].get("type") == "variable" and vid not in new_model.variables:
            next_graph.remove_node(vid)
    for vid, v in new_model.variables.items():
        if vid not in next_graph:
            next_graph.add_node(
                vid,
                id=vid,
                type="variable",
                name=v.name,
                domain=v.domain.to_json(),
                size=v.domain.size,
                semantic_hash=None,
                is_objective=v.is_objective,
            )

    return IncrementalState(graph=next_graph, constraint_hash_to_id=new_map)
