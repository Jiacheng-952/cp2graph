# JSSPI (Resource-Constrained JSSP) 项目说明

## 目录结构

*   `generate_jsspi.py`: JSSPI 数据生成器脚本。
*   `solver.py`: 基于 OR-Tools 的 CP-SAT 求解器。
*   `data/`: 存放生成的实例数据 (`.jsspi` 文件)。
*   `results/`: 存放求解结果 (`.txt` 文件) 和汇总报告 (`summary.txt`)。

## 问题描述

JSSPI 是标准 JSSP 的扩展，增加了一个**全局累积资源约束 (Cumulative Resource Constraint)**。
*   每个工序除了需要占用特定的机器外，在加工过程中还会消耗一定的**资源强度 (Intensity)**。
*   在任何时刻，所有正在进行的工序消耗的资源强度总和，不能超过**全局容量限制 (Capacity)**。

## 数据格式说明 (.jsspi)

文件第一行包含三个整数：
```
<作业数 num_jobs> <机器数 num_machines> <全局容量 capacity>
```

随后的每一行代表一个作业，包含一系列工序。每个工序由三个数字组成：
```
<机器编号 machine_id> <加工时长 duration> <资源强度 intensity>
```

**示例:**
```
2 2 10
0 10 5 1 20 6
...
```
*   全局容量限制为 10。
*   作业0的第一个工序: 机器0，时长10，消耗强度5。
*   作业0的第二个工序: 机器1，时长20，消耗强度6。
*   如果这两个工序试图同时运行（虽然在同一个作业中不可能，但考虑不同作业间的情况），总强度 5+6=11 > 10，因此它们不能并行，必须错开时间。

## 脚本使用方法

### 1. 数据生成 (generate_jsspi.py)

支持自定义资源约束的强度。

**常用命令:**

*   **查看帮助:**
    ```bash
    python generate_jsspi.py --help
    ```

*   **生成单个自定义实例:**
    ```bash
    python generate_jsspi.py --jobs 10 --machines 5 --output data/custom.jsspi
    ```

*   **生成高约束实例 (Capacity 较小):**
    设置较小的全局容量，迫使更多工序串行，增加求解难度。
    ```bash
    # 每个任务消耗 1-10，总容量仅为 10 (意味着几乎只能串行)
    python generate_jsspi.py --jobs 10 --machines 5 --max_intensity_task 10 --capacity 10 --output data/tight.jsspi
    ```

*   **批量生成:**
    ```bash
    python generate_jsspi.py --batch
    ```

**参数说明:**
*   `--jobs, -j` / `--machines, -m`: 规模参数。
*   `--min_intensity / --max_intensity_task`: 单个工序消耗资源的随机范围。
*   `--capacity, -c`: **关键参数**。全局资源总容量。值越小，约束越紧。
*   `--mode`: 机器顺序模式。

### 2. 求解器 (solver.py)

读取 `data/` 目录下的 `.jsspi` 文件进行求解。

**运行:**
```bash
python solver.py
```

*   模型中添加了 `AddCumulative` 约束来处理资源限制。
*   结果输出同 JSSP，但在详细结果中增加了 Intensity 信息。
