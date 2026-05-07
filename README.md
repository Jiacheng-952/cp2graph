# cp2graph

将约束规划模型（FlatZinc / MiniZinc 编译后 IR）转换为“数学约束网络”二分图（变量节点 - 约束节点）。

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
