from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

import networkx as nx

from cp2graph.hash_utils import semantic_hash
from cp2graph.similarity import (
    GraphSimilarityConfig,
    GraphSimilarityResult,
    GraphSummary,
    _canonical_node_sequence,
    _fusion_score,
    _levenshtein_distance,
    label_jaccard_similarity,
    passes_structural_filter,
    structural_compatibility_score,
    wl_kernel_similarity,
)


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


def manifest_path(value: str) -> Path:
    return Path(value.replace("\\", "/"))


def _numeric_suffix(node_id: str) -> int:
    try:
        return int(node_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return -1


def _next_id(graph: nx.MultiDiGraph, prefix: str, offset: int = 1) -> str:
    max_seen = max((_numeric_suffix(str(node_id)) for node_id in graph.nodes if str(node_id).startswith(prefix)), default=-1)
    return f"{prefix}{max_seen + offset:05d}"


def _variable_nodes(graph: nx.MultiDiGraph) -> List[str]:
    return sorted([str(node_id) for node_id, data in graph.nodes(data=True) if data.get("type") == "variable"])


def _constraint_nodes(graph: nx.MultiDiGraph) -> List[str]:
    return sorted([str(node_id) for node_id, data in graph.nodes(data=True) if data.get("type") == "constraint"])


def _add_bidirectional_edge(graph: nx.MultiDiGraph, var_id: str, constraint_id: str, role: str = "read") -> None:
    graph.add_edge(var_id, constraint_id, src=var_id, dst=constraint_id, role=role)
    graph.add_edge(constraint_id, var_id, src=constraint_id, dst=var_id, role=role)


def _add_local_linear_constraint(graph: nx.MultiDiGraph, rng: random.Random, variant_index: int) -> Dict[str, Any]:
    variables = _variable_nodes(graph)
    if not variables:
        return {"operation": "skip_add_local_linear_constraint", "reason": "no variable nodes"}
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
    if not variables:
        return {"operation": "skip_add_bool_guard_subgraph", "reason": "no variable nodes"}
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
    if not candidates:
        return {"operation": "skip_retag_small_constraint", "reason": "no constraint nodes"}
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


def load_records(dataset_root: Path) -> List[Dict[str, Any]]:
    conversion = json.loads((dataset_root / "conversion_manifest.json").read_text(encoding="utf-8"))
    return conversion["records"]


def record_maps(records: Iterable[Mapping[str, Any]]) -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    by_model_id: Dict[str, Dict[str, Any]] = {}
    by_category_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        item = dict(record)
        by_model_id[item["model_id"]] = item
        by_category_slug[item["category_slug"]].append(item)
    for items in by_category_slug.values():
        items.sort(key=lambda item: item["model_id"])
    return by_model_id, dict(by_category_slug)


def categorized_variant_path(variant_root: Path, category_slug: str, variant_id: str) -> Path:
    return variant_root / category_slug / f"{variant_id}.graph.json"


def copy_existing_bsp_variants(
    dataset_root: Path,
    out_dir: Path,
    records_by_model_id: Mapping[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    old_manifest_path = dataset_root / "bsp_micro_similarity" / "micro_bsp_manifest.json"
    if not old_manifest_path.exists():
        return []
    old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    copied = []
    for variant in old_manifest.get("variants", []):
        expected_base_id = variant["expected_base_id"]
        base_record = records_by_model_id[expected_base_id]
        src = manifest_path(variant["graph_file"])
        dst = categorized_variant_path(out_dir / "variant_graphs", base_record["category_slug"], variant["variant_id"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        copied.append(
            {
                **variant,
                "graph_file": str(dst),
                "category": base_record["category"],
                "category_slug": base_record["category_slug"],
                "expected_base_id": expected_base_id,
                "expected_category": base_record["category"],
                "source": "existing_bsp_micro",
            }
        )
    return copied


def build_all_micro_variants(
    dataset_root: Path,
    out_dir: Path,
    *,
    per_category: int,
    seed: int,
) -> Dict[str, Any]:
    records = load_records(dataset_root)
    records_by_model_id, records_by_category_slug = record_maps(records)
    rng = random.Random(seed)
    variant_records: List[Dict[str, Any]] = []

    variant_records.extend(copy_existing_bsp_variants(dataset_root, out_dir, records_by_model_id))
    existing_categories = {item["category_slug"] for item in variant_records}

    for category_slug, category_records in sorted(records_by_category_slug.items()):
        if category_slug in existing_categories:
            continue
        category = category_records[0]["category"]
        base_graphs = {
            record["model_id"]: load_graph_json(manifest_path(record["graph_file"]))
            for record in category_records
        }
        for index in range(1, per_category + 1):
            base_record = category_records[(index - 1) % len(category_records)]
            base_id = base_record["model_id"]
            variant_id = f"{category_slug}_micro_{index:02d}_from_{base_id}"
            variant_graph, changes = make_micro_variant(base_graphs[base_id], index, rng)
            variant_path = categorized_variant_path(out_dir / "variant_graphs", category_slug, variant_id)
            write_graph_json(variant_graph, variant_path)
            variant_records.append(
                {
                    "variant_id": variant_id,
                    "category": category,
                    "category_slug": category_slug,
                    "expected_base_id": base_id,
                    "expected_category": category,
                    "graph_file": str(variant_path),
                    "change_count": len(changes),
                    "changes": changes,
                    "node_count": variant_graph.number_of_nodes(),
                    "edge_count": variant_graph.number_of_edges(),
                    "source": "generated_micro",
                }
            )

    variant_records.sort(key=lambda item: (item["category_slug"], item["variant_id"]))
    manifest = {
        "dataset_root": str(dataset_root),
        "out_dir": str(out_dir),
        "seed": seed,
        "per_category": per_category,
        "category_count": len(records_by_category_slug),
        "base_model_count": len(records),
        "variant_count": len(variant_records),
        "categories": [
            {
                "category_slug": slug,
                "category": items[0]["category"],
                "base_ids": [item["model_id"] for item in items],
                "variant_count": sum(1 for variant in variant_records if variant["category_slug"] == slug),
            }
            for slug, items in sorted(records_by_category_slug.items())
        ],
        "variants": variant_records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "all_micro_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def result_to_dict(result: GraphSimilarityResult, metadata: Mapping[str, Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    meta = metadata.get(result.candidate_id, {}) if metadata else {}
    return {
        "candidate_id": result.candidate_id,
        "candidate_category": meta.get("category"),
        "candidate_category_slug": meta.get("category_slug"),
        "structure_score": result.structure_score,
        "wl_similarity": result.wl_similarity,
        "ted_similarity": result.ted_similarity,
        "collapse_match_similarity": result.collapse_match_similarity,
        "jaccard_similarity": result.jaccard_similarity,
        "fusion_score": result.fusion_score,
        "passed_filter": result.passed_filter,
    }


def make_config(coarse_top_k: int) -> GraphSimilarityConfig:
    return GraphSimilarityConfig(
        coarse_top_k=coarse_top_k,
        min_node_ratio=0.20,
        min_edge_ratio=0.15,
        min_type_ratio=0.20,
        max_node_gap=50_000,
        max_edge_gap=220_000,
        fusion_wl_weight=0.35,
        fusion_ted_weight=0.20,
        fusion_jaccard_weight=0.15,
        fusion_collapse_weight=0.30,
    )


@dataclass
class CachedGraph:
    graph: nx.MultiDiGraph
    summary: GraphSummary
    tokens: List[str]
    token_counts: Counter[str]


def build_cached_graph(graph: nx.MultiDiGraph, config: GraphSimilarityConfig) -> CachedGraph:
    shared = graph.graph.get("shared_subexpressions", {})
    tokens = _canonical_node_sequence(graph, shared)
    return CachedGraph(
        graph=graph,
        summary=GraphSummary.from_graph(graph, wl_iterations=config.wl_iterations),
        tokens=tokens,
        token_counts=Counter(tokens),
    )


def cached_ted_similarity(left: CachedGraph, right: CachedGraph) -> float:
    if len(left.tokens) * len(right.tokens) > 200_000:
        common = sum(
            min(left.token_counts[token], right.token_counts[token])
            for token in left.token_counts.keys() & right.token_counts.keys()
        )
        return common / max(len(left.tokens), len(right.tokens), 1)
    distance = _levenshtein_distance(left.tokens, right.tokens)
    return max(0.0, 1.0 - (distance / max(len(left.tokens), len(right.tokens), 1)))


def cached_collapse_similarity(left: CachedGraph, right: CachedGraph) -> float:
    common = sum(
        min(left.token_counts[token], right.token_counts[token])
        for token in left.token_counts.keys() & right.token_counts.keys()
    )
    return common / max(sum(left.token_counts.values()), sum(right.token_counts.values()), 1)


def cached_rank(
    query: CachedGraph,
    candidates: Mapping[str, CachedGraph],
    config: GraphSimilarityConfig,
    *,
    top_k: int,
    coarse_top_k: int,
) -> List[GraphSimilarityResult]:
    coarse_scored: List[tuple[str, float]] = []
    for key, candidate in candidates.items():
        if not passes_structural_filter(query.summary, candidate.summary, config):
            continue
        wl_score = wl_kernel_similarity(query.summary.wl_features, candidate.summary.wl_features)
        jaccard_score = label_jaccard_similarity(query.summary, candidate.summary)
        coarse_scored.append((key, 0.75 * wl_score + 0.25 * jaccard_score))

    if not coarse_scored:
        for key, candidate in candidates.items():
            wl_score = wl_kernel_similarity(query.summary.wl_features, candidate.summary.wl_features)
            jaccard_score = label_jaccard_similarity(query.summary, candidate.summary)
            coarse_scored.append((key, 0.75 * wl_score + 0.25 * jaccard_score))

    coarse_scored.sort(key=lambda item: item[1], reverse=True)
    shortlist = [key for key, _score in coarse_scored[:coarse_top_k]]

    scored: List[GraphSimilarityResult] = []
    for key in shortlist:
        candidate = candidates[key]
        structure_score = structural_compatibility_score(query.summary, candidate.summary)
        wl_score = wl_kernel_similarity(query.summary.wl_features, candidate.summary.wl_features)
        jaccard_score = label_jaccard_similarity(query.summary, candidate.summary)
        ted_score = cached_ted_similarity(query, candidate)
        collapse_score = cached_collapse_similarity(query, candidate)
        fusion_score = _fusion_score(structure_score, wl_score, ted_score, jaccard_score, collapse_score, config)
        scored.append(
            GraphSimilarityResult(
                candidate_id=key,
                structure_score=structure_score,
                wl_similarity=wl_score,
                ted_similarity=ted_score,
                collapse_match_similarity=collapse_score,
                jaccard_similarity=jaccard_score,
                fusion_score=fusion_score,
                passed_filter=passes_structural_filter(query.summary, candidate.summary, config),
            )
        )

    scored.sort(key=lambda item: item.wl_similarity, reverse=True)
    scored = scored[:coarse_top_k]
    scored.sort(key=lambda item: item.fusion_score, reverse=True)
    return scored[:top_k]


def evaluate_base_retrieval(
    dataset_root: Path,
    out_dir: Path,
    manifest: Mapping[str, Any],
    variant_cache: Mapping[str, CachedGraph],
    *,
    top_k: int,
    coarse_top_k: int,
) -> Dict[str, Any]:
    records = load_records(dataset_root)
    records_by_model_id, _records_by_category_slug = record_maps(records)
    config = make_config(coarse_top_k=coarse_top_k)
    base_graphs = {
        record["model_id"]: build_cached_graph(load_graph_json(manifest_path(record["graph_file"])), config)
        for record in records
    }

    rows = []
    top1_base_correct = 0
    top1_category_correct = 0
    topk_base_correct = 0
    topk_category_correct = 0
    per_category: Dict[str, Dict[str, Any]] = {}

    for variant in manifest["variants"]:
        ranked = cached_rank(variant_cache[variant["variant_id"]], base_graphs, config, top_k=top_k, coarse_top_k=coarse_top_k)
        top5 = [result_to_dict(item, records_by_model_id) for item in ranked]
        top1 = top5[0] if top5 else {}
        top_ids = [item["candidate_id"] for item in top5]
        top_categories = [item["candidate_category"] for item in top5]
        expected_base_id = variant["expected_base_id"]
        expected_category = variant["expected_category"]
        is_top1_base_correct = top1.get("candidate_id") == expected_base_id
        is_top1_category_correct = top1.get("candidate_category") == expected_category
        is_topk_base_correct = expected_base_id in top_ids
        is_topk_category_correct = expected_category in top_categories
        top1_base_correct += int(is_top1_base_correct)
        top1_category_correct += int(is_top1_category_correct)
        topk_base_correct += int(is_topk_base_correct)
        topk_category_correct += int(is_topk_category_correct)

        bucket = per_category.setdefault(
            variant["category_slug"],
            {
                "category": expected_category,
                "query_count": 0,
                "top1_base_correct": 0,
                "top1_category_correct": 0,
                f"top{top_k}_base_correct": 0,
                f"top{top_k}_category_correct": 0,
            },
        )
        bucket["query_count"] += 1
        bucket["top1_base_correct"] += int(is_top1_base_correct)
        bucket["top1_category_correct"] += int(is_top1_category_correct)
        bucket[f"top{top_k}_base_correct"] += int(is_topk_base_correct)
        bucket[f"top{top_k}_category_correct"] += int(is_topk_category_correct)

        rows.append(
            {
                "query_id": variant["variant_id"],
                "query_category": expected_category,
                "query_category_slug": variant["category_slug"],
                "expected_base_id": expected_base_id,
                "top1_id": top1.get("candidate_id"),
                "top1_category": top1.get("candidate_category"),
                "top1_base_correct": is_top1_base_correct,
                "top1_category_correct": is_top1_category_correct,
                f"top{top_k}_base_correct": is_topk_base_correct,
                f"top{top_k}_category_correct": is_topk_category_correct,
                "top5": top5,
            }
        )

    total = len(rows)
    for bucket in per_category.values():
        count = bucket["query_count"]
        bucket["top1_base_accuracy"] = bucket["top1_base_correct"] / count if count else 0.0
        bucket["top1_category_accuracy"] = bucket["top1_category_correct"] / count if count else 0.0
        bucket[f"top{top_k}_base_accuracy"] = bucket[f"top{top_k}_base_correct"] / count if count else 0.0
        bucket[f"top{top_k}_category_accuracy"] = bucket[f"top{top_k}_category_correct"] / count if count else 0.0

    summary = {
        "task": "micro_variant_to_base_model",
        "dataset_root": str(dataset_root),
        "variant_count": total,
        "candidate_base_model_count": len(base_graphs),
        "top_k": top_k,
        "coarse_top_k": coarse_top_k,
        "weights": {"wl": 0.35, "ted": 0.20, "jaccard": 0.15, "collapse": 0.30},
        "top1_base_correct": top1_base_correct,
        "top1_base_accuracy": top1_base_correct / total if total else 0.0,
        "top1_category_correct": top1_category_correct,
        "top1_category_accuracy": top1_category_correct / total if total else 0.0,
        f"top{top_k}_base_correct": topk_base_correct,
        f"top{top_k}_base_accuracy": topk_base_correct / total if total else 0.0,
        f"top{top_k}_category_correct": topk_category_correct,
        f"top{top_k}_category_accuracy": topk_category_correct / total if total else 0.0,
        "per_category": dict(sorted(per_category.items())),
        "rows": rows,
    }
    (out_dir / "all_micro_base_retrieval_eval.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_base_csv(out_dir / "all_micro_base_retrieval_eval.csv", rows, top_k)
    return summary


def write_base_csv(path: Path, rows: List[Dict[str, Any]], top_k: int) -> None:
    fields = [
        "query_id",
        "query_category",
        "expected_base_id",
        "top1_id",
        "top1_category",
        "top1_base_correct",
        "top1_category_correct",
        f"top{top_k}_base_correct",
        f"top{top_k}_category_correct",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def evaluate_self_recall(
    out_dir: Path,
    manifest: Mapping[str, Any],
    variant_cache: Mapping[str, CachedGraph],
    *,
    top_k: int,
    coarse_top_k: int,
) -> Dict[str, Any]:
    variants = manifest["variants"]
    metadata = {
        variant["variant_id"]: {
            "category": variant["category"],
            "category_slug": variant["category_slug"],
            "expected_base_id": variant["expected_base_id"],
        }
        for variant in variants
    }
    config = make_config(coarse_top_k=coarse_top_k)

    rows = []
    top1_correct = 0
    topk_correct = 0
    for variant in variants:
        query_id = variant["variant_id"]
        ranked = cached_rank(variant_cache[query_id], variant_cache, config, top_k=top_k, coarse_top_k=coarse_top_k)
        top5 = [result_to_dict(item, metadata) for item in ranked]
        top_ids = [item["candidate_id"] for item in top5]
        top1 = top5[0] if top5 else {}
        is_top1_correct = top1.get("candidate_id") == query_id
        is_topk_correct = query_id in top_ids
        top1_correct += int(is_top1_correct)
        topk_correct += int(is_topk_correct)
        rows.append(
            {
                "query_id": query_id,
                "query_category": variant["category"],
                "expected_base_id": variant["expected_base_id"],
                "top1_id": top1.get("candidate_id"),
                "top1_correct": is_top1_correct,
                f"top{top_k}_correct": is_topk_correct,
                "top5": top5,
            }
        )

    total = len(rows)
    summary = {
        "task": "micro_variant_self_recall",
        "variant_count": total,
        "candidate_variant_count": len(variant_cache),
        "top_k": top_k,
        "coarse_top_k": coarse_top_k,
        "weights": {"wl": 0.35, "ted": 0.20, "jaccard": 0.15, "collapse": 0.30},
        "top1_correct": top1_correct,
        "top1_accuracy": top1_correct / total if total else 0.0,
        f"top{top_k}_correct": topk_correct,
        f"top{top_k}_accuracy": topk_correct / total if total else 0.0,
        "rows": rows,
    }
    (out_dir / "all_micro_self_recall_eval.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_self_csv(out_dir / "all_micro_self_recall_eval.csv", rows, top_k)
    return summary


def write_self_csv(path: Path, rows: List[Dict[str, Any]], top_k: int) -> None:
    fields = ["query_id", "query_category", "expected_base_id", "top1_id", "top1_correct", f"top{top_k}_correct"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_report(out_dir: Path, manifest: Mapping[str, Any], base_summary: Mapping[str, Any], self_summary: Mapping[str, Any]) -> None:
    top_k = base_summary["top_k"]
    topk_base_key = f"top{top_k}_base_accuracy"
    topk_category_key = f"top{top_k}_category_accuracy"
    self_topk_key = f"top{top_k}_accuracy"

    lines = [
        "# 全类别 Micro 二分图相似度测试报告",
        "",
        "## 1. 测试目标",
        "",
        "本轮测试把 BSP micro 实验扩展到 `cp2graph_dataset` 的 13 个问题类。每类保留或生成 20 个只包含少量局部子图差异的 micro variant，总计 260 个 micro 图。",
        "",
        "测试分为两项：",
        "",
        "1. `micro variant -> 原始问题实例`：以 micro 图为 query，在 26 个原始问题实例图中检索 Top-5，检查是否找回对应类别和具体 base 编号。",
        "2. `micro variant -> micro variant 自身`：以 260 个 micro 图组成图库，任选一个 micro 图作为 query，检查 Top-1 是否召回它自身。",
        "",
        "## 2. 数据与目录",
        "",
        "- 原始图目录：`cp2graph_dataset/graphs`",
        "- Micro 图目录：`cp2graph_dataset/bsp_micro_similarity/variant_graphs`",
        "- 分类清单：`cp2graph_dataset/bsp_micro_similarity/all_micro_manifest.json`",
        "- BSP：复用已生成的 20 个 micro 图，并复制到分类子目录。",
        "- 剩余 12 类：每类新生成 20 个 micro 图。",
        "",
        "## 3. 问题类覆盖",
        "",
        "| 类别目录 | 问题类 | Base 实例 | Micro 图数量 |",
        "|---|---|---|---:|",
    ]
    for category in manifest["categories"]:
        lines.append(
            f"| `{category['category_slug']}` | {category['category']} | "
            f"`{', '.join(category['base_ids'])}` | {category['variant_count']} |"
        )

    lines.extend(
        [
            "",
            "## 4. 相似度权重",
            "",
            "| 指标 | 权重 |",
            "|---|---:|",
            "| WL | 0.35 |",
            "| TED | 0.20 |",
            "| Jaccard | 0.15 |",
            "| Collapse-Match | 0.30 |",
            "",
            "## 5. 测试一：Micro 召回原始问题实例",
            "",
            "候选图库为 26 个原始问题实例图。结果 JSON 中为每个 query 保存了 Top-5 候选及各项分数：`structure_score`、`wl_similarity`、`ted_similarity`、`collapse_match_similarity`、`jaccard_similarity`、`fusion_score`。",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            f"| Query 数量 | {base_summary['variant_count']} |",
            f"| 原始候选实例数 | {base_summary['candidate_base_model_count']} |",
            f"| 粗筛候选数 | {base_summary['coarse_top_k']} |",
            f"| Top-1 具体 base 正确率 | {base_summary['top1_base_accuracy']:.4f} |",
            f"| Top-1 问题类别正确率 | {base_summary['top1_category_accuracy']:.4f} |",
            f"| Top-{top_k} 具体 base 正确率 | {base_summary[topk_base_key]:.4f} |",
            f"| Top-{top_k} 问题类别正确率 | {base_summary[topk_category_key]:.4f} |",
            "",
            "### 5.1 分类别结果",
            "",
            "| 类别目录 | 问题类 | Query | Top-1 Base Acc | Top-1 Category Acc | Top-5 Base Acc | Top-5 Category Acc |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for slug, bucket in base_summary["per_category"].items():
        lines.append(
            f"| `{slug}` | {bucket['category']} | {bucket['query_count']} | "
            f"{bucket['top1_base_accuracy']:.4f} | {bucket['top1_category_accuracy']:.4f} | "
            f"{bucket[f'top{top_k}_base_accuracy']:.4f} | {bucket[f'top{top_k}_category_accuracy']:.4f} |"
        )

    lines.extend(
        [
            "",
            "### 5.2 Top-5 样例",
            "",
            "下面展开前 5 个 query 的 Top-5 候选。完整 260 个 query 的 Top-5 分数保存在 `all_micro_base_retrieval_eval.json`。",
            "",
            "| Query | Expected Base | Rank | Candidate | Candidate 类别 | Fusion | Structure | WL | TED | CM | Jaccard |",
            "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in base_summary["rows"][:5]:
        for rank, candidate in enumerate(row["top5"], start=1):
            lines.append(
                f"| `{row['query_id']}` | `{row['expected_base_id']}` | {rank} | "
                f"`{candidate['candidate_id']}` | {candidate['candidate_category']} | "
                f"{fmt(candidate['fusion_score'])} | {fmt(candidate['structure_score'])} | "
                f"{fmt(candidate['wl_similarity'])} | {fmt(candidate['ted_similarity'])} | "
                f"{fmt(candidate['collapse_match_similarity'])} | {fmt(candidate['jaccard_similarity'])} |"
            )

    lines.extend(
        [
            "",
            "## 6. 测试二：260 个 Micro 图内部自召回",
            "",
            "候选图库为全部 260 个 micro variant。为了控制大图精排成本，先使用 WL/Jaccard 粗筛，再对 shortlist 做 TED、Collapse-Match 和融合排序。每个 query 的 Top-5 仍完整保存在 JSON 中。",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            f"| Query 数量 | {self_summary['variant_count']} |",
            f"| Micro 候选图数量 | {self_summary['candidate_variant_count']} |",
            f"| 粗筛候选数 | {self_summary['coarse_top_k']} |",
            f"| Top-1 自召回正确率 | {self_summary['top1_accuracy']:.4f} |",
            f"| Top-{top_k} 自召回正确率 | {self_summary[self_topk_key]:.4f} |",
            "",
            "### 6.1 自召回 Top-5 样例",
            "",
            "下面展开前 5 个 query 在 260 个 micro 图图库中的 Top-5 候选。完整结果保存在 `all_micro_self_recall_eval.json`。",
            "",
            "| Query | Rank | Candidate | Candidate 类别 | Fusion | Structure | WL | TED | CM | Jaccard | 自身命中 |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in self_summary["rows"][:5]:
        for rank, candidate in enumerate(row["top5"], start=1):
            is_self = candidate["candidate_id"] == row["query_id"]
            lines.append(
                f"| `{row['query_id']}` | {rank} | `{candidate['candidate_id']}` | "
                f"{candidate['candidate_category']} | {fmt(candidate['fusion_score'])} | "
                f"{fmt(candidate['structure_score'])} | {fmt(candidate['wl_similarity'])} | "
                f"{fmt(candidate['ted_similarity'])} | {fmt(candidate['collapse_match_similarity'])} | "
                f"{fmt(candidate['jaccard_similarity'])} | {is_self} |"
            )

    lines.extend(
        [
            "",
            "## 7. 输出文件",
            "",
            "- `all_micro_manifest.json`：260 个 micro 图的分类清单。",
            "- `all_micro_base_retrieval_eval.json`：micro 查询 26 个原始问题实例的 Top-5 详细分数。",
            "- `all_micro_base_retrieval_eval.csv`：测试一的扁平摘要。",
            "- `all_micro_self_recall_eval.json`：260 个 micro 图内部自召回的 Top-5 详细分数。",
            "- `all_micro_self_recall_eval.csv`：测试二的扁平摘要。",
            "- `all_micro_similarity_test_report.md`：本文档。",
            "",
            "## 8. 结论",
            "",
            f"- Micro 召回原始问题实例：Top-1 具体 base 正确率为 `{base_summary['top1_base_accuracy']:.4f}`，Top-1 类别正确率为 `{base_summary['top1_category_accuracy']:.4f}`。",
            f"- Micro 图内部自召回：Top-1 准确率为 `{self_summary['top1_accuracy']:.4f}`。",
            "- 本轮测试覆盖全部 13 个问题类；BSP micro 图已按类别目录整理，剩余 12 类已补齐生成。",
        ]
    )
    (out_dir / "all_micro_similarity_test_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(
    dataset_root: Path,
    out_dir: Path,
    *,
    per_category: int,
    seed: int,
    top_k: int,
    base_coarse_top_k: int,
    self_coarse_top_k: int,
) -> Dict[str, Any]:
    manifest = build_all_micro_variants(dataset_root, out_dir, per_category=per_category, seed=seed)
    cache_config = make_config(coarse_top_k=max(base_coarse_top_k, self_coarse_top_k))
    variant_cache = {
        variant["variant_id"]: build_cached_graph(load_graph_json(manifest_path(variant["graph_file"])), cache_config)
        for variant in manifest["variants"]
    }
    base_summary = evaluate_base_retrieval(
        dataset_root,
        out_dir,
        manifest,
        variant_cache,
        top_k=top_k,
        coarse_top_k=base_coarse_top_k,
    )
    self_summary = evaluate_self_recall(
        out_dir,
        manifest,
        variant_cache,
        top_k=top_k,
        coarse_top_k=self_coarse_top_k,
    )
    write_report(out_dir, manifest, base_summary, self_summary)
    result = {
        "manifest": str(out_dir / "all_micro_manifest.json"),
        "base_eval": str(out_dir / "all_micro_base_retrieval_eval.json"),
        "self_eval": str(out_dir / "all_micro_self_recall_eval.json"),
        "report": str(out_dir / "all_micro_similarity_test_report.md"),
        "base_top1_accuracy": base_summary["top1_base_accuracy"],
        "base_category_top1_accuracy": base_summary["top1_category_accuracy"],
        "self_top1_accuracy": self_summary["top1_accuracy"],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and evaluate micro variants for all cp2graph_dataset categories.")
    parser.add_argument("--dataset-root", default="cp2graph_dataset")
    parser.add_argument("--out-dir", default="cp2graph_dataset/bsp_micro_similarity")
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--base-coarse-top-k", type=int, default=8)
    parser.add_argument("--self-coarse-top-k", type=int, default=8)
    args = parser.parse_args()

    result = evaluate(
        Path(args.dataset_root),
        Path(args.out_dir),
        per_category=args.per_category,
        seed=args.seed,
        top_k=args.top_k,
        base_coarse_top_k=args.base_coarse_top_k,
        self_coarse_top_k=args.self_coarse_top_k,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
