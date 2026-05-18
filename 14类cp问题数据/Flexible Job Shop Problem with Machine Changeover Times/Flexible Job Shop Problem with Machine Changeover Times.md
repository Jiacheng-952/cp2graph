
## 3. 数学模型
### 参数说明 (Parameters):
- $J$: 工件集合, $j \in J$.
- $O_j$: 工件 $j$ 的工序集合, $o \in O_j$.
- $M$: 机器集合, $m \in M$.
- $M_{jo} \subseteq M$: 能够加工工件 $j$ 的工序 $o$ 的机器集合。
- $p_{jom}$: 工件 $j$ 的工序 $o$ 在机器 $m$ 上的加工时间。
- $c_{m_1 m_2}$: 从机器 $m_1$ 转换到机器 $m_2$ 的转换时间。
- $L$: 一个足够大的正数 (Big-M)。

### 决策变量 (Decision Variables):
- $start_{jo}$: 连续变量，表示工件 $j$ 的工序 $o$ 的开始时间。
- $end_{jo}$: 连续变量，表示工件 $j$ 的工序 $o$ 的结束时间。
- $y_{jom}$: 二元变量，如果工件 $j$ 的工序 $o$ 分配给机器 $m$，则为1，否则为0。
- $z_{j_1 o_1 j_2 o_2 m}$: 二元变量，如果工序 $(j_1, o_1)$ 和 $(j_2, o_2)$ 都在机器 $m$ 上加工，且 $(j_1, o_1)$ 在 $(j_2, o_2)$ 之前，则为1，否则为0。
- $C_{max}$: 连续变量，表示最大完工时间 (Makespan)。

### 目标函数 (Objective Function):
目标是最小化最大完工时间。

$$
\mathrm{Minimize} \quad C_{max}
$$

### 约束条件 (Constraints):

1.  **最大完工时间约束 (Makespan Constraint):**
最大完工时间必须不小于任何工件的最后一个工序的完成时间。

$$
C_{max} \ge end_{j, |O_j|-1} \quad \forall j \in J
$$

2.  **工序分配约束 (Assignment Constraint):**
每个工序必须且只能分配给一台可用的机器。

$$
\sum_{m \in M_{jo}} y_{jom} = 1 \quad \forall j \in J, o \in O_j
$$

3.  **工时计算约束 (Processing Time Constraint):**
工序的完成时间等于其开始时间加上在指定机器上的加工时间。

$$
end_{jo} = start_{jo} + \sum_{m \in M_{jo}} y_{jom} \cdot p_{jom} \quad \forall j \in J, o \in O_j
$$

4.  **工序顺序约束 (Precedence Constraint):**
对于同一个工件，后一道工序的开始时间必须晚于前一道工序的完成时间，并考虑可能的机器转换时间。

$$
start_{j, o+1} \ge end_{jo} + \sum_{m_1 \in M_{j,o}} \sum_{m_2 \in M_{j,o+1}} y_{j,o,m_1} \cdot y_{j,o+1,m_2} \cdot c_{m_1 m_2} \quad \forall j \in J, o \in \{0, ..., |O_j|-2\}
$$

注意: 上述约束中的 $y_{j,o,m_1} \cdot y_{j,o+1,m_2}$ 是非线性的，在实际模型中需要进行线性化处理。

5.  **机器互斥约束 (Disjunctive Constraint):**
对于任意两个在同一台机器 $m$ 上加工的工序 $(j_1, o_1)$ 和 $(j_2, o_2)$，它们在时间上不能重叠。

$$
start_{j_1 o_1} \ge end_{j_2 o_2} - L \cdot (1 - z_{j_2 o_2 j_1 o_1 m}) \quad \forall m \in M, \forall (j_1, o_1), (j_2, o_2) \mathrm{\ s.t.\ } j_1 \neq j_2 \lor o_1 \neq o_2
$$

$$
start_{j_2 o_2} \ge end_{j_1 o_1} - L \cdot z_{j_2 o_2 j_1 o_1 m} \quad \forall m \in M, \forall (j_1, o_1), (j_2, o_2) \mathrm{\ s.t.\ } j_1 \neq j_2 \lor o_1 \neq o_2
$$

注意: 上述约束只有在工序 $(j_1, o_1)$ 和 $(j_2, o_2)$ 都分配给机器 $m$ 时才生效，即 $y_{j_1,o_1,m}=1$ 和 $y_{j_2,o_2,m}=1$。在代码实现中，这通过将 $y$ 变量整合到 Big-M 项中来处理。
