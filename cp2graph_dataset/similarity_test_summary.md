# cp2graph_dataset 图相似度测试总结

## 测试设置

- 数据来源：`14类cp问题数据`，排除 `gortek`。
- 数据集：13 类问题，每类取 `data/` 下按文件名排序的前 2 条 JSON 数据。
- 总模型数：26。
- 转换链路：`solver.py/solve.py -> CpModelProto -> 二分图 JSON -> 图相似度检索`。
- 评估方式：leave-one-out。每次选 1 个 CP 模型作为 query，从剩余 25 个模型中检索最相似模型。
- 粗筛候选数：25。
- 判定标准：检索结果与 query 属于同一问题类别则为正确。

## 总体结果

- Query 数量：26
- Top-1 正确数：21
- Top-1 准确率：0.8077
- Top-5 正确数：21
- Top-5 准确率：0.8977

## 示例检索

- Query：`01_batch_scheduling_problem_01`
- Query 类别：Batch Scheduling Problem
- Top-1：`01_batch_scheduling_problem_02`
- Top-1 类别：Batch Scheduling Problem
- 是否正确：True
- Fusion：0.475308
- WL：0.765507
- TED：0.157018
- CM：0.157018
- Jaccard：0.880716

## 明细

| Query | 类别 | Top-1 | Top-1 类别 | 正确 | Fusion |
|---|---|---|---|---:|---:|
| `01_batch_scheduling_problem_01` | Batch Scheduling Problem | `01_batch_scheduling_problem_02` | Batch Scheduling Problem | True | 0.475308 |
| `01_batch_scheduling_problem_02` | Batch Scheduling Problem | `01_batch_scheduling_problem_01` | Batch Scheduling Problem | True | 0.475308 |
| `02_emergency_staff_scheduling_optimization_01` | emergency_staff_scheduling_optimization | `02_emergency_staff_scheduling_optimization_02` | emergency_staff_scheduling_optimization | True | 0.782410 |
| `02_emergency_staff_scheduling_optimization_02` | emergency_staff_scheduling_optimization | `02_emergency_staff_scheduling_optimization_01` | emergency_staff_scheduling_optimization | True | 0.782410 |
| `03_flexible_job_shop_problem_fjsp_01` | Flexible Job Shop Problem (FJSP) | `03_flexible_job_shop_problem_fjsp_02` | Flexible Job Shop Problem (FJSP) | True | 0.393895 |
| `03_flexible_job_shop_problem_fjsp_02` | Flexible Job Shop Problem (FJSP) | `03_flexible_job_shop_problem_fjsp_01` | Flexible Job Shop Problem (FJSP) | True | 0.393895 |
| `04_flexible_job_shop_problem_with_machine_changeover_times_01` | Flexible Job Shop Problem with Machine Changeover Times | `04_flexible_job_shop_problem_with_machine_changeover_times_02` | Flexible Job Shop Problem with Machine Changeover Times | True | 0.562808 |
| `04_flexible_job_shop_problem_with_machine_changeover_times_02` | Flexible Job Shop Problem with Machine Changeover Times | `04_flexible_job_shop_problem_with_machine_changeover_times_01` | Flexible Job Shop Problem with Machine Changeover Times | True | 0.562808 |
| `05_flexible_job_shop_problem_with_setup_times_fjsp_sdst_01` | Flexible Job Shop Problem with Setup Times (FJSP-SDST) | `10_rsp_01` | RSP | False | 0.345784 |
| `05_flexible_job_shop_problem_with_setup_times_fjsp_sdst_02` | Flexible Job Shop Problem with Setup Times (FJSP-SDST) | `05_flexible_job_shop_problem_with_setup_times_fjsp_sdst_01` | Flexible Job Shop Problem with Setup Times (FJSP-SDST) | True | 0.305857 |
| `06_flexible_resource_constrained_project_scheduling_problem_frcpsp_01` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | `06_flexible_resource_constrained_project_scheduling_problem_frcpsp_02` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | True | 0.393897 |
| `06_flexible_resource_constrained_project_scheduling_problem_frcpsp_02` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | `06_flexible_resource_constrained_project_scheduling_problem_frcpsp_01` | Flexible Resource-Constrained Project Scheduling Problem (FRCPSP) | True | 0.393897 |
| `07_job_shop_scheduling_problem_jssp_01` | Job Shop Scheduling Problem (JSSP) | `08_job_shop_scheduling_problem_with_intensity_01` | Job Shop Scheduling Problem with Intensity | False | 0.174693 |
| `07_job_shop_scheduling_problem_jssp_02` | Job Shop Scheduling Problem (JSSP) | `11_scheduling_problem_01` | Scheduling Problem | False | 0.119153 |
| `08_job_shop_scheduling_problem_with_intensity_01` | Job Shop Scheduling Problem with Intensity | `07_job_shop_scheduling_problem_jssp_01` | Job Shop Scheduling Problem (JSSP) | False | 0.174693 |
| `08_job_shop_scheduling_problem_with_intensity_02` | Job Shop Scheduling Problem with Intensity | `09_open_shop_scheduling_problem_01` | Open Shop Scheduling Problem | False | 0.126461 |
| `09_open_shop_scheduling_problem_01` | Open Shop Scheduling Problem | `09_open_shop_scheduling_problem_02` | Open Shop Scheduling Problem | True | 0.408924 |
| `09_open_shop_scheduling_problem_02` | Open Shop Scheduling Problem | `09_open_shop_scheduling_problem_01` | Open Shop Scheduling Problem | True | 0.408924 |
| `10_rsp_01` | RSP | `10_rsp_02` | RSP | True | 0.735769 |
| `10_rsp_02` | RSP | `10_rsp_01` | RSP | True | 0.735769 |
| `11_scheduling_problem_01` | Scheduling Problem | `11_scheduling_problem_02` | Scheduling Problem | True | 0.544980 |
| `11_scheduling_problem_02` | Scheduling Problem | `11_scheduling_problem_01` | Scheduling Problem | True | 0.544980 |
| `12_stochastic_job_shop_scheduling_problem_01` | Stochastic Job Shop Scheduling Problem | `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | True | 0.489033 |
| `12_stochastic_job_shop_scheduling_problem_02` | Stochastic Job Shop Scheduling Problem | `12_stochastic_job_shop_scheduling_problem_01` | Stochastic Job Shop Scheduling Problem | True | 0.489033 |
| `13_surgery_scheduling_01` | surgery scheduling | `13_surgery_scheduling_02` | surgery scheduling | True | 0.766359 |
| `13_surgery_scheduling_02` | surgery scheduling | `13_surgery_scheduling_01` | surgery scheduling | True | 0.766359 |
