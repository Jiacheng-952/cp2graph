# RSP2 链路说明（重点：可行性兜底机制）

## 1. RSP2 的角色

`RSP2` 提供两类上游能力：

1. 数据生成：`RSP2/generate.py`
2. 求解与建模：`RSP2/solver.py`

真正的闭环运行在 `Rtest/batch_*` 中完成。

附加约定（避免路径混淆）：

- `Rtest` 根目录旧工作位已归档到 `Rtest/_archive/RSP_root_legacy_workspace/`。
- 新测试不要再读取归档目录；统一以 `batch_xxx/RSP/` 为运行工作位。

## 2. 数据如何进入闭环

入口是 `Rtest/flow/run_rtest_pipeline.py`，它先调用 `create_rsp_pack.py`：

1. 创建本次批次目录 `batch_xxx/`
2. 在批次内创建工作位 `batch_xxx/RSP/`
3. 将数据准备到 `batch_xxx/RSP/data/*.json`（两种方式）：
- 复制 `RSP2/data/*.json`
- 或运行 `RSP2/generate.py` 动态生成
4. 复制 `RSP2/solver.py` 到 `batch_xxx/RSP/solver.py`

后续所有步骤统一只读取批次内这份 `RSP/data` 和 `RSP/solver.py`。

默认建议：

- 不加 `--use-existing-data`，优先使用 `RSP2/generate.py` 现生成数据。

## 3. CP 模型如何实例化

由 `Rtest/flow/generate_rsp_protos.py` 完成（RSP2 默认 `solver_capture`）：

1. 枚举 `batch_xxx/RSP/data/*.json`
2. 对每个实例调用 `solver.py`：
- `load_instance_data(...)`：JSON 转建模输入
- `solve_with_ortools(...)`：内部执行 `cp_model.CpModel()` 并加约束
3. `generate_rsp_protos.py` monkey patch `cp_model.CpModel`，捕获模型对象
4. 对该对象执行 `model.Proto()`，写入 `protos/proto_XXXX.pb`

结论：CP 模型是“每个实例运行时动态实例化”，不是静态文件。

## 4. 可行性兜底机制（详细）

位置：`RSP2/generate.py`  
目标：保证生成的数据尽量“可解且多样”，避免大量无效样本进入后链路。

### 4.1 总体流程

`generate_feasible_instance(...)` 中每个实例按以下顺序重试：

1. 采样参数与场景 `_sample_profile_config`
2. 粗粒度规模闸门（`rough_horizon`）
3. 构造实例 `_build_instance`
4. 快速可行性过滤 `_quick_feasibility_filter`
5. 严格校验 + solver 终检 `_validate_feasibility`
6. 若失败则重采样，直到 `max_attempts_per_instance`

### 4.2 第一层：粗粒度规模闸门（便宜且快）

代码逻辑：

- `rough_horizon = num_stations * (station_duration_base + track_duration_base) * num_trains`
- 若 `rough_horizon > 9000`，直接丢弃当前参数，进入下一次尝试

意义：

- 先剪掉明显超大规模组合，减少后续构图/求解浪费。

### 4.3 第二层：快速可行性过滤 `_quick_feasibility_filter`

这层是“近似保守过滤”，不求精确最优，只求快速排雷。

核心常量：

- `horizon_limit = 10000`
- `safety_margin = 200`
- `hard_cap = 9800`

主要检查：

1. 路径合法性
- 路线不能为空
- 车的起点必须在其路线中
- 截断后路径长度不能过短

2. 单车路径时间下界
- 对每辆车计算从起点到终点的最小时长 `train_lb`
- 若 `train_lb > hard_cap`，直接拒绝

3. 资源负载下界
- 对每个资源累计工作量 `workload`
- 估计资源下界 `resource_lb = ceil(workload / capacity)`
- 若该资源是维修轨道且有受影响列车，加上维修时长惩罚
- 若任何 `resource_lb > hard_cap`，拒绝

4. 组合下界
- `combined_lb = max(max_train_path_lb, max_resource_lb)`
- 若 `combined_lb > hard_cap`，拒绝

输出：

- 通过：`(True, "quick_filter_pass", diagnostics)`
- 失败：`(False, reason_code, diagnostics)`

已定义失败码示例：

- `quick_filter_empty_route`
- `quick_filter_start_not_in_route`
- `quick_filter_too_short_path`
- `quick_filter_train_lb_over_cap`
- `quick_filter_resource_lb_over_cap`
- `quick_filter_combined_lb_over_cap`

会落盘到实例：

- `feasibility.quick_filter`
- `feasibility.quick_filter_diagnostics`

### 4.4 第三层：严格结构校验 `_hard_sanity_check`

在 solver 前做硬一致性检查：

1. 核心数组是否为空（trains/stations/tracks/routes）
2. 初始站点容量总和是否覆盖列车数（t=0 可放下）
3. 每列车 route id 是否存在
4. 列车 start 是否在 route 中
5. route 中的站点/轨道 id 是否都在定义表里

失败会返回明确原因，例如：

- `missing core arrays`
- `insufficient station start capacity for t=0`
- `train route id missing`
- `train start not in route`
- `route station id not defined`
- `route track id not defined`

### 4.5 第四层：solver 终检 `_validate_feasibility`

流程：

1. 先过 `_hard_sanity_check`
2. 将实例转为 solver 输入 `_to_solver_input`
3. 调 `solver.solve_with_ortools(...)`，时间上限为 `feasibility_time_limit_sec`
4. 只要返回非空解，即视为可行（`OPTIMAL/FEASIBLE`）

通过后在实例里记录：

- `feasibility.validated = true`
- `feasibility.attempt`
- `feasibility.check_stage = "solver_check"`
- `feasibility.solver_status`
- `feasibility.total_delay`

### 4.6 失败后的重采样策略

外层 `for attempt in range(1, max_attempts+1)` 控制：

1. 任一层失败都不会终止批次，只丢弃当前候选继续采样
2. 每次尝试用不同 seed（`base_seed + attempt * 1009`）
3. 达到最大尝试次数仍失败，才抛异常

这保证了：

- 单个坏样本不会拖死整批流程
- 参数空间会持续探索，不会卡死在同一构型

## 5. 这套兜底机制对后续 Proto/二分图的影响

1. Proto 生成更稳定
- 无效或高风险样本在前层已被筛掉，减少 proto 阶段失败。

2. 图结构差异更可信
- 进入图阶段的样本可行且结构真实，二分图差异更有解释力。

3. 为后续相似度重构提供特征
- 可直接利用 `quick_filter_diagnostics`、`generation_features`、`train_profiles` 做更细粒度指标。

## 6. 关键文件

- 生成器：`pipeline_cp_log_to_bigraph/Rtest/RSP2/generate.py`
- 求解器：`pipeline_cp_log_to_bigraph/Rtest/RSP2/solver.py`
- 装配脚本：`pipeline_cp_log_to_bigraph/Rtest/flow/create_rsp_pack.py`
- Proto 脚本：`pipeline_cp_log_to_bigraph/Rtest/flow/generate_rsp_protos.py`
- 建图脚本：`pipeline_cp_log_to_bigraph/Rtest/flow/build_rsp_graphs_from_protos.py`
- 相似度脚本：`pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_similarity_on_v1_graphs.py`
