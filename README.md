# cp2graph

将约束规划模型（FlatZinc / MiniZinc 编译后 IR）转换为“数学约束网络”二分图（变量节点 - 约束节点），搭建图神经网络（GNN）或图卷积网络（GCN）架构，训练高效的图编码器，使编码器生成的节点/图向量具备精准的比对能力，可用于后续相似性匹配、分类识别等下游任务，确保向量比对结果的准确性与可靠性。
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
