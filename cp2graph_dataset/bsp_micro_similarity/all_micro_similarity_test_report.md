# 全类别 Micro 二分图相似度测试报告

## 1. 测试目标

本轮测试把 BSP micro 实验扩展到 `cp2graph_dataset` 的 13 个问题类。每类保留或生成 20 个只包含少量局部子图差异的 micro variant，总计 260 个 micro 图。

测试分为两项：

1. `micro variant -> 原始问题实例`：以 micro 图为 query，在 26 个原始问题实例图中检索 Top-5，检查是否找回对应类别和具体 base 编号。
2. `micro variant -> micro variant 自身`：以 260 个 micro 图组成图库，任选一个 micro 图作为 query，检查 Top-1 是否召回它自身。

## 2. 数据与目录

- 原始图目录：`cp2graph_dataset/graphs`
- Micro 图目录：`cp2graph_dataset/bsp_micro_similarity/variant_graphs`
- 分类清单：`cp2graph_dataset/bsp_micro_similarity/all_micro_manifest.json`
- BSP：复用已生成的 20 个 micro 图，并复制到分类子目录。
- 剩余 12 类：每类新生成 20 个 micro 图。

## 3. 问题类覆盖

| 类别目录 | 问题类 | Base 实例 | Micro 图数量 |
|---|---|---|---:|
| `batch_scheduling_problem` | Batch Scheduling Problem | `01_batch_scheduling_problem_01, 01_batch_scheduling_problem_02` | 20 |
| `emergency_staff_scheduling_optimization` | emergency_staff_scheduling_optimization | `02_emergency_staff_scheduling_optimization_01, 02_emergency_staff_scheduling_optimization_02` | 20 |
| `flexible_job_shop_problem_fjsp` | Flexible Job Shop Problem (FJSP) | `03_flexible_job_shop_problem_fjsp_01, 03_flexible_job_shop_problem_fjsp_02` | 20 |
| `flexible_job_shop_problem_with_machine_changeover_times` | Flexible Job Shop Problem with Machine Changeover Times | `04_flexible_job_shop_problem_with_machine_changeover_times_01, 04_flexible_job_shop_problem_with_machine_changeover_times_02` | 20 |
| `flexible_job_shop_problem_with_setup_times_fjsp_sdst` | Flexible Job Shop Problem with Setup Times (FJSP-SDST) | `05_flexible_job_shop_problem_with_setup_times_fjsp_sdst_01, 05_flexible_job_shop_problem_with_setup_times_fjsp_sdst_02` | 20 |
| `flexible_resource_constrained_project_scheduling_problem_frcpsp` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | `06_flexible_resource_constrained_project_scheduling_problem_frcpsp_01, 06_flexible_resource_constrained_project_scheduling_problem_frcpsp_02` | 20 |
| `job_shop_scheduling_problem_jssp` | Job Shop Scheduling Problem (JSSP) | `07_job_shop_scheduling_problem_jssp_01, 07_job_shop_scheduling_problem_jssp_02` | 20 |
| `job_shop_scheduling_problem_with_intensity` | Job Shop Scheduling Problem with Intensity | `08_job_shop_scheduling_problem_with_intensity_01, 08_job_shop_scheduling_problem_with_intensity_02` | 20 |
| `open_shop_scheduling_problem` | Open Shop Scheduling Problem | `09_open_shop_scheduling_problem_01, 09_open_shop_scheduling_problem_02` | 20 |
| `rsp` | RSP | `10_rsp_01, 10_rsp_02` | 20 |
| `scheduling_problem` | Scheduling Problem | `11_scheduling_problem_01, 11_scheduling_problem_02` | 20 |
| `stochastic_job_shop_scheduling_problem` | Stochastic Job Shop Scheduling Problem | `12_stochastic_job_shop_scheduling_problem_01, 12_stochastic_job_shop_scheduling_problem_02` | 20 |
| `surgery_scheduling` | surgery scheduling | `13_surgery_scheduling_01, 13_surgery_scheduling_02` | 20 |

## 4. 相似度权重

| 指标 | 权重 |
|---|---:|
| WL | 0.35 |
| TED | 0.20 |
| Jaccard | 0.15 |
| Collapse-Match | 0.30 |

## 5. 测试一：Micro 召回原始问题实例

候选图库为 26 个原始问题实例图。结果 JSON 中为每个 query 保存了 Top-5 候选及各项分数：`structure_score`、`wl_similarity`、`ted_similarity`、`collapse_match_similarity`、`jaccard_similarity`、`fusion_score`。

| 指标 | 数值 |
|---|---:|
| Query 数量 | 260 |
| 原始候选实例数 | 26 |
| 粗筛候选数 | 8 |
| Top-1 具体 base 正确率 | 1.0000 |
| Top-1 问题类别正确率 | 1.0000 |
| Top-5 具体 base 正确率 | 1.0000 |
| Top-5 问题类别正确率 | 1.0000 |

### 5.1 分类别结果

| 类别目录 | 问题类 | Query | Top-1 Base Acc | Top-1 Category Acc | Top-5 Base Acc | Top-5 Category Acc |
|---|---|---:|---:|---:|---:|---:|
| `batch_scheduling_problem` | Batch Scheduling Problem | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `emergency_staff_scheduling_optimization` | emergency_staff_scheduling_optimization | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `flexible_job_shop_problem_fjsp` | Flexible Job Shop Problem (FJSP) | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `flexible_job_shop_problem_with_machine_changeover_times` | Flexible Job Shop Problem with Machine Changeover Times | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `flexible_job_shop_problem_with_setup_times_fjsp_sdst` | Flexible Job Shop Problem with Setup Times (FJSP-SDST) | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `flexible_resource_constrained_project_scheduling_problem_frcpsp` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `job_shop_scheduling_problem_jssp` | Job Shop Scheduling Problem (JSSP) | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `job_shop_scheduling_problem_with_intensity` | Job Shop Scheduling Problem with Intensity | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `open_shop_scheduling_problem` | Open Shop Scheduling Problem | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `rsp` | RSP | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `scheduling_problem` | Scheduling Problem | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `stochastic_job_shop_scheduling_problem` | Stochastic Job Shop Scheduling Problem | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `surgery_scheduling` | surgery scheduling | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### 5.2 Top-5 样例

下面展开前 5 个 query 的 Top-5 候选。完整 260 个 query 的 Top-5 分数保存在 `all_micro_base_retrieval_eval.json`。

| Query | Expected Base | Rank | Candidate | Candidate 类别 | Fusion | Structure | WL | TED | CM | Jaccard |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 1 | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.997612 | 0.999326 | 0.998492 | 0.998415 | 0.998415 | 0.997895 |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 2 | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.466675 | 0.973994 | 0.765192 | 0.156894 | 0.156894 | 0.878968 |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 3 | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | 0.063134 | 0.728752 | 0.002956 | 0.000792 | 0.000792 | 0.515748 |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 4 | `11_scheduling_problem_01` | Scheduling Problem | 0.057466 | 0.655272 | 0.005767 | 0.000792 | 0.000792 | 0.520761 |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 5 | `10_rsp_01` | RSP | 0.051159 | 0.436559 | 0.173887 | 0.029319 | 0.029319 | 0.379167 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 1 | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.993282 | 0.997734 | 0.996764 | 0.995098 | 0.995098 | 0.995781 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 2 | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.467714 | 0.976859 | 0.764928 | 0.155432 | 0.155432 | 0.880952 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 3 | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | 0.068879 | 0.744966 | 0.015111 | 0.004085 | 0.004085 | 0.516765 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 4 | `11_scheduling_problem_01` | Scheduling Problem | 0.063112 | 0.668455 | 0.023584 | 0.003268 | 0.003268 | 0.519031 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 5 | `10_rsp_01` | RSP | 0.053687 | 0.444491 | 0.179897 | 0.031863 | 0.031863 | 0.379958 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 1 | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.995027 | 0.999326 | 0.997207 | 0.997623 | 0.997623 | 0.987500 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 2 | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.465213 | 0.973994 | 0.765080 | 0.156894 | 0.156894 | 0.870334 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 3 | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | 0.061556 | 0.728752 | 0.000000 | 0.000000 | 0.000000 | 0.510721 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 4 | `11_scheduling_problem_01` | Scheduling Problem | 0.055531 | 0.655272 | 0.000000 | 0.000000 | 0.000000 | 0.516295 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 5 | `10_rsp_01` | RSP | 0.051333 | 0.436559 | 0.176074 | 0.029319 | 0.029319 | 0.375258 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 1 | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.994184 | 0.997734 | 0.998110 | 0.996732 | 0.996732 | 0.993684 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 2 | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.467831 | 0.976859 | 0.764990 | 0.156225 | 0.156225 | 0.879208 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 3 | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | 0.067728 | 0.744966 | 0.012070 | 0.003268 | 0.003268 | 0.515748 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 4 | `11_scheduling_problem_01` | Scheduling Problem | 0.061486 | 0.668455 | 0.017660 | 0.002451 | 0.002451 | 0.518135 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | 5 | `10_rsp_01` | RSP | 0.054020 | 0.444491 | 0.182155 | 0.031863 | 0.031863 | 0.379167 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 1 | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.997686 | 0.999326 | 0.998594 | 0.999208 | 0.999208 | 0.995798 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 2 | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.466477 | 0.973994 | 0.765468 | 0.156894 | 0.156894 | 0.877228 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 3 | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | 0.062040 | 0.728752 | 0.000000 | 0.000000 | 0.000000 | 0.514735 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 4 | `11_scheduling_problem_01` | Scheduling Problem | 0.056197 | 0.655272 | 0.000000 | 0.000000 | 0.000000 | 0.522491 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | 5 | `10_rsp_01` | RSP | 0.051619 | 0.436559 | 0.176163 | 0.029319 | 0.029319 | 0.381250 |

## 6. 测试二：260 个 Micro 图内部自召回

候选图库为全部 260 个 micro variant。为了控制大图精排成本，先使用 WL/Jaccard 粗筛，再对 shortlist 做 TED、Collapse-Match 和融合排序。每个 query 的 Top-5 仍完整保存在 JSON 中。

| 指标 | 数值 |
|---|---:|
| Query 数量 | 260 |
| Micro 候选图数量 | 260 |
| 粗筛候选数 | 8 |
| Top-1 自召回正确率 | 1.0000 |
| Top-5 自召回正确率 | 1.0000 |

### 6.1 自召回 Top-5 样例

下面展开前 5 个 query 在 260 个 micro 图图库中的 Top-5 候选。完整结果保存在 `all_micro_self_recall_eval.json`。

| Query | Rank | Candidate | Candidate 类别 | Fusion | Structure | WL | TED | CM | Jaccard | 自身命中 |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | 1 | `bsp_micro_01_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | True |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | 2 | `bsp_micro_17_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998559 | 1.000000 | 0.998034 | 0.998415 | 0.998415 | 1.000000 | False |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | 3 | `bsp_micro_11_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998346 | 1.000000 | 0.997390 | 0.998415 | 0.998415 | 1.000000 | False |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | 4 | `bsp_micro_07_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998335 | 1.000000 | 0.997356 | 0.998415 | 0.998415 | 1.000000 | False |
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | 5 | `bsp_micro_13_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998034 | 1.000000 | 0.997525 | 0.998415 | 0.998415 | 0.997899 | False |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | 1 | `bsp_micro_02_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | True |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | 2 | `bsp_micro_16_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996708 | 1.000000 | 0.994974 | 0.996732 | 0.996732 | 1.000000 | False |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | 3 | `bsp_micro_04_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996371 | 1.000000 | 0.995040 | 0.996732 | 0.996732 | 0.997895 | False |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | 4 | `bsp_micro_14_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996199 | 1.000000 | 0.995757 | 0.995915 | 0.995915 | 0.997895 | False |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | 5 | `bsp_micro_08_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996141 | 1.000000 | 0.995580 | 0.995915 | 0.995915 | 0.997895 | False |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | 1 | `bsp_micro_03_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | True |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | 2 | `bsp_micro_13_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.996289 | 1.000000 | 0.996649 | 0.997623 | 0.997623 | 0.991667 | False |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | 3 | `bsp_micro_09_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.996122 | 1.000000 | 0.995193 | 0.996830 | 0.996830 | 0.995842 | False |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | 4 | `bsp_micro_17_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.995968 | 1.000000 | 0.996750 | 0.997623 | 0.997623 | 0.989583 | False |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | 5 | `bsp_micro_11_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.995756 | 1.000000 | 0.996107 | 0.997623 | 0.997623 | 0.989583 | False |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | 1 | `bsp_micro_04_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | True |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | 2 | `bsp_micro_14_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.997667 | 1.000000 | 0.996644 | 0.997549 | 0.997549 | 1.000000 | False |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | 3 | `bsp_micro_08_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996999 | 1.000000 | 0.996785 | 0.997549 | 0.997549 | 0.995798 | False |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | 4 | `bsp_micro_20_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996894 | 1.000000 | 0.996467 | 0.997549 | 0.997549 | 0.995798 | False |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | 5 | `bsp_micro_10_from_01_batch_scheduling_problem_02` | Batch Scheduling Problem | 0.996627 | 1.000000 | 0.996894 | 0.996732 | 0.996732 | 0.995798 | False |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | 1 | `bsp_micro_05_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | True |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | 2 | `bsp_micro_17_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998632 | 1.000000 | 0.998137 | 0.999208 | 0.999208 | 0.997899 | False |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | 3 | `bsp_micro_11_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998475 | 1.000000 | 0.997663 | 0.999208 | 0.999208 | 0.997899 | False |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | 4 | `bsp_micro_07_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998397 | 1.000000 | 0.997426 | 0.999208 | 0.999208 | 0.997899 | False |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | 5 | `bsp_micro_13_from_01_batch_scheduling_problem_01` | Batch Scheduling Problem | 0.998097 | 1.000000 | 0.997595 | 0.999208 | 0.999208 | 0.995807 | False |

## 7. 输出文件

- `all_micro_manifest.json`：260 个 micro 图的分类清单。
- `all_micro_base_retrieval_eval.json`：micro 查询 26 个原始问题实例的 Top-5 详细分数。
- `all_micro_base_retrieval_eval.csv`：测试一的扁平摘要。
- `all_micro_self_recall_eval.json`：260 个 micro 图内部自召回的 Top-5 详细分数。
- `all_micro_self_recall_eval.csv`：测试二的扁平摘要。
- `all_micro_similarity_test_report.md`：本文档。

## 8. 结论

- Micro 召回原始问题实例：Top-1 具体 base 正确率为 `1.0000`，Top-1 类别正确率为 `1.0000`。
- Micro 图内部自召回：Top-1 准确率为 `1.0000`。
- 本轮测试覆盖全部 13 个问题类；BSP micro 图已按类别目录整理，剩余 12 类已补齐生成。
