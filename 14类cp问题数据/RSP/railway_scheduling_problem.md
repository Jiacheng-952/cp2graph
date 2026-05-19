
# 数学模型 
## 模型公式化
### 集合与参数
- $I$: 列车集合
- $R$: 资源集合（包括站点 $R_S$ 和轨道 $R_T$）
- $R_i$: 列车 $i \in I$ 需要访问的有序资源列表
- $dur_r$: 列车通过资源 $r \in R$ 所需的时间
- $cap_r$: 资源 $r \in R$ 的容量
- $r_m$: 正在进行维修的轨道资源, $r_m \in R_T$
- $T_{start}$: 维修开始时间
- $T_{end}$: 维修结束时间

### 决策变量
- $t_{i,r}$: 列车 $i$ 访问（开始占用）资源 $r$ 的时间, $\forall i \in I, r \in R_i$
- $t^F_i$: 列车 $i$ 的完成时间, $\forall i \in I$
- $y_{i,j,r}$: 二元变量，如果列车 $i$ 在资源 $r$ 上先于列车 $j$ 经过，则为1
- $x_{i,j,r}$: 二元变量，如果列车 $i$ 和 $j$ 在资源 $r$ 上相遇（同时占用），则为1
- $m_{i,r_m}$: 二元变量, $\forall i \in I$ 使得 $r_m \in R_i$。如果列车 $i$ 在维修开始前通过轨道 $r_m$，则为1；如果在维修结束后通过，则为0。

### 目标函数
目标是最小化所有列车的总延误时间。

$$
\min \sum_{i \in I} (t^F_i - \sum_{r \in R_i} dur_r)
$$

### 约束条件
1.  **列车内路径约束 (Intra-train path constraints)**:

$$
t_{i,r'} \ge t_{i,r} + dur_r \quad \forall i \in I, (r, r') \mathrm{\ are\ consecutive\ resources\ in\ } R_i
$$

$$
t^F_i \ge t_{i,r_{last}} + dur_{r_{last}} \quad \forall i \in I, r_{last} \mathrm{\ is\ the\ last\ resource\ in\ } R_i
$$

2.  **资源容量约束 (Resource capacity constraints)**:
对于共享资源 $r$ 的任意一对列车 $(i, j)$，它们之间必须满足以下关系之一：$i$ 先于 $j$，$j$ 先于 $i$，或者它们相遇。

$$
y_{i,j,r} + y_{j,i,r} + x_{i,j,r} = 1 \quad \forall r \in R, \forall i,j \in I: r \in R_i \cap R_j, i < j
$$

同时，在任何时间点，占用资源 $r$ 的列车数量不能超过其容量 $cap_r$。这通过对任意 $cap_r+1$ 列车的组合，限制其两两相遇的变量 $x$ 的总和来实现。

$$
\sum_{i,j \in S, i<j} x_{i,j,r} \le \binom{|S|}{2} - 1 \quad \forall r \in R, \forall S \subseteq \{i \in I | r \in R_i\}, |S| = cap_r + 1
$$

3.  **计划性维修约束 (Scheduled Maintenance Constraint)**:
对于需要使用维修轨道 $r_m$ 的每一列车 $i$，它必须在维修开始前完全通过，或者在维修结束后才能进入。

$$
t_{i,r_m} + dur_{r_m} \le T_{start} + M \cdot (1 - m_{i,r_m}) \quad \forall i \in I \mathrm{\ s.t.\ } r_m \in R_i
$$

$$
t_{i,r_m} \ge T_{end} - M \cdot m_{i,r_m} \quad \forall i \in I \mathrm{\ s.t.\ } r_m \in R_i
$$

其中 $M$ 是一个足够大的数。
