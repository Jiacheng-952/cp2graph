# BSP Micro 二分图相似度测试报告

## 1. 测试目标

本测试围绕 `Batch Scheduling Problem` 构造一组带有微小局部子图差异的二分图，用来验证当前 `cp2graph` 图相似度模块是否能够完成两类召回任务：

1. `micro variant -> 原始 BSP base 图`：验证微扰后的 BSP 图是否还能准确找回对应原图。
2. `micro variant -> micro variant 自身`：验证在 20 个 micro 图组成的图库中，任选一个 micro 图作为 query，是否能准确召回它自己的图。

这两个任务分别对应“对原始模型的鲁棒召回”和“图库内精确匹配召回”。

## 2. 数据来源

数据来自现有目录：

```text
14类cp问题数据/Batch Scheduling Problem
```

本次测试实际使用的是 `cp2graph_dataset` 中已经转换出的 BSP 二分图：

```text
cp2graph_dataset/graphs/01_batch_scheduling_problem_01.graph.json
cp2graph_dataset/graphs/01_batch_scheduling_problem_02.graph.json
```

以这两个 BSP 原始图为 base，生成 20 个 micro variant 图，输出目录为：

```text
cp2graph_dataset/bsp_micro_similarity/variant_graphs
```

生成清单：

```text
cp2graph_dataset/bsp_micro_similarity/micro_bsp_manifest.json
```

## 3. Micro 图构造方式

每个 micro variant 都从对应 BSP base 图复制而来，然后只做少量局部子图改动，保持整体仍是“变量节点 - 约束节点”的二分图。

本次使用的微扰操作包括：

- 增加一个局部 `linear` 约束节点，并连接少量变量节点。
- 部分样本增加一个布尔 guard 变量和 `bool_or` 约束子图。
- 部分样本修改一个已有约束节点的局部参数标记，使其语义哈希发生轻微变化。

这些改动会改变少量节点、边和标签原子，但不会改变 BSP 图的主体结构。

## 4. 相似度配置

本次测试使用同一组融合权重：

| 指标 | 权重 |
|---|---:|
| WL | 0.35 |
| TED | 0.20 |
| Jaccard | 0.15 |
| Collapse-Match | 0.30 |

为了避免粗筛阶段截断候选，本次测试将 `coarse_top_k` 设置为候选图库大小。

## 5. 测试一：Micro Variant 召回原始 BSP Base 图

### 5.1 测试设置

Query 图：

```text
20 个 micro variant 图
```

候选图库：

```text
2 个 BSP base 图 + 24 个其他类别图 = 26 个候选图
```

判定标准：

```text
每个 micro variant 的 Top-1 是否等于它对应的 expected_base_id
```

详细结果文件：

```text
cp2graph_dataset/bsp_micro_similarity/micro_bsp_similarity_eval.json
cp2graph_dataset/bsp_micro_similarity/micro_bsp_similarity_eval.csv
cp2graph_dataset/bsp_micro_similarity/micro_bsp_similarity_summary.md
```

### 5.2 总体结果

| 指标 | 数值 |
|---|---:|
| Query 数量 | 20 |
| 候选图数量 | 26 |
| Top-1 正确数 | 20 |
| Top-1 准确率 | 1.0000 |
| Top-5 正确数 | 20 |
| Top-5 准确率 | 1.0000 |

### 5.3 明细结果

| Query | Expected Base | Top-1 | 正确 | Fusion | WL | TED | CM | Jaccard |
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

## 6. 测试二：20 个 Micro 图内部自召回

### 6.1 测试设置

Query 图：

```text
variant_graphs 下的 20 个 micro variant 图
```

候选图库：

```text
同一个 variant_graphs 目录下的 20 个 micro variant 图
```

判定标准：

```text
每个 query 的 Top-1 是否等于 query 自身
```

详细结果文件：

```text
cp2graph_dataset/bsp_micro_similarity/micro_variant_self_recall_eval.json
```

### 6.2 总体结果

| 指标 | 数值 |
|---|---:|
| Micro 图数量 | 20 |
| Top-1 召回自身正确数 | 20 |
| Top-1 自召回准确率 | 1.0000 |

### 6.3 自召回样例

| Query | Top-1 | Fusion | WL | 正确 |
|---|---|---:|---:|---:|
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `bsp_micro_01_from_01_batch_scheduling_problem_01` | 1.000000 | 1.000000 | True |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `bsp_micro_02_from_01_batch_scheduling_problem_02` | 1.000000 | 1.000000 | True |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `bsp_micro_03_from_01_batch_scheduling_problem_01` | 1.000000 | 1.000000 | True |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `bsp_micro_04_from_01_batch_scheduling_problem_02` | 1.000000 | 1.000000 | True |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `bsp_micro_05_from_01_batch_scheduling_problem_01` | 1.000000 | 1.000000 | True |

### 6.4 排除自身后的最近邻

为了确认 20 个 micro 图之间的相似关系，额外做了“排除 query 自身后”的 Top-1 检索。结果显示，最近邻基本落在同一个 BSP base 来源下的其他 micro variant。

| Query | 排除自身后的 Top-1 | Fusion | WL |
|---|---|---:|---:|
| `bsp_micro_01_from_01_batch_scheduling_problem_01` | `bsp_micro_17_from_01_batch_scheduling_problem_01` | 0.998559 | 0.998034 |
| `bsp_micro_02_from_01_batch_scheduling_problem_02` | `bsp_micro_16_from_01_batch_scheduling_problem_02` | 0.996708 | 0.994974 |
| `bsp_micro_03_from_01_batch_scheduling_problem_01` | `bsp_micro_13_from_01_batch_scheduling_problem_01` | 0.996289 | 0.996649 |
| `bsp_micro_04_from_01_batch_scheduling_problem_02` | `bsp_micro_14_from_01_batch_scheduling_problem_02` | 0.997667 | 0.996644 |
| `bsp_micro_05_from_01_batch_scheduling_problem_01` | `bsp_micro_17_from_01_batch_scheduling_problem_01` | 0.998632 | 0.998137 |
| `bsp_micro_06_from_01_batch_scheduling_problem_02` | `bsp_micro_12_from_01_batch_scheduling_problem_02` | 0.996317 | 0.995030 |
| `bsp_micro_07_from_01_batch_scheduling_problem_01` | `bsp_micro_17_from_01_batch_scheduling_problem_01` | 0.999079 | 0.998408 |
| `bsp_micro_08_from_01_batch_scheduling_problem_02` | `bsp_micro_14_from_01_batch_scheduling_problem_02` | 0.997490 | 0.997035 |
| `bsp_micro_09_from_01_batch_scheduling_problem_01` | `bsp_micro_19_from_01_batch_scheduling_problem_01` | 0.996740 | 0.996816 |
| `bsp_micro_10_from_01_batch_scheduling_problem_02` | `bsp_micro_20_from_01_batch_scheduling_problem_02` | 0.997797 | 0.997037 |

## 7. 结论

本次测试中，当前 `cp2graph` 相似度模块在 BSP micro 二分图上通过了两类召回验证：

| 测试项 | Top-1 准确率 |
|---|---:|
| Micro variant 召回原始 BSP base 图 | 1.0000 |
| Micro variant 在 20 个 micro 图中召回自身 | 1.0000 |

结果说明，在本组 BSP 微扰图上，当前 WL、TED、Jaccard、Collapse-Match 融合权重能够稳定识别微小子图差异下的对应关系；同时，排除自身后的最近邻结果也符合预期，即同源 BSP base 的 micro variant 之间相似度最高。

## 8. 运行与验证记录

本次使用的实验脚本：

```text
scripts/evaluate_bsp_micro_similarity.py
```

核心命令：

```bash
python3 scripts/evaluate_bsp_micro_similarity.py
```

补充测试：

```text
20 个 variant_graphs 图内部 self-recall 测试
```

验证结果：

```text
python3 -m py_compile scripts/evaluate_bsp_micro_similarity.py 通过
```

已知环境说明：完整 `pytest` 当前有一个与本测试无关的既有失败，位置为 `tests/test_serialize.py::test_write_json_and_graphml`。失败原因是 NetworkX GraphML writer 不支持 graph-level 的 `shared_subexpressions` 字典类型。
