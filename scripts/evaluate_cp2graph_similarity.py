from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import networkx as nx

from cp2graph.similarity import GraphSimilarityIndex


def load_graph_json(path: Path) -> nx.MultiDiGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.MultiDiGraph()
    for node in payload.get("nodes", []):
        node_id = node["id"]
        graph.add_node(node_id, **node)
    for edge in payload.get("edges", []):
        graph.add_edge(edge["src"], edge["dst"], src=edge["src"], dst=edge["dst"], role=edge.get("role", "read"))
    return graph


def evaluate(dataset_root: Path, top_k: int = 5, coarse_top_k: int = 8) -> Dict[str, Any]:
    conversion = json.loads((dataset_root / "conversion_manifest.json").read_text(encoding="utf-8"))
    records = conversion["records"]
    graphs = {record["model_id"]: load_graph_json(Path(record["graph_file"])) for record in records}
    metadata = {record["model_id"]: record for record in records}

    index = GraphSimilarityIndex(graphs)
    rows: List[Dict[str, Any]] = []
    top1_correct = 0
    topk_correct = 0

    for record in records:
        model_id = record["model_id"]
        category = record["category"]
        candidate_keys = [key for key in graphs if key != model_id]
        ranked = index.rank(graphs[model_id], top_k=top_k, coarse_top_k=coarse_top_k, candidate_keys=candidate_keys)
        top1 = ranked[0] if ranked else None
        top1_category = metadata[top1.candidate_id]["category"] if top1 else None
        topk_categories = [metadata[item.candidate_id]["category"] for item in ranked]

        is_top1_correct = top1_category == category
        is_topk_correct = category in topk_categories
        top1_correct += int(is_top1_correct)
        topk_correct += int(is_topk_correct)

        rows.append(
            {
                "query_id": model_id,
                "query_category": category,
                "query_data": record["data_file"],
                "top1_id": top1.candidate_id if top1 else None,
                "top1_category": top1_category,
                "top1_correct": is_top1_correct,
                "top1_fusion": top1.fusion_score if top1 else None,
                "top1_wl": top1.wl_similarity if top1 else None,
                "top1_ted": top1.ted_similarity if top1 else None,
                "top1_cm": top1.collapse_match_similarity if top1 else None,
                "top1_jaccard": top1.jaccard_similarity if top1 else None,
                "topk_correct": is_topk_correct,
                "topk_ids": [item.candidate_id for item in ranked],
            }
        )

    total = len(records)
    summary = {
        "dataset_root": str(dataset_root),
        "total_queries": total,
        "coarse_top_k": coarse_top_k,
        "top1_correct": top1_correct,
        "top1_accuracy": top1_correct / total if total else 0.0,
        f"top{top_k}_correct": topk_correct,
        f"top{top_k}_accuracy": topk_correct / total if total else 0.0,
        "rows": rows,
    }
    (dataset_root / "similarity_eval.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = dataset_root / "similarity_eval.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    write_markdown_report(dataset_root / "similarity_test_summary.md", summary, top_k)
    return summary


def write_markdown_report(path: Path, summary: Dict[str, Any], top_k: int) -> None:
    rows = summary["rows"]
    example = rows[0] if rows else None

    def _fmt(value: Any) -> str:
        if value is None:
            return "NA"
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    lines = [
        "# cp2graph_dataset 图相似度测试总结",
        "",
        "## 测试设置",
        "",
        "- 数据来源：`14类cp问题数据`，排除 `gortek`。",
        "- 数据集：13 类问题，每类取 `data/` 下按文件名排序的前 2 条 JSON 数据。",
        "- 总模型数：26。",
        "- 转换链路：`solver.py/solve.py -> CpModelProto -> 二分图 JSON -> 图相似度检索`。",
        "- 评估方式：leave-one-out。每次选 1 个 CP 模型作为 query，从剩余 25 个模型中检索最相似模型。",
        f"- 粗筛候选数：{summary['coarse_top_k']}。",
        "- 判定标准：检索结果与 query 属于同一问题类别则为正确。",
        "",
        "## 总体结果",
        "",
        f"- Query 数量：{summary['total_queries']}",
        f"- Top-1 正确数：{summary['top1_correct']}",
        f"- Top-1 准确率：{summary['top1_accuracy']:.4f}",
        f"- Top-{top_k} 正确数：{summary[f'top{top_k}_correct']}",
        f"- Top-{top_k} 准确率：{summary[f'top{top_k}_accuracy']:.4f}",
        "",
    ]

    if example:
        lines.extend(
            [
                "## 示例检索",
                "",
                f"- Query：`{example['query_id']}`",
                f"- Query 类别：{example['query_category']}",
                f"- Top-1：`{example['top1_id']}`",
                f"- Top-1 类别：{example['top1_category']}",
                f"- 是否正确：{example['top1_correct']}",
                f"- Fusion：{_fmt(example['top1_fusion'])}",
                f"- WL：{_fmt(example['top1_wl'])}",
                f"- TED：{_fmt(example['top1_ted'])}",
                f"- CM：{_fmt(example['top1_cm'])}",
                f"- Jaccard：{_fmt(example['top1_jaccard'])}",
                "",
            ]
        )

    lines.extend(
        [
            "## 明细",
            "",
            "| Query | 类别 | Top-1 | Top-1 类别 | 正确 | Fusion |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for row in rows:
        fusion = row["top1_fusion"]
        lines.append(
            f"| `{row['query_id']}` | {row['query_category']} | `{row['top1_id']}` | "
            f"{row['top1_category']} | {row['top1_correct']} | {_fmt(fusion)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate graph similarity retrieval on cp2graph_dataset.")
    parser.add_argument("--dataset-root", default="cp2graph_dataset")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--coarse-top-k", type=int, default=8)
    args = parser.parse_args()

    summary = evaluate(Path(args.dataset_root), top_k=args.top_k, coarse_top_k=args.coarse_top_k)
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Top-{args.top_k} accuracy: {summary[f'top{args.top_k}_accuracy']:.4f}")


if __name__ == "__main__":
    main()
