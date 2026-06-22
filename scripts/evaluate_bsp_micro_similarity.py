from __future__ import annotations

import argparse
import copy
import csv
import json
import random
from pathlib import Path
from typing import Any, Dict, List

import networkx as nx

from cp2graph.hash_utils import semantic_hash
from cp2graph.similarity import GraphSimilarityConfig, GraphSimilarityIndex


BSP_CATEGORY = "Batch Scheduling Problem"


def load_graph_json(path: Path) -> nx.MultiDiGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.MultiDiGraph()
    for node in payload.get("nodes", []):
        graph.add_node(node["id"], **node)
    for edge in payload.get("edges", []):
        graph.add_edge(
            edge["src"],
            edge["dst"],
            src=edge["src"],
            dst=edge["dst"],
            role=edge.get("role", "read"),
        )
    return graph


def graph_to_json_obj(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    nodes = [dict(data) for _node_id, data in graph.nodes(data=True)]
    edges = [
        {"src": src, "dst": dst, "role": data.get("role", "read")}
        for src, dst, _key, data in graph.edges(keys=True, data=True)
    ]
    nodes.sort(key=lambda item: (item.get("type") or "", item.get("id") or ""))
    edges.sort(key=lambda item: (item["src"], item["dst"], item["role"]))
    return {"nodes": nodes, "edges": edges}


def write_graph_json(graph: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph_to_json_obj(graph), ensure_ascii=False, indent=2), encoding="utf-8")


def _numeric_suffix(node_id: str) -> int:
    try:
        return int(node_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return -1


def _next_id(graph: nx.MultiDiGraph, prefix: str, offset: int = 1) -> str:
    max_seen = max((_numeric_suffix(str(node_id)) for node_id in graph.nodes if str(node_id).startswith(prefix)), default=-1)
    return f"{prefix}{max_seen + offset:05d}"


def _variable_nodes(graph: nx.MultiDiGraph) -> List[str]:
    return sorted([node_id for node_id, data in graph.nodes(data=True) if data.get("type") == "variable"])


def _constraint_nodes(graph: nx.MultiDiGraph) -> List[str]:
    return sorted([node_id for node_id, data in graph.nodes(data=True) if data.get("type") == "constraint"])


def _add_bidirectional_edge(graph: nx.MultiDiGraph, var_id: str, constraint_id: str, role: str = "read") -> None:
    graph.add_edge(var_id, constraint_id, src=var_id, dst=constraint_id, role=role)
    graph.add_edge(constraint_id, var_id, src=constraint_id, dst=var_id, role=role)


def _add_local_linear_constraint(graph: nx.MultiDiGraph, rng: random.Random, variant_index: int) -> Dict[str, Any]:
    variables = _variable_nodes(graph)
    chosen = sorted(rng.sample(variables, k=min(3, len(variables))))
    constraint_id = _next_id(graph, "c_")
    payload = {
        "linear": {
            "vars": [_numeric_suffix(var_id) for var_id in chosen],
            "coeffs": ["1" for _ in chosen],
            "domain": ["0", str(variant_index % 5 + len(chosen))],
            "micro_variant": variant_index,
        }
    }
    graph.add_node(
        constraint_id,
        id=constraint_id,
        type="constraint",
        name=None,
        domain=None,
        size=None,
        semantic_hash=semantic_hash({"type": "linear", "payload": payload}),
        constraint_type="linear",
        params=payload,
        is_objective=False,
    )
    for var_id in chosen:
        _add_bidirectional_edge(graph, var_id, constraint_id)
    return {"operation": "add_local_linear_constraint", "constraint_id": constraint_id, "variables": chosen}


def _add_bool_guard_subgraph(graph: nx.MultiDiGraph, rng: random.Random, variant_index: int) -> Dict[str, Any]:
    variables = _variable_nodes(graph)
    anchor = rng.choice(variables)
    var_id = _next_id(graph, "v_")
    constraint_id = _next_id(graph, "c_")
    graph.add_node(
        var_id,
        id=var_id,
        type="variable",
        name=f"micro_guard_{variant_index}",
        domain={"kind": "bool", "values": None, "lower": 0, "upper": 1},
        size=2.0,
        semantic_hash=None,
        is_objective=False,
    )
    payload = {
        "bool_or": {
            "literals": [_numeric_suffix(var_id), _numeric_suffix(anchor)],
            "micro_variant": variant_index,
        }
    }
    graph.add_node(
        constraint_id,
        id=constraint_id,
        type="constraint",
        name=None,
        domain=None,
        size=None,
        semantic_hash=semantic_hash({"type": "bool_or", "payload": payload}),
        constraint_type="bool_or",
        params=payload,
        is_objective=False,
    )
    _add_bidirectional_edge(graph, var_id, constraint_id)
    _add_bidirectional_edge(graph, anchor, constraint_id)
    return {"operation": "add_bool_guard_subgraph", "constraint_id": constraint_id, "variables": [var_id, anchor]}


def _retag_small_constraint(graph: nx.MultiDiGraph, rng: random.Random, variant_index: int) -> Dict[str, Any]:
    candidates = _constraint_nodes(graph)
    constraint_id = rng.choice(candidates)
    data = dict(graph.nodes[constraint_id])
    params = copy.deepcopy(data.get("params") or {})
    if isinstance(params, dict):
        params["micro_note"] = {"variant": variant_index, "kind": "retag"}
    data["params"] = params
    data["semantic_hash"] = semantic_hash({"type": data.get("constraint_type"), "payload": params})
    graph.nodes[constraint_id].update(data)
    return {"operation": "retag_small_constraint", "constraint_id": constraint_id}


def make_micro_variant(base: nx.MultiDiGraph, variant_index: int, rng: random.Random) -> tuple[nx.MultiDiGraph, List[Dict[str, Any]]]:
    graph = copy.deepcopy(base)
    operations = [_add_local_linear_constraint]
    if variant_index % 2 == 0:
        operations.append(_add_bool_guard_subgraph)
    if variant_index % 3 == 0:
        operations.append(_retag_small_constraint)

    changes = []
    for operation in operations:
        changes.append(operation(graph, rng, variant_index))
    return graph, changes


def load_conversion_records(dataset_root: Path) -> List[Dict[str, Any]]:
    conversion = json.loads((dataset_root / "conversion_manifest.json").read_text(encoding="utf-8"))
    return conversion["records"]


def manifest_path(value: str) -> Path:
    return Path(value.replace("\\", "/"))


def build_test_set(
    dataset_root: Path,
    out_dir: Path,
    *,
    sample_count: int,
    seed: int,
) -> Dict[str, Any]:
    records = load_conversion_records(dataset_root)
    bsp_records = [record for record in records if record["category"] == BSP_CATEGORY]
    if not bsp_records:
        raise RuntimeError(f"No {BSP_CATEGORY!r} records found in {dataset_root / 'conversion_manifest.json'}")

    rng = random.Random(seed)
    base_graphs = {
        record["model_id"]: load_graph_json(manifest_path(record["graph_file"]))
        for record in bsp_records
    }
    candidate_graphs = dict(base_graphs)

    variant_records = []
    variants_dir = out_dir / "variant_graphs"
    for index in range(1, sample_count + 1):
        base_record = bsp_records[(index - 1) % len(bsp_records)]
        base_id = base_record["model_id"]
        variant_id = f"bsp_micro_{index:02d}_from_{base_id}"
        variant_graph, changes = make_micro_variant(base_graphs[base_id], index, rng)
        variant_path = variants_dir / f"{variant_id}.graph.json"
        write_graph_json(variant_graph, variant_path)
        variant_records.append(
            {
                "variant_id": variant_id,
                "expected_base_id": base_id,
                "graph_file": str(variant_path),
                "change_count": len(changes),
                "changes": changes,
                "node_count": variant_graph.number_of_nodes(),
                "edge_count": variant_graph.number_of_edges(),
            }
        )

    for record in records:
        if record["category"] == BSP_CATEGORY:
            continue
        candidate_graphs[record["model_id"]] = load_graph_json(manifest_path(record["graph_file"]))

    manifest = {
        "dataset_root": str(dataset_root),
        "out_dir": str(out_dir),
        "seed": seed,
        "sample_count": sample_count,
        "base_ids": [record["model_id"] for record in bsp_records],
        "candidate_count": len(candidate_graphs),
        "variants": variant_records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "micro_bsp_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest, "candidate_graphs": candidate_graphs}


def evaluate(
    dataset_root: Path,
    out_dir: Path,
    *,
    sample_count: int = 20,
    seed: int = 20260609,
    top_k: int = 5,
) -> Dict[str, Any]:
    built = build_test_set(dataset_root, out_dir, sample_count=sample_count, seed=seed)
    manifest = built["manifest"]
    candidate_graphs = built["candidate_graphs"]
    config = GraphSimilarityConfig(
        coarse_top_k=len(candidate_graphs),
        min_node_ratio=0.35,
        min_edge_ratio=0.30,
        min_type_ratio=0.35,
        max_node_gap=2500,
        max_edge_gap=10000,
        fusion_wl_weight=0.35,
        fusion_ted_weight=0.20,
        fusion_jaccard_weight=0.15,
        fusion_collapse_weight=0.30,
    )
    index = GraphSimilarityIndex(candidate_graphs, config=config)

    rows = []
    top1_correct = 0
    topk_correct = 0
    for variant in manifest["variants"]:
        query = load_graph_json(Path(variant["graph_file"]))
        ranked = index.rank(query, top_k=top_k, coarse_top_k=len(candidate_graphs))
        expected = variant["expected_base_id"]
        top1 = ranked[0] if ranked else None
        topk_ids = [item.candidate_id for item in ranked]
        is_top1_correct = bool(top1 and top1.candidate_id == expected)
        is_topk_correct = expected in topk_ids
        top1_correct += int(is_top1_correct)
        topk_correct += int(is_topk_correct)
        rows.append(
            {
                "query_id": variant["variant_id"],
                "expected_base_id": expected,
                "top1_id": top1.candidate_id if top1 else None,
                "top1_correct": is_top1_correct,
                "top1_fusion": top1.fusion_score if top1 else None,
                "top1_structure": top1.structure_score if top1 else None,
                "top1_wl": top1.wl_similarity if top1 else None,
                "top1_ted": top1.ted_similarity if top1 else None,
                "top1_cm": top1.collapse_match_similarity if top1 else None,
                "top1_jaccard": top1.jaccard_similarity if top1 else None,
                "topk_correct": is_topk_correct,
                "topk_ids": topk_ids,
                "change_count": variant["change_count"],
                "node_count": variant["node_count"],
                "edge_count": variant["edge_count"],
            }
        )

    summary = {
        "dataset_root": str(dataset_root),
        "out_dir": str(out_dir),
        "sample_count": sample_count,
        "candidate_count": len(candidate_graphs),
        "top_k": top_k,
        "weights": {
            "wl": config.fusion_wl_weight,
            "ted": config.fusion_ted_weight,
            "jaccard": config.fusion_jaccard_weight,
            "collapse": config.fusion_collapse_weight,
        },
        "top1_correct": top1_correct,
        "top1_accuracy": top1_correct / sample_count if sample_count else 0.0,
        f"top{top_k}_correct": topk_correct,
        f"top{top_k}_accuracy": topk_correct / sample_count if sample_count else 0.0,
        "rows": rows,
    }
    write_outputs(out_dir, summary)
    return summary


def write_outputs(out_dir: Path, summary: Dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "micro_bsp_similarity_eval.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = summary["rows"]
    csv_path = out_dir / "micro_bsp_similarity_eval.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    def fmt(value: Any) -> str:
        if value is None:
            return "NA"
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    weights = summary["weights"]
    top_k = summary["top_k"]
    topk_correct_key = f"top{top_k}_correct"
    topk_accuracy_key = f"top{top_k}_accuracy"
    lines = [
        "# BSP 微扰二分图相似度测试",
        "",
        "## 测试理解",
        "",
        "- 数据来源：`14类cp问题数据/Batch Scheduling Problem` 经 `cp2graph_dataset` 已转换出的 BSP 二分图。",
        "- 构造方式：以 BSP 原图为 base，生成 20 个只含少量局部子图差异的 query 变体。",
        "- 预期答案：每个变体都应该检索回它对应的原始 BSP base 图。",
        "- 图库候选：BSP base 图 + 其他类别图，检验模型是否能从干扰图里找回正确 base。",
        "",
        "## 权重",
        "",
        f"- WL：{weights['wl']}",
        f"- TED：{weights['ted']}",
        f"- Jaccard：{weights['jaccard']}",
        f"- Collapse-Match：{weights['collapse']}",
        "",
        "## 结果",
        "",
        f"- Query 数量：{summary['sample_count']}",
        f"- 候选图数量：{summary['candidate_count']}",
        f"- Top-1 正确数：{summary['top1_correct']}",
        f"- Top-1 准确率：{summary['top1_accuracy']:.4f}",
        f"- Top-{top_k} 正确数：{summary[topk_correct_key]}",
        f"- Top-{top_k} 准确率：{summary[topk_accuracy_key]:.4f}",
        "",
        "## 明细",
        "",
        "| Query | Expected | Top-1 | 正确 | Fusion | WL | TED | CM | Jaccard |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['query_id']}` | `{row['expected_base_id']}` | `{row['top1_id']}` | "
            f"{row['top1_correct']} | {fmt(row['top1_fusion'])} | {fmt(row['top1_wl'])} | "
            f"{fmt(row['top1_ted'])} | {fmt(row['top1_cm'])} | {fmt(row['top1_jaccard'])} |"
        )
    (out_dir / "micro_bsp_similarity_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BSP micro-variant bipartite graph retrieval.")
    parser.add_argument("--dataset-root", default="cp2graph_dataset")
    parser.add_argument("--out-dir", default="cp2graph_dataset/bsp_micro_similarity")
    parser.add_argument("--sample-count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    summary = evaluate(
        Path(args.dataset_root),
        Path(args.out_dir),
        sample_count=args.sample_count,
        seed=args.seed,
        top_k=args.top_k,
    )
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Top-{args.top_k} accuracy: {summary[f'top{args.top_k}_accuracy']:.4f}")
    print(f"Report: {Path(args.out_dir) / 'micro_bsp_similarity_summary.md'}")


if __name__ == "__main__":
    main()
