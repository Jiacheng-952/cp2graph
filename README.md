# cp2graph

将约束规划模型（FlatZinc / MiniZinc 编译后 IR）转换为“数学约束网络”二分图（变量节点 - 约束节点），并在此基础上提供图相似度检索与排序能力。当前版本支持对 CP 图进行规范化、WL 特征提取、结构兼容性过滤、标签 Jaccard 计算与自适应融合排序，可用于相似性匹配、实例检索、分类识别等下游任务；同时保留 GNN/GCN 编码器接口，便于后续训练高效图编码器并进一步增强节点向量与图向量的比对精度。

## 安装

```bash
pip install -e .[dev]
```

## CLI

```bash
cp2graph model.fzn -o graph.json --hash
cp2graph model.mzn -o graph.graphml --format graphml --hash
```

## Python API

```python
from cp2graph import parse_and_build_graph
from cp2graph.serialize import write_graph_json

graph = parse_and_build_graph("model.fzn")
write_graph_json(graph, "graph.json")
```

## GNN/GCN encoder

```python
from cp2graph.api import parse_and_build_graph
from cp2graph.gnn import GraphPair, compare_graphs, train_encoder

g1 = parse_and_build_graph("a.fzn")
g2 = parse_and_build_graph("b.fzn")

model, history = train_encoder(
    [GraphPair(g1, g1, 1.0), GraphPair(g1, g2, 0.0)],
    epochs=10,
)
score = compare_graphs(model, g1, g2)
```

Install the ML extra with `pip install -e .[ml]` if PyTorch is not already available.

## 输出格式

`JSON` 字段固定为：

- `nodes/{id,type,domain,size,semantic_hash}`
- `edges/{src,dst,role}`

更多细节见 `docs/data_format.md` 与 `docs/api.md`。

## 测试与覆盖率

```bash
pytest
```

## 性能基准

```bash
python scripts/benchmark.py --max-seconds 2.0
```

## 哈希冲突抽样验证

```bash
python scripts/hash_collision_check.py --samples 10000 --seed 42
```

## 图相似度检索

第一版的图相似度模块已经放在 `cp2graph.similarity` 中，既支持**两个图直接比较**，也支持**图库检索**。

两个图直接比较时，使用：

```python
from cp2graph.api import parse_and_build_graph
from cp2graph.similarity import score_graph_pair

g1 = parse_and_build_graph("a.fzn")
g2 = parse_and_build_graph("b.fzn")
result = score_graph_pair(g1, g2)
```

如果你有一个图库，并希望对一个查询图做 Top-k 检索，则使用：

```python
from cp2graph.api import parse_and_build_graph
from cp2graph.similarity import GraphSimilarityIndex

library = {
    "m01": parse_and_build_graph("tests/models/m01_arith.fzn"),
    "m03": parse_and_build_graph("tests/models/m03_all_diff.fzn"),
}
index = GraphSimilarityIndex(library)
results = index.rank(parse_and_build_graph("tests/models/m04_element.fzn"), top_k=5)
```

当前支持的核心流程是：

- `WL` 结构粗筛
- 结构兼容性过滤
- `TED` 图近似
- `Collapse-Match` 图近似
- 标签 `Jaccard` 重叠
- 自适应融合排序

同时，`normalize_model` 已加入 graph-CSE 风格的共享子表达式折叠，会把重复子结构提取到 `shared_subexpressions` 中，供后续比较阶段复用。

设计说明见 [docs/graph_similarity.md](docs/graph_similarity.md)。
