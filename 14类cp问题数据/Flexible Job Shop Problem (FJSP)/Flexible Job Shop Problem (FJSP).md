

# 柔性作业车间调度问题 (FJSP) - 数学模型

## 实际业务背景

假设一个制造工厂，需要加工一组不同的工件（作业）。每个工件都需要经过一系列特定的加工步骤（工序），例如切割、钻孔、打磨等。工厂拥有多台功能不同的机器，其中某些机器是多功能的，即同一个工序可以在不同的机器上完成，但花费的时间可能不同。调度的目标是合理地为每个工序分配机器，并确定每个工序的开始加工时间，使得所有工件都完成加工的总时间（即最大完工时间）最短。

---

## 参数说明

- $I$: 作业（Jobs）的集合, $i \in I$。
- $O_i$: 作业 $i$ 的工序（Operations）集合, $o \in O_i$。
- $K$: 机器（Machines）的集合, $k \in K$。
- $K_{io}$: 可用于加工工序 $(i, o)$ 的机器集合, $K_{io} \subseteq K$。
- $p_{iok}$: 工序 $(i, o)$ 在机器 $k$ 上的加工时间（Processing Time）。
- $M$: 一个足够大的正数（Big-M）。

## 决策变量

- $x_{iok}$: 二元变量。如果工序 $(i, o)$ 被分配到机器 $k$ 上加工，则为1，否则为0。

$$
x_{iok} \in \{0, 1\}, \quad \forall i \in I, o \in O_i, k \in K_{io}
$$

- $s_{io}$: 连续变量。表示工序 $(i, o)$ 的开始时间。

$$
s_{io} \ge 0, \quad \forall i \in I, o \in O_i
$$

- $y_{i_1o_1i_2o_2k}$: 二元变量。如果工序 $(i_1, o_1)$ 在工序 $(i_2, o_2)$ 之前在机器 $k$ 上执行，则为1，否则为0。用于处理同一台机器上的工序顺序。

$$
y_{i_1o_1i_2o_2k} \in \{0, 1\}, \quad \forall k \in K, \mathrm{\ and\ pairs\ of\ ops\ } (i_1, o_1), (i_2, o_2) \mathrm{\ that\ can\ use\ machine\ } k
$$

- $C_{max}$: 连续变量。表示最大完工时间（Makespan），即所有作业完成的时间。

$$
C_{max} \ge 0
$$

## 目标函数

目标是最小化最大完工时间。

$$
\mathrm{Minimize} \quad C_{max}
$$

## 约束条件

1.  **机器分配约束 (Assignment Constraint)**:
每个工序必须且只能被分配到一台可用的机器上。

$$
\sum_{k \in K_{io}} x_{iok} = 1, \quad \forall i \in I, o \in O_i
$$

2.  **工序顺序约束 (Precedence Constraint)**:
对于同一个作业，前一个工序必须在后一个工序开始之前完成。这里 $p_{io}$ 是工序 $(i,o)$ 的实际加工时间，其值取决于分配的机器。

$$
s_{io} + \sum_{k \in K_{io}} p_{iok} \cdot x_{iok} \le s_{i, o+1}, \quad \forall i \in I, o \in O_i, o < |O_i|
$$

3.  **不重叠约束 (Disjunctive Constraint)**:
对于任意两个不同的工序 $(i_1, o_1)$ 和 $(i_2, o_2)$，如果它们都被分配到同一台机器 $k$ 上，则它们不能在时间上重叠。

$$
s_{i_1o_1} + \sum_{k' \in K_{i_1o_1}} p_{i_1o_1k'} \cdot x_{i_1o_1k'} \le s_{i_2o_2} + M \cdot (1 - y_{i_1o_1i_2o_2k}) + M \cdot (2 - x_{i_1o_1k} - x_{i_2o_2k})
$$

$$
s_{i_2o_2} + \sum_{k' \in K_{i_2o_2}} p_{i_2o_2k'} \cdot x_{i_2o_2k'} \le s_{i_1o_1} + M \cdot y_{i_1o_1i_2o_2k} + M \cdot (2 - x_{i_1o_1k} - x_{i_2o_2k})
$$

以上两个约束适用于所有机器 $k \in K$ 以及所有可以在机器 $k$ 上执行的工序对 $((i_1, o_1), (i_2, o_2))$。

4.  **最大完工时间约束 (Makespan Constraint)**:
最大完工时间必须大于或等于任何一个作业的最后一个工序的完成时间。

$$
C_{max} \ge s_{io_{last}} + \sum_{k \in K_{io_{last}}} p_{io_{last}k} \cdot x_{io_{last}k}, \quad \forall i \in I
$$

其中 $o_{last}$ 是作业 $i$ 的最后一个工序。

