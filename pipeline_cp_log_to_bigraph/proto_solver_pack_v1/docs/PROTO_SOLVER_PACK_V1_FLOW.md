# proto_solver_pack_v1 全流程说明

## 1. 这条链路是什么

这是 v1 的自洽工程工作区，主链路已经从旧的 `log -> 提取代码 -> FZN` 切换为：

`14类问题数据 -> v1/flow/run_v1_pipeline.py -> 每类 solver -> CpModel -> CpModelProto -> 二分图`

它不依赖 log 来重建模型代码。log 只保留在外层旧流程里做追溯，不是 v1 主链路。

## 2. v1 里有哪些内容

- `flow/`：v1 本地流程脚本
- `docs/`：v1 方案与测试说明
- `<类别>/solver.py|solve.py`：每类求解器副本
- `<类别>/data/*.json`：每类实例数据副本
- `<类别>/model.proto.pb`：每类最新 proto
- `bipartite_graphs/`：当前成功生成的二分图
- `proto_manifest.json`：proto 阶段统计
- `graph_manifest.json`：图阶段统计
- `graph_index.json`：图文件索引
- `conversion_failures.json`：失败明细

## 3. 实例数据从哪里来

每一类都优先使用自己的本地数据副本：

1. `proto_solver_pack_v1/<类别>/data/*.json`
2. 仅本地数据缺失时，再把 `artifacts/extracted_records.json` 当作兼容兜底

类别专用规则：

- `FJSP`：只挑结构完整、字段契约正确的 FJSP JSON
- `FRCPSP`：只挑符合字段契约的 FRCPSP JSON
- 其他类别：取第一个可用实例

## 4. 核心脚本

- `flow/create_solver_proto_pack.py`
- `flow/generate_category_protos.py`
- `flow/build_graphs_from_category_protos.py`
- `flow/run_v1_pipeline.py`

### `create_solver_proto_pack.py`

作用：

- 从 `14类cp问题数据/<类别>/solver.py|solve.py` 复制求解器
- 同时复制该类 `data/`
- 注入统一的 `build_model()` / `build_proto()` 入口

输出：

- `proto_solver_pack_v1/<类别>/solver.py` 或 `solve.py`
- `proto_solver_pack_v1/<类别>/data/`
- `proto_solver_pack_v1/PACK_INDEX.json`

### `generate_category_protos.py`

作用：

- 为每一类选一个实例
- 先尝试脚本式执行
- 再尝试函数式调用
- 对特殊类别做专用提取
- 捕获 `CpModel`
- 调用 `model.Proto()`
- 写出 `model.proto.pb`

输出：

- `proto_solver_pack_v1/<类别>/model.proto.pb`
- `proto_solver_pack_v1/proto_manifest.json`

### `build_graphs_from_category_protos.py`

作用：

- 读取 `model.proto.pb`
- 解析 `CpModelProto`
- 构建变量-约束二分图
- 写出图 JSON

输出：

- `proto_solver_pack_v1/bipartite_graphs/graph_*.json`
- `proto_solver_pack_v1/graph_index.json`
- `proto_solver_pack_v1/graph_manifest.json`
- `proto_solver_pack_v1/conversion_failures.json`

### `run_v1_pipeline.py`

作用：

- 一次性串起本地包刷新、proto 生成、二分图生成
- 是 v1 的一键入口

## 5. Proto 是怎么得到的

核心流程：

1. 先拿到一个可执行 solver
2. 绑定 `CpModel` 构造器拦截
3. 执行 solver
4. 抓到 `CpModel` 实例
5. 调用：`proto = model.Proto()`

`Proto` 是模型结构，不是求解结果。

## 6. 一键入口

推荐直接运行：

```bash
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_v1_pipeline.py
```

它会顺序执行：

1. 刷新 `proto_solver_pack_v1/`
2. 生成每类 `model.proto.pb`
3. 生成 `bipartite_graphs/*.json`
4. 更新 `proto_manifest.json` / `graph_manifest.json` / `graph_index.json`

默认会优先使用：

- `D:\ProgramAnaconda\envs\optagent_fixed\python.exe`

如果你手动指定 `--python-bin`，则优先使用你指定的解释器。

## 7. 覆盖规则

会覆盖：

- `model.proto.pb`
- `proto_manifest.json`
- `graph_manifest.json`
- `graph_index.json`
- `conversion_failures.json`
- `bipartite_graphs/*.json`

会保留：

- `docs/`
- 类别原始 `data/`

## 8. 当前状态

当前状态：`13/14`

失败的唯一类别：

- `gortek`：缺少 `docplex`
