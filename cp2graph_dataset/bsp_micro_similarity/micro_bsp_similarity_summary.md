# BSP 微扰二分图相似度测试

## 测试理解

- 数据来源：`14类cp问题数据/Batch Scheduling Problem` 经 `cp2graph_dataset` 已转换出的 BSP 二分图。
- 构造方式：以 BSP 原图为 base，生成 20 个只含少量局部子图差异的 query 变体。
- 预期答案：每个变体都应该检索回它对应的原始 BSP base 图。
- 图库候选：BSP base 图 + 其他类别图，检验模型是否能从干扰图里找回正确 base。

## 权重

- WL：0.35
- TED：0.2
- Jaccard：0.15
- Collapse-Match：0.3

## 结果

- Query 数量：20
- 候选图数量：26
- Top-1 正确数：20
- Top-1 准确率：1.0000
- Top-5 正确数：20
- Top-5 准确率：1.0000

## 明细

| Query | Expected | Top-1 | 正确 | Fusion | WL | TED | CM | Jaccard |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.997612 | 0.998492 | 0.998415 | 0.998415 | 0.997895 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.993282 | 0.996764 | 0.995098 | 0.995098 | 0.995781 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.995027 | 0.997207 | 0.997623 | 0.997623 | 0.987500 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994184 | 0.998110 | 0.996732 | 0.996732 | 0.993684 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.997686 | 0.998594 | 0.999208 | 0.999208 | 0.995798 |
| `bsp_micro_06_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.992280 | 0.996775 | 0.995915 | 0.995915 | 0.987448 |
| `bsp_micro_07_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.998120 | 0.998831 | 0.999208 | 0.999208 | 0.997895 |
| `bsp_micro_08_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994767 | 0.998641 | 0.997549 | 0.997549 | 0.993684 |
| `bsp_micro_09_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.995668 | 0.997951 | 0.998415 | 0.998415 | 0.987500 |
| `bsp_micro_10_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994383 | 0.998713 | 0.996732 | 0.996732 | 0.993684 |
| `bsp_micro_11_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.998142 | 0.998899 | 0.999208 | 0.999208 | 0.997895 |
| `bsp_micro_12_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.992849 | 0.997264 | 0.996732 | 0.996732 | 0.987448 |
| `bsp_micro_13_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.997820 | 0.999001 | 0.999208 | 0.999208 | 0.995798 |
| `bsp_micro_14_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994674 | 0.998358 | 0.997549 | 0.997549 | 0.993684 |
| `bsp_micro_15_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.995081 | 0.997373 | 0.997623 | 0.997623 | 0.987500 |
| `bsp_micro_16_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994273 | 0.997298 | 0.996732 | 0.996732 | 0.995781 |
| `bsp_micro_17_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.998354 | 0.999543 | 0.999208 | 0.999208 | 0.997895 |
| `bsp_micro_18_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.991905 | 0.996698 | 0.995915 | 0.995915 | 0.985386 |
| `bsp_micro_19_from_01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | `01_batch_scheduling_problem_01` | True | 0.997775 | 0.998865 | 0.999208 | 0.999208 | 0.995798 |
| `bsp_micro_20_from_01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | `01_batch_scheduling_problem_02` | True | 0.994651 | 0.998288 | 0.997549 | 0.997549 | 0.993684 |
