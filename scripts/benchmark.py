"""
这段代码 = 自动生成一个超级大的 CP 模型
           → 用你的 cp2graph 解析成图
           → 测试解析速度
           → 测试内存占用是否合理
           → 不达标就直接报错（性能回归检测）
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from cp2graph.api import parse_model_text_to_graph


def build_large_model(lines: int = 10_000) -> str:
    constraints = max(1, lines - 5)
    chunks = ["var 0..10000: x;"]
    for i in range(constraints):
        chunks.append(f"constraint int_le(x,{10000 - (i % 100)});")
    chunks.append("solve satisfy;")
    return "\n".join(chunks) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-seconds", type=float, default=2.0)
    parser.add_argument("--lines", type=int, default=10_000)
    args = parser.parse_args()

    text = build_large_model(args.lines)
    t0 = time.perf_counter()
    g = parse_model_text_to_graph(text, normalize=True)
    elapsed = time.perf_counter() - t0
    text_bytes = len(text.encode("utf-8"))
    mem_bound = text_bytes * 5
    rough_graph_bytes = (g.number_of_nodes() + g.number_of_edges()) * 256

    print(f"elapsed_seconds={elapsed:.4f}")
    print(f"nodes={g.number_of_nodes()} edges={g.number_of_edges()}")
    print(f"text_bytes={text_bytes} rough_graph_bytes={rough_graph_bytes} bound={mem_bound}")

    if elapsed > args.max_seconds:
        raise SystemExit(f"Performance regression: {elapsed:.4f}s > {args.max_seconds:.4f}s")
    if rough_graph_bytes > mem_bound:
        raise SystemExit("Approx memory regression: rough graph size exceeds 5x text bound")


if __name__ == "__main__":
    main()
