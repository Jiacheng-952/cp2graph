# Rtest 工程闭环说明（RSP / RSP2）

## 1. 文档目标

本说明对应 `pipeline_cp_log_to_bigraph/Rtest` **当前真实可运行版本**。

你现在可以在 Rtest 内完成以下闭环：

1. 数据与模型来源准备（RSP 或 RSP2）
2. `CpModelProto` 生成
3. Proto 转二分图
4. 图相似度检索（Top-k）
5. 结果分析与批次归档

并且每次运行都会生成独立 `batch_*` 子文件夹，历史结果不会覆盖。

---

## 2. 当前目录角色

- `Rtest/flow/`：主流程脚本
- `Rtest/RSP2/`：RSP2 源数据与生成器（已内置到 Rtest）
- `Rtest/batch_*`：每次完整测试的独立结果包
- `Rtest/_archive/`：历史遗留工作位归档（不参与当前闭环）
- `Rtest/BATCH_INDEX.md`：所有批次汇总索引
- `Rtest/BATCH_INDEX.json`：批次索引的机器可读版本

注意：

- 当前有效输入/输出只看 `batch_*` 与 `RSP2`。
- 根目录旧工作位已归档到 `Rtest/_archive/RSP_root_legacy_workspace/`，不要再作为新测试输入。

---

## 3. 一次测试的完整流程

入口脚本：

- `pipeline_cp_log_to_bigraph/Rtest/flow/run_rtest_pipeline.py`

执行顺序：

1. `create_rsp_pack.py`
2. `generate_rsp_protos.py`
3. `build_rsp_graphs_from_protos.py`
4. `proto_solver_pack_v1/flow/run_similarity_on_v1_graphs.py`
5. `analyze_rsp_pipeline.py`
6. `generate_batch_index.py`（自动刷新批次总索引）

---

## 4. RSP 与 RSP2 的关系

- `RSP`：流程运行时的统一工作目录名（批次内是 `batch_xxx/RSP`）
- `RSP2`：上游来源包（高质量数据、生成器、模型代码）

当你使用 `--source-kind rsp2` 时：

- 来源来自 `Rtest/RSP2`
- 可直接复制 `RSP2/data`，或先调用 `RSP2/generate.py` 生成新实例
- 之后流程仍按统一 RSP 工作位进入 proto -> 图 -> 相似度

默认建议：

- 不加 `--use-existing-data`，优先使用 `RSP2/generate.py` 现生成数据
- 这样可确保用到的是当前生成逻辑，而不是旧静态 data

---

## 4.1 逐步闭环细解：原始数据 + solver.py 如何变成二分图（以及 CP 模型在哪）

下面用 `source-kind=rsp2` 说明（`legacy` 同理，只是数据来源不同）：

### Step A：创建批次工作区

脚本：

- `Rtest/flow/run_rtest_pipeline.py`

动作：

- 在 `Rtest/` 下创建新的 `batch_YYYYMMDD_HHMMSS[_tag]/`
- 后续所有产物都写入这个批次目录，不覆盖历史

### Step B：把“来源包”装配到批次内统一 RSP 工作位

脚本：

- `Rtest/flow/create_rsp_pack.py`

动作：

1. 在批次内创建 `batch_xxx/RSP/`
2. 准备实例数据到 `batch_xxx/RSP/data/*.json`：
   - 要么从 `Rtest/RSP2/data` 拷贝
   - 要么调用 `Rtest/RSP2/generate.py` 现场生成
3. 把 `RSP2/solver.py` 复制到 `batch_xxx/RSP/solver.py`
4. 写 `batch_xxx/PACK_INDEX.json` 记录来源与参数

结果：

- 批次内已经有“可运行的实例数据 + solver 代码”

### Step C：由实例数据触发 CP 建模并导出 Proto（CP 模型在这里出现）

脚本：

- `Rtest/flow/generate_rsp_protos.py`

动作（RSP2 默认 `solver_capture`）：

1. 枚举 `batch_xxx/RSP/data/*.json`
2. 对每个实例调用 `batch_xxx/RSP/solver.py` 的：
   - `load_instance_data(...)`
   - `solve_with_ortools(...)`
3. 在 `solve_with_ortools(...)` 内部执行 `cp_model.CpModel()` 并添加约束  
   这一步就是 **实例化 CP 模型**（真正的建模发生点）
4. 脚本用 monkey patch 捕获该 `CpModel`，执行 `model.Proto()`
5. 输出 `batch_xxx/protos/proto_XXXX.pb`
6. 写 `batch_xxx/proto_manifest.json`

结论：

- `CP 模型`不是静态文件，它是在运行 `solver.py` 时按每个实例动态构建出来的
- 每个 `json` 实例对应一个 `CpModelProto`

### Step D：Proto 转二分图

脚本：

- `Rtest/flow/build_rsp_graphs_from_protos.py`

动作：

1. 读取 `proto_manifest.json` 中成功的 `proto_*.pb`
2. 调用 `src/cp2graph` 的构图能力，把变量与约束节点化
3. 输出二分图 JSON 到 `batch_xxx/bipartite_graphs/graph_XXXX.json`
4. 写索引与统计：
   - `graph_index.json`
   - `graph_manifest.json`
   - `conversion_failures.json`

### Step E：在图上做相似度与检索

脚本：

- `proto_solver_pack_v1/flow/run_similarity_on_v1_graphs.py`

动作：

1. 读取 `batch_xxx/graph_index.json`
2. 在图之间做两两相似度计算（六项指标加权）
3. 输出 `batch_xxx/similarity_report.json`（含 Top-k 检索结果）

### Step F：批次分析与总索引更新

脚本：

- `Rtest/flow/analyze_rsp_pipeline.py`
- `Rtest/flow/generate_batch_index.py`

动作：

- 生成本批次分析报告 `reports/analysis_*.json|md`
- 刷新全局批次索引 `Rtest/BATCH_INDEX.md|json`

---

## 5. 批次产物结构（每次测试）

每次运行都会在 `Rtest` 下新建：

- `batch_YYYYMMDD_HHMMSS[_tag]/`

其中包含：

- `PACK_INDEX.json`
- `proto_manifest.json`
- `protos/*.pb`
- `graph_manifest.json`
- `graph_index.json`
- `bipartite_graphs/*.json`
- `similarity_report.json`
- `conversion_failures.json`
- `reports/analysis_*.json`
- `reports/analysis_*.md`
- `RUN_INFO.md`（本批次说明：来源、时间、目的、参数、产物路径）

说明：

- 历史批次不会被覆盖
- 后续检索测试可直接复用旧批次图文件

---

## 6. 关键脚本说明

### 6.1 `create_rsp_pack.py`

路径：`pipeline_cp_log_to_bigraph/Rtest/flow/create_rsp_pack.py`

作用：准备批次内 `RSP/solver.py` 与 `RSP/data`。

- `source-kind=legacy`：来源于旧 RSP 数据目录
- `source-kind=rsp2`：来源于 `Rtest/RSP2`

### 6.2 `generate_rsp_protos.py`

路径：`pipeline_cp_log_to_bigraph/Rtest/flow/generate_rsp_protos.py`

作用：将 `RSP/data/*.json` + `RSP/solver.py` 转为 `protos/*.pb`。

说明：支持两种捕获方式（自动判定）：

- adapter（传统 build_proto/build_model）
- solver_capture（适配 RSP2 solver 风格）

### 6.3 `build_rsp_graphs_from_protos.py`

路径：`pipeline_cp_log_to_bigraph/Rtest/flow/build_rsp_graphs_from_protos.py`

作用：Proto 构图并输出：

- `bipartite_graphs/*.json`
- `graph_manifest.json`
- `graph_index.json`
- `conversion_failures.json`

### 6.4 相似度检索入口（复用 v1）

路径：`pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_similarity_on_v1_graphs.py`

作用：读取 `graph_index.json`，进行 Top-k 检索并输出 `similarity_report.json`。

底层依赖：

- `src/cp2graph/v1_graph_io.py`
- `src/cp2graph/similarity.py`

### 6.5 `analyze_rsp_pipeline.py`

路径：`pipeline_cp_log_to_bigraph/Rtest/flow/analyze_rsp_pipeline.py`

作用：汇总本批次运行质量报告（json + md）。

### 6.6 `generate_batch_index.py`

路径：`pipeline_cp_log_to_bigraph/Rtest/flow/generate_batch_index.py`

作用：扫描所有 `batch_*`，自动更新：

- `Rtest/BATCH_INDEX.md`
- `Rtest/BATCH_INDEX.json`

---

## 7. 使用建议

1. 后续你改 RSP2 数据逻辑时，统一在 `Rtest/RSP2` 下修改。
2. 每次跑新测试加 `--run-tag` 和 `--run-purpose`，方便追溯。
3. 通过 `BATCH_INDEX.md` 先看全局，再进入单个 `batch_*` 细看。

---

## 8. 相关文档

- 批次总索引：`pipeline_cp_log_to_bigraph/Rtest/BATCH_INDEX.md`
- 命令说明：`pipeline_cp_log_to_bigraph/Rtest/COMMANDS_RTEST_ZH.md`
