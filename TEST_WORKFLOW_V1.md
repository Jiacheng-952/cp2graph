# proto_solver_pack_v1 测试流程

## 1. 每次测试先做什么

完整流程是：

1. 抽取日志记录
2. 重建 solver 包
3. 生成每类 Proto
4. 从 Proto 生成二分图
5. 写失败分析与图索引
6. 如在 `run_iteration.py` 中执行，再做是否保留的回退判断

## 2. 会调用哪些脚本

### 一键流程

- `run_pipeline.py`

它会依次调用：

- `extract_models_from_log.py`
- `create_solver_proto_pack.py`
- `generate_category_protos.py`
- `build_graphs_from_category_protos.py`

### 严格迭代流程

- `run_iteration.py`

它会额外调用：

- `iteration_manager.py`

用于记录本轮失败分析、解决方案与版本文档。

## 3. 每一步的输入输出

### `extract_models_from_log.py`

输入：

- 原始 log

输出：

- `artifacts/extracted_records.json`

说明：

- 这个文件只保留“追溯信息”
- 当前主链路已经不再依赖里面的 `model_code` 做 Proto 来源

### `create_solver_proto_pack.py`

输入：

- `14类cp问题数据/`

输出：

- `proto_solver_pack_v1/<类别>/solver.py`
- `proto_solver_pack_v1/<类别>/data/`
- `proto_solver_pack_v1/PACK_INDEX.json`

说明：

- 每次运行会覆盖同名类别文件
- 不会在结果目录里保留旧的残留版本

### `generate_category_protos.py`

输入：

- `proto_solver_pack_v1`
- `artifacts/extracted_records.json`

输出：

- `proto_solver_pack_v1/<类别>/model.proto.pb`
- `proto_solver_pack_v1/proto_manifest.json`

说明：

- 每类只保留一个当前 proto
- 成功的 proto 会覆盖旧的 proto
- 失败会写入 manifest 的 `proto_error`

### `build_graphs_from_category_protos.py`

输入：

- `proto_solver_pack_v1/proto_manifest.json`

输出：

- `proto_solver_pack_v1/bipartite_graphs/graph_*.json`
- `proto_solver_pack_v1/graph_index.json`
- `proto_solver_pack_v1/graph_manifest.json`
- `proto_solver_pack_v1/conversion_failures.json`

说明：

- `bipartite_graphs/` 每次会先清空再重写
- 图文件编号从 `graph_0001.json` 重新开始

## 4. 是否覆盖

会覆盖的内容：

- `model.proto.pb`
- `proto_manifest.json`
- `graph_manifest.json`
- `graph_index.json`
- `conversion_failures.json`
- `bipartite_graphs/*.json`

不会丢失的内容：

- `failure_analysis/<date>/...`
- `cp_to_fzn_improvement/<date>/...`
- `issue_solution_journal/<date>/...`

## 5. 失败时怎么看

先看这三个文件：

- `proto_manifest.json`
- `graph_manifest.json`
- `conversion_failures.json`

再按类别回查：

- `FJSP` / `FRCPSP` / `RSP` 当前主要是模型捕获入口问题
- `gortek` 是依赖缺失问题

