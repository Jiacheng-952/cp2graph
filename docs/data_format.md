# 数据格式说明

## 节点（nodes）

每个节点至少包含以下字段：

- `id`: 全局唯一 ID。
- `type`: `variable` 或 `constraint`。
- `domain`: 变量域（约束节点为 `null`）。
- `size`: 域大小（约束节点为 `null`）。
- `semantic_hash`: 语义哈希（变量节点为 `null`）。

变量节点附加属性：

- `name`: 原始变量名（仅溯源）。
- `is_objective`: 是否目标变量。

约束节点附加属性：

- `constraint_type`: 如 `int_lin_eq`、`all_different_int`、`int_element`。
- `params`: 规范化参数列表。

## 边（edges）

每条边包含：

- `src`: 起点节点 ID。
- `dst`: 终点节点 ID。
- `role`: `read` 或 `write`。

对于无向关系，序列化时以双向边表示（`v->c` 与 `c->v`）。

## 哈希策略

- 约束哈希：`blake2b-128(canonical_json({"type": ctype, "params": normalized_params}))`
- 图哈希：`blake2b-128(canonical_json({"nodes": ..., "edges": ...}))`

其中 `canonical_json` 为键排序且无多余空白的 JSON 序列化。
