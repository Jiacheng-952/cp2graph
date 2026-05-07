# Python API

## 顶层入口

- `parse_and_build_graph(model_path, normalize=True)`
  - 输入 `.fzn` 或 `.mzn` 文件路径，返回 `networkx.MultiDiGraph`。
- `parse_model_text_to_graph(text, normalize=True)`
  - 输入 FlatZinc 文本，返回图对象。
- `graph_fingerprint(graph)`
  - 返回图整体语义哈希。

## 解析器

- `FlatZincParser.parse_text(text)`
- `FlatZincParser.parse_file(path)`
- `compile_minizinc_to_fzn(model_path)`

## 归一化

- `normalize_model(model)`
  - 常量折叠
  - 变量标准化重命名（`v1, v2, ...`）
  - 约束去重（按语义哈希）

## 序列化

- `write_graph_json(graph, output_path)`
- `write_graph_graphml(graph, output_path)`
- `graph_to_json_obj(graph)`

## 增量更新

- `create_state(model)`
- `update_state(prev_state, new_model)`

以约束语义哈希为粒度，仅增量替换变更约束子图。
