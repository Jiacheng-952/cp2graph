# RSP2 数据颗粒度与调参说明

## 1. 现在的数据颗粒度到底是什么

当前不是“只按三类固定模板”。

现状是两层结构：

1. `easy / medium / hard` 只负责给出硬边界（上界/下界）。
2. 每次在边界内按 `scenario` + 连续参数随机采样，再经过可行性过滤与 solver 兜底。

所以粒度是“**三类边界 + 类内连续变化**”，不是三套写死结构。

路径约定（避免旧目录混淆）：

- 当前有效数据工作位是每个批次内的 `batch_xxx/RSP/data/*.json`。
- `Rtest` 根目录旧工作位已归档到 `Rtest/_archive/RSP_root_legacy_workspace/`，不参与当前链路。

## 2. 当前每类硬边界范围（来自 generate.py）

文件：`RSP2/generate.py -> default_profile_ranges()`

### easy
- `num_stations`: 4 ~ 20
- `num_trains`: 4 ~ 30（并受 `num_stations * [1.1, 2.2]` 二次约束）
- `station_capacity`: 2 ~ 6
- `station_duration`: 1 ~ 4
- `track_capacity`: 2 ~ 5
- `track_duration`: 2 ~ 6
- `maintenance_duration`: 6 ~ 25
- `maintenance_gap`: 20 ~ 120

### medium
- `num_stations`: 8 ~ 45
- `num_trains`: 8 ~ 70（并受 `num_stations * [1.1, 2.2]` 二次约束）
- `station_capacity`: 1 ~ 5
- `station_duration`: 1 ~ 7
- `track_capacity`: 1 ~ 4
- `track_duration`: 3 ~ 9
- `maintenance_duration`: 10 ~ 45
- `maintenance_gap`: 8 ~ 90

### hard
- `num_stations`: 12 ~ 90
- `num_trains`: 12 ~ 110（并受 `num_stations * [1.1, 2.2]` 二次约束）
- `station_capacity`: 1 ~ 4
- `station_duration`: 2 ~ 10
- `track_capacity`: 1 ~ 3
- `track_duration`: 4 ~ 12
- `maintenance_duration`: 12 ~ 70
- `maintenance_gap`: 0 ~ 70

## 3. 类内高颗粒度参数（真正拉开差异）

文件：`RSP2/generate.py -> _sample_profile_config()`

这些参数决定“同一类内部”的结构差异：

- `scenario`: 场景模式（balanced/asymmetric/bottleneck/maintenance_tight 等）
- `reverse_link_prob`: 反向边概率
- `bypass_prob`: 跨越一站的旁路概率
- `jump_prob`: 跨越两站以上跳跃边概率
- `bottleneck_ratio`: 瓶颈轨道注入比例
- `train_speed_noise`: 车速扰动（影响列车个体 `d_ir` 风格时长）
- `route0_bias`: 列车偏向主路线的概率
- `maintenance_overlap_bias`: 维修窗口与车流重叠概率

结论：你关心的“同样100站，稍微改一辆车/通过时长就有结构变化”主要靠这组参数驱动。

## 4. 可行性相关调参点（A任务核心）

文件：`RSP2/generate.py`

### 4.1 全局设置
- `max_attempts_per_instance`: 每个实例最大重采样次数（默认 200）
- `feasibility_time_limit_sec`: solver 校验时间上限（默认 8 秒）

### 4.2 规模闸门
- `rough_horizon > 9000` 则丢弃候选（生成阶段快速剪枝）

### 4.3 快速可行性过滤
- `horizon_limit = 10000`
- `safety_margin = 200`
- `hard_cap = 9800`
- 通过 `train_lb / resource_lb / combined_lb` 过滤高风险样本

## 5. 你后续应该重点关注的参数（按优先级）

### 第一优先级（直接影响图结构）
- `num_stations`
- `num_trains`
- `track_capacity`
- `track_duration`
- `bypass_prob / jump_prob / reverse_link_prob`

### 第二优先级（影响冲突模式与可行性边界）
- `bottleneck_ratio`
- `maintenance_duration`
- `maintenance_gap`
- `maintenance_overlap_bias`

### 第三优先级（细粒度差异，适配未来相似度指标）
- `train_speed_noise`
- `route0_bias`

## 6. 面向“100站台实验”的建议

如果你后续要专做 100 站附近：

1. 先把 `num_stations` 固定在窄区间（例如 90~100 或 100 固定）。
2. 重点扫描 `num_trains`、`train_speed_noise`、`bottleneck_ratio`、`maintenance_overlap_bias`。
3. 保持可行性兜底开启（quick filter + solver check），不要走穷举。
4. 每轮实验单独跑一个 `batch_*`，保留全量历史供检索评测。

## 7. 这份文档对应的代码入口

- 参数边界：`RSP2/generate.py -> default_profile_ranges`
- 场景采样：`RSP2/generate.py -> _sample_profile_config`
- 可行性兜底：`RSP2/generate.py -> generate_feasible_instance`
- 流程入口：`Rtest/flow/run_rtest_pipeline.py`

默认运行建议：

- 使用 `source-kind=rsp2` 且不加 `--use-existing-data`，确保使用“当前生成器逻辑”的新数据。
