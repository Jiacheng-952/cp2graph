# JSSP (Job Shop Scheduling Problem) 项目说明

## 目录结构

*   `generate_jssp.py`: JSSP 数据生成器脚本。
*   `solver.py`: 基于 OR-Tools 的 CP-SAT 求解器。
*   `data/`: 存放生成的实例数据 (`.jssc` 文件)。
*   `results/`: 存放求解结果 (`.txt` 文件) 和汇总报告 (`summary.txt`)。

## 数据格式说明 (.jssc)

文件第一行包含两个整数：
```
<作业数 num_jobs> <机器数 num_machines>
```

随后的每一行代表一个作业 (Job)，包含一系列工序 (Task)。每个工序由两个数字组成：
```
<机器编号 machine_id> <加工时长 duration>
```

例如 `3 2` 表示该工序在机器 3 上进行，耗时 2 个单位时间。

**示例:**
```
2 2
0 10 1 20
1 15 0 5
```
*   2个作业，2台机器。
*   作业0: 先在机器0加工10单位，再在机器1加工20单位。
*   作业1: 先在机器1加工15单位，再在机器0加工5单位。

## 脚本使用方法

### 1. 数据生成 (generate_jssp.py)

该脚本支持生成自定义规模和结构的 JSSP 实例。

**常用命令:**

*   **查看帮助:**
    ```bash
    python generate_jssp.py --help
    ```

*   **生成单个自定义实例:**
    ```bash
    python generate_jssp.py --jobs 10 --machines 5 --output data/custom_instance.jssc
    ```

*   **生成 Flow Shop (流水车间) 模式:**
    所有作业都按照相同的机器顺序 (0 -> 1 -> ... -> m) 进行加工。
    ```bash
    python generate_jssp.py --jobs 10 --machines 5 --mode flowshop --output data/flowshop.jssc
    ```

*   **批量生成 (默认 10 个实例):**
    生成 `generate_instance_001.jssc` 到 `010.jssc`。
    ```bash
    python generate_jssp.py --batch
    ```

**参数说明:**
*   `--jobs, -j`: 作业数量。
*   `--machines, -m`: 机器数量。
*   `--min_duration / --max_duration`: 工序时长的随机范围。
*   `--mode`: 机器顺序模式 (`random` 为标准 Job Shop, `flowshop` 为流水车间)。
*   `--seed`: 随机种子，用于复现结果。

### 2. 求解器 (solver.py)

读取 `data/` 目录下的所有 `.jssc` 文件进行求解，并将结果输出到 `results/`。

**运行:**
```bash
python solver.py
```

*   求解器使用 OR-Tools 的 CP-SAT 模型。
*   输出包含每个实例的求解状态 (Optimal/Feasible)、最大完工时间 (Makespan) 和求解时间。
*   详细的调度方案 (甘特图数据) 会保存在 `results/` 下的对应文件中。
