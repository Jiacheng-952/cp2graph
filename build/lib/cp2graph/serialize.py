from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import networkx as nx


def graph_to_json_obj(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    nodes = []
    for _nid, data in graph.nodes(data=True):
        nodes.append(
            {
                "id": data.get("id"),
                "type": data.get("type"),
                "domain": data.get("domain"),
                "size": data.get("size"),
                "semantic_hash": data.get("semantic_hash"),
            }
        )

    edges = []
    for src, dst, _k, data in graph.edges(keys=True, data=True):
        edges.append({"src": src, "dst": dst, "role": data.get("role", "read")})

    nodes.sort(key=lambda x: (x["type"], x["id"]))
    edges.sort(key=lambda x: (x["src"], x["dst"], x["role"]))
    return {"nodes": nodes, "edges": edges}


def write_graph_json(graph: nx.MultiDiGraph, output_path: str | Path) -> None:
    payload = graph_to_json_obj(graph)
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=False), encoding="utf-8")


def write_graph_graphml(graph: nx.MultiDiGraph, output_path: str | Path) -> None:
    g = graph.copy()
    for node_id in list(g.nodes()):
        data = g.nodes[node_id]
        for key in ["domain", "params"]:
            if key in data and data[key] is not None and not isinstance(data[key], str):
                data[key] = json.dumps(data[key], ensure_ascii=True, sort_keys=True)
        for k, v in list(data.items()):
            if v is None:
                data[k] = ""
    for src, dst, key in list(g.edges(keys=True)):
        data = g[src][dst][key]
        for k, v in list(data.items()):
            if v is None:
                data[k] = ""
    nx.write_graphml(g, output_path)
