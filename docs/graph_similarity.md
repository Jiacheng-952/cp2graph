# 图相似度检索设计

本模块建立在现有 `cp2graph` 图构建能力之上，为 CP 模型提供一层图相似度检索与排序能力。

## 设计目标

- 保留 FlatZinc / MiniZinc 到二分图的构图流程
- 在图层面支持快速相似度匹配
- 为后续分类、检索、排序、候选召回提供统一入口
- 预留第二阶段的更精细图编辑距离近似能力

## 已复用的部分

- `parse_and_build_graph`：负责把 CP 模型解析并构造成图
- `normalize_model`：负责模型规范化
- `graph_builder`：负责变量节点、约束节点及边关系的生成

## 新增的部分

`cp2graph.similarity` 提供以下能力：

- `WL` 特征提取
- 结构兼容性过滤
- 标签 `Jaccard` 重叠计算
- 自适应融合排序
- 候选集索引与检索接口

## 第一版流程

1. 预先准备一个图库，每个 CP 模型对应一个图。
2. 离线计算每个图的 `WL` 特征和标签集合。
3. 查询时先做结构兼容性过滤，排除规模差异过大的候选。
4. 对剩余候选计算：
   - `WL` 相似度
   - 标签 `Jaccard` 相似度
   - 融合得分
5. 按融合得分排序，输出 Top-k 结果。

这一版是“图原生”的实现，不依赖树结构，因此还没有引入论文中的 `TED` 和 `Collapse-Match`。

## 核心 API

```python
from cp2graph.similarity import GraphSimilarityIndex, score_graph_pair
```

### `score_graph_pair(left, right, config=None)`

返回两个图的相似度结果，包含：

- `structure_score`
- `wl_similarity`
- `jaccard_similarity`
- `fusion_score`
- `passed_filter`

### `GraphSimilarityIndex(graphs, config=None)`

接收一个图库，参数可以是：

- `{"id": graph, ...}`
- `[(id, graph), ...]`

### `rank(query, top_k=None, coarse_top_k=None)`

对查询图进行检索排序，返回候选结果列表。

## 特征解释

### `WL` 特征

`WL` 特征用于捕捉图的局部结构模式。它把节点的邻域信息逐轮聚合，形成可比较的结构向量，适合做粗筛。

### 结构兼容性过滤

这一层用于提前剔除明显不可能相似的候选，例如：

- 节点数差距过大
- 边数差距过大
- 变量节点或约束节点数量差异过大

### 标签 `Jaccard`

这一项用于衡量两个图在“标签集合”上的重叠程度。当前主要看：

- 节点类型
- 约束类型
- 域信息
- 常量与参数中的结构性原子

### 自适应融合

最终排序不是单一指标，而是把结构得分、`WL` 相似度和 `Jaccard` 重叠综合起来，形成更稳健的融合分数。

## 第二阶段预留

论文里的 `TED` 和 `Collapse-Match` 更偏向树结构。若后续要继续增强 CP 图的精细比对能力，可以考虑：

- 图编辑距离近似
- 二分图锚点对齐
- 子图折叠匹配
- 约束子结构的局部一致性比较

这些能力可以作为第二阶段加入，不需要改动现有解析器和图构建器。
