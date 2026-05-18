# Flexible Resource-Constrained Project Scheduling Problem - 数学模型

本文档提供了灵活性资源约束项目调度问题（FRCPSP）的数学规划模型。

---

### 1. 参数与集合 (Parameters & Sets)

#### 集合 (Sets)
- $I$: 所有任务（Jobs）的集合, $i \in I$。
- $R$: 所有可用执行模式（Modes/Resources）的集合, $r \in R$。
- $K$: 所有资源种类（Resource Types）的集合, $k \in K$。
- $P_j$: 任务 $j$ 的所有紧前任务（Predecessors）的集合, $i \in P_j$ 表示任务 $i$ 必须在任务 $j$ 开始前完成。
- $NP$: 集合中包含了所有没有直接或间接前置依赖关系的任务对 $(i, j)$，其中 $i < j$。

#### 数据参数 (Data Parameters)
- $d_{ir}$: 任务 $i$ 在模式 $r$ 下执行所需的处理时长（Duration）。
- $u_{irk}$: 任务 $i$ 在模式 $r$ 下执行时，对资源种类 $k$ 的单位时间消耗量（Usage/Consumption）。
- $C_k$: 资源种类 $k$ 的最大可用容量（Capacity）。
- $M$: 一个足够大的正数（Big-M），用于线性化逻辑约束。

---

### 2. 决策变量 (Decision Variables)

- $x_{ir}$: 二元变量。如果任务 $i$ 选择模式 $r$ 执行，则 $x_{ir} = 1$，否则为 0。

$$
x_{ir} \in \{0, 1\}, \quad \forall i \in I, r \in R
$$

- $s_i$: 连续变量。表示任务 $i$ 的开始时间。

$$
s_i \ge 0, \quad \forall i \in I
$$

- $e_i$: 连续变量。表示任务 $i$ 的结束时间。

$$
e_i \ge 0, \quad \forall i \in I
$$

- $b_{ij}$: 二元变量。对于没有前后置关系的任务对 $(i, j) \in NP$，此变量用于决定它们的执行顺序。如果 $i$ 在 $j$ 之前完成，$b_{ij}=0$；如果 $j$ 在 $i$ 之前完成，$b_{ij}=1$。

$$
b_{ij} \in \{0, 1\}, \quad \forall (i, j) \in NP
$$

- $Z_{max}$: 连续变量。表示整个项目的总工期（Makespan）。

$$
Z_{max} \ge 0
$$

---

### 3. 目标函数 (Objective Function)

优化目标是最小化项目的总工期 $Z_{max}$。

$$
\mathrm{Minimize} \quad Z_{max}
$$

---

### 4. 约束条件 (Constraints)

1.  **任务分配约束 (Assignment Constraint):**
每个任务必须且只能选择一个执行模式。

$$
\sum_{r \in R} x_{ir} = 1, \quad \forall i \in I
$$

2.  **结束时间约束 (End Time Constraint):**
任务 $i$ 的结束时间由其开始时间和在所选模式下的处理时长决定。

$$
e_i = s_i + \sum_{r \in R} x_{ir} \cdot d_{ir}, \quad \forall i \in I
$$

3.  **前置依赖约束 (Precedence Constraint):**
任务 $j$ 必须在其所有紧前任务 $i \in P_j$ 完成后才能开始。

$$
s_j \ge e_i, \quad \forall j \in I, \forall i \in P_j
$$

4.  **总工期约束 (Makespan Constraint):**
总工期必须大于或等于所有任务的结束时间。

$$
Z_{max} \ge e_i, \quad \forall i \in I
$$

5.  **资源容量约束 (Resource Capacity Constraint):**
对于任意一对没有前后置关系的任务 $(i, j) \in NP$，以及任意一对模式选择 $(r_1, r_2) \in R \times R$，如果它们对任何一种资源 $k \in K$ 的总需求超过了该资源的容量，那么这两个任务在时间上不能重叠。

这个逻辑通过以下一组“大M”约束来实现。对于所有满足 $u_{ir_1k} + u_{jr_2k} > C_k$ 的组合 $(i, j, k, r_1, r_2)$: 

$$
s_j \ge e_i - M \cdot b_{ij} - M \cdot (2 - x_{ir_1} - x_{jr_2})
$$

$$
s_i \ge e_j - M \cdot (1 - b_{ij}) - M \cdot (2 - x_{ir_1} - x_{jr_2})
$$

  *   **约束含义解释:** 当任务 $i$ 选择模式 $r_1$ ($x_{ir_1}=1$) 并且任务 $j$ 选择模式 $r_2$ ($x_{jr_2}=1$) 时，约束右侧的 $M \cdot (2 - x_{ir_1} - x_{jr_2})$ 项变为0，此时约束被激活。激活的约束 `s_j >= e_i - M * b_ij` 和 `s_i >= e_j - M * (1 - b_ij)` 共同确保了 $s_j \ge e_i$ 或 $s_i \ge e_j$ 之一必须成立，从而强制为这两个任务排序，避免了时间上的重叠。如果 $x_{ir_1}$ 或 $x_{jr_2}$ 中任何一个为0，则该约束的右侧变为一个非常大的负数，约束自动满足，不产生任何限制。
