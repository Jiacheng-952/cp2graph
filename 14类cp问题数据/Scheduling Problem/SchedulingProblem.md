# 员工排班与技能匹配问题数学模型

## 参数说明

- $E$: 所有员工的集合。
- $R$: 所有餐厅的集合。
- $S$: 所有班次的集合。
- $K$: 所有技能（岗位）的集合。
- $d_{rsk}$: 在餐厅 $r \in R$ 的班次 $s \in S$ 对技能 $k \in K$ 的员工需求数量。
- $h_{ek}$: 一个二进制参数，如果员工 $e \in E$ 拥有技能 $k \in K$，则 $h_{ek} = 1$；否则为 $0$。
- $a_{es}$: 一个二进制参数，如果员工 $e \in E$ 可以在班次 $s \in S$ 工作，则 $a_{es} = 1$；否则为 $0$。
- $c_{ek}$: 将员工 $e \in E$ 分配到需要技能 $k \in K$ 的岗位所产生的偏好成本。
- $C_{unful}$: 未能满足一个岗位需求所产生的罚金成本。

## 决策变量

- $x_{ersk}$: 一个二进制变量。如果决定将员工 $e \in E$ 分配到餐厅 $r \in R$ 的班次 $s \in S$ 去执行需要技能 $k \in K$ 的工作，则 $x_{ersk} = 1$；否则为 $0$。
- $u_{rsk}$: 一个非负整数变量，表示在餐厅 $r \in R$ 的班次 $s \in S$ 对技能 $k \in K$ 未被满足的员工需求数量。

## 目标函数

优化目标是最小化总成本，该成本由两部分组成：所有岗位未被满足产生的罚金成本，以及所有员工分配的偏好成本之和。

$$
\mathrm{Minimize} \quad \sum_{r \in R} \sum_{s \in S} \sum_{k \in K} C_{unful} \cdot u_{rsk} + \sum_{e \in E} \sum_{r \in R} \sum_{s \in S} \sum_{k \in K} c_{ek} \cdot x_{ersk}
$$

## 约束条件

1.  **需求满足约束 (Demand Satisfaction)**:
对于每个餐厅的每个班次的每项技能需求，分配的员工总数加上未满足的需求数，必须等于总需求数。

$$
\sum_{e \in E} x_{ersk} + u_{rsk} = d_{rsk} \quad \forall r \in R, \forall s \in S, \forall k \in K
$$

2.  **员工技能约束 (Skill Requirement)**:
员工只能被分配到他们拥有相应技能的岗位。

$$
x_{ersk} \le h_{ek} \quad \forall e \in E, \forall r \in R, \forall s \in S, \forall k \in K
$$

3.  **员工班次可用性约束 (Shift Availability)**:
员工不能在他们不可用的班次被分配工作。对于任意员工和班次，他在所有餐厅和所有技能岗位的分配总数不能超过他的可用性（0或1）。

$$
\sum_{r \in R} \sum_{k \in K} x_{ersk} \le a_{es} \quad \forall e \in E, \forall s \in S
$$

4.  **单一任务约束 (Single Assignment per Employee)**:
每位员工在所有餐厅、所有班次、所有技能岗位中，最多只能被分配一次。

$$
\sum_{r \in R} \sum_{s \in S} \sum_{k \in K} x_{ersk} \le 1 \quad \forall e \in E
$$
