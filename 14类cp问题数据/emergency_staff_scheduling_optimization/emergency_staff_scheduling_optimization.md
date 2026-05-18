
# 数学模型 
## 模型公式化

### 集合与索引
- $s \in \mathrm{Shifts}$：班次的集合。
- $w \in \mathrm{Workers}$：自有护士的集合。
- $w \in \mathrm{SeniorNurses} \subseteq \mathrm{Workers}$：高级护士的集合。
- $\mathrm{Availability} = \{(w,s): w \in \mathrm{Workers} \text{ 且可在班次 } s \text{ 工作}\}$：护士的可工作时间集合。

### 参数
- $\mathrm{shiftRequirements}(s) \in \mathbb{N}$：班次 $s$ 所需的护士总人数。
- $\mathrm{pay}(w) \in \mathbb{R}^{+}$：护士 $w$ 的日薪（本模型中未直接用于目标函数，但作为数据保留）。
- $\mathrm{relTol}$：用于多目标优化，表示次要目标在优化时，主要目标可以偏离其最优值的最大相对容差。

### 决策变量
- $x(w,s) \in \{0,1\}$：如果护士 $w$ 被分配到班次 $s$，则为1，否则为0。此变量仅在 $(w,s) \in \mathrm{Availability}$ 时有意义。
- $Slack(s) \geq 0$：为满足班次 $s$ 的需求，需要额外聘请的临时护士数量。

### 辅助变量
- $totSlack$：两周内需要聘请的临时护士总数。
- $\mathrm{totShifts}(w)$：护士 $w$ 在两周内工作的总班次数。
- $\mathrm{minShift}$：所有护士中工作班次总数的最小值。
- $\mathrm{maxShift}$：所有护士中工作班次总数的最大值。

### 目标函数
1.  **主要目标 (最小化临时工)**：

$$
\mathrm{Minimize} \quad \mathrm{totSlack} = \sum_{s \in \mathrm{Shifts}} Slack(s)
$$

2.  **次要目标 (最大化公平性)**：

$$
\mathrm{Minimize} \quad (\mathrm{maxShift} - \mathrm{minShift})
$$

### 约束条件
1.  **班次人数需求**：每个班次的总护士数（自有护士 + 临时护士）必须满足当日需求。

$$
\sum_{w \in \mathrm{Workers}} x(w,s) + Slack(s) = \mathrm{shiftRequirements}(s) \quad \forall s \in \mathrm{Shifts}
$$

2.  **高级护士在场** (新增约束)：每个班次必须至少有一名高级护士。

$$
\sum_{w \in \mathrm{SeniorNurses}, (w,s) \in \mathrm{Availability}} x(w,s) \geq 1 \quad \forall s \in \mathrm{Shifts}
$$

3.  **临时工总数**：计算临时护士的总和。

$$
\sum_{s \in \mathrm{Shifts}} Slack(s) = \mathrm{totSlack}
$$

4.  **护士工作班次**：计算每位护士的总工作班次。

$$
\sum_{s \in \mathrm{Shifts}, (w,s) \in \mathrm{Availability}} x(w,s) = \mathrm{totShifts}(w) \quad \forall w \in \mathrm{Workers}
$$

5.  **工作量差距**：定义最大和最小工作班次。

$$
\mathrm{maxShift} = \max_{w \in \mathrm{Workers}} \{\mathrm{totShifts}(w)\}
$$

$$
\mathrm{minShift} = \min_{w \in \mathrm{Workers}} \{\mathrm{totShifts}(w)\}
$$

6.  **多目标约束**：在优化次要目标时，主要目标的值不能超过其最优解的一定容差范围。

$$
\mathrm{totSlack} \leq (1 + \mathrm{relTol}) \times \mathrm{Opt(totSlack)}
$$
