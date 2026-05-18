### **数学模型**

#### **参数 (Parameters)**

-   $J$: 作业（Job）的集合, $j \in J$。
-   $M$: 机器（Machine）的集合, $m \in M$。
-   $O_j$: 作业 $j$ 的工序（Operation）集合, $o \in O_j$。
-   $T$: 离散时间点的集合, $t \in T = \{0, 1, ..., T_{max}-1\}$。
-   $mach_{jo}$: 分配给作业 $j$ 的工序 $o$ 的机器。
-   $req_{jo}$: 作业 $j$ 的工序 $o$ 所需的总加工量。
-   $int_{mt}$: 机器 $m$ 在时间点 $t$ 的加工强度。
-   $M_{big}$: 一个足够大的正数（Big-M）。

#### **决策变量 (Decision Variables)**

-   $x_{jot}$: 二元变量。如果作业 $j$ 的工序 $o$ 在时间点 $t$ 被加工，则为1，否则为0。

$$
x_{jot} \in \{0, 1\} \quad \forall j \in J, o \in O_j, t \in T
$$

-   $e_{jo}$: 连续变量，表示作业 $j$ 的工序 $o$ 的结束时间。

$$
e_{jo} \ge 0 \quad \forall j \in J, o \in O_j
$$

-   $C_{max}$: 连续变量，表示最终需要最小化的最大完工时间（Makespan）。

$$
C_{max} \ge 0
$$

#### **目标函数 (Objective Function)**

我们的目标是最小化最大完工时间：

$$
\mathrm{Minimize} \quad C_{max}
$$

#### **约束条件 (Constraints)**

1.  **加工量约束**:
对于每个工序，其在所有被加工的时间点上所累积的机器强度之和，必须大于或等于其所需的总加工量。

$$
\sum_{t \in T} x_{jot} \cdot int_{mach_{jo}, t} \ge req_{jo} \quad \forall j \in J, o \in O_j
$$

2.  **机器能力约束**:
在任意一个时间点，每台机器最多只能加工一个工序。

$$
\sum_{j \in J} \sum_{o \in O_j \mid mach_{jo}=m} x_{jot} \le 1 \quad \forall m \in M, t \in T
$$

3.  **工序结束时间定义**:
一个工序的结束时间必须大于或等于其任何一个加工时间点 `t` 的结束时刻 `t+1`。

$$
e_{jo} \ge (t + 1) \cdot x_{jot} \quad \forall j \in J, o \in O_j, t \in T
$$

4.  **工序先后顺序约束**:
对于同一个作业，后一道工序 ($o+1$) 的任意加工时间点 $t$，必须在前一道工序 ($o$) 完成之后。

$$
e_{j,o} \le t + M_{big} \cdot (1 - x_{j, o+1, t}) \quad \forall j \in J, o \in \{0, ..., |O_j|-2\}, t \in T
$$

5.  **最大完工时间约束**:
最大完工时间必须大于或等于每个作业的最后一个工序的结束时间。

$$
C_{max} \ge e_{j, |O_j|-1} \quad \forall j \in J
$$
