# 图相似度模块全貌

这个模块建立在现有 `cp2graph` 图构建能力之上，用来比较两个 CP 图是否相似，也可以扩展成图库检索。

## 项目整体逻辑

1. 先把 FlatZinc / MiniZinc 编译后的 IR 解析成 CP 模型。
2. 再把 CP 模型转换成“变量节点 - 约束节点”的二分图。
3. 在图层上做相似度计算、结构过滤、候选排序。
4. 需要时再接入 GNN/GCN 编码器，做更强的向量表示和下游任务。

换句话说，当前项目不是只做“建图”，也不是只做“检索”，而是把这两层连起来。

## 当前支持的两种用法

### 1. 两个图直接比较

这是你现在最常用的场景。

```python
from cp2graph.api import parse_and_build_graph
from cp2graph.similarity import score_graph_pair

g1 = parse_and_build_graph("a.fzn")
g2 = parse_and_build_graph("b.fzn")

result = score_graph_pair(g1, g2)
```

它会直接返回两个图的相似度分数，包括：

- `structure_score`
- `wl_similarity`
- `jaccard_similarity`
- `fusion_score`
- `passed_filter`

### 2. 图库检索

当你手头有很多 CP 模型时，可以把每个模型都预先构造成图，放入图库，然后对一个 query 图做 Top-k 检索。

```python
from cp2graph.api import parse_and_build_graph
from cp2graph.similarity import GraphSimilarityIndex

library = {
    "m01": parse_and_build_graph("tests/models/m01_arith.fzn"),
    "m03": parse_and_build_graph("tests/models/m03_all_diff.fzn"),
}
index = GraphSimilarityIndex(library)
results = index.rank(parse_and_build_graph("tests/models/m04_element.fzn"), top_k=5)
```

## 第一版流程

第一版的相似度模块采用的是“先粗筛、再融合排序”的思路：

1. 先做结构兼容性过滤，排除规模差距过大的图。
2. 再计算 `WL` 相似度，抓住局部结构。
3. 再计算标签 `Jaccard`，衡量图中结构原子的重叠。
4. 最后把这些指标融合成一个最终分数。

这套流程既适用于两图比较，也适用于图库检索。

## CSE 的借鉴方式

论文里的 CSE 是表达式树上的“相同子表达式消除”。  
在 CP 图里可以类比成：

- 重复约束子结构折叠
- 重复邻域模式归并
- 对高频子图做规范化表示

当前项目里已经有一部分类似能力：

- `normalize_model` 会按语义哈希去重重复约束

后续如果要更接近论文，可以继续补：

- 重复子图折叠
- 局部结构缓存
- 更精细的子图规范化

## 新增模块

`cp2graph.similarity` 提供：

- `WL` 特征提取
- 结构兼容性过滤
- 标签 `Jaccard` 重叠
- 自适应融合排序
- 两图比较接口
- 图库检索接口

## 为什么没有直接照搬 TED / Collapse-Match

论文的方法主要面向树结构。  
当前项目的核心对象是 CP 二分图，所以第一版先保留图原生的方法，避免把树算法硬塞进图结构里。

后续如果要增强精细匹配，可以再加：

- 图编辑距离近似
- 锚点对齐
- 子图折叠匹配

## 你现在应该怎么理解这个项目

可以把它看成三层：

1. **解析层**：把 CP 模型变成图
2. **比较层**：判断两个图是否相似
3. **检索层**：在图库里找最像的图

你现在最直接用的是第 2 层。  
第 3 层是第 2 层的批量版。
