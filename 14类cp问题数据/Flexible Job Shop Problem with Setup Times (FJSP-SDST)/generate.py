import random
import os
import json


def generate_fjsp_sdst(num_jobs, num_machines, avg_flex):
    """
    生成 FJSP-SDST 实例，返回字典格式。
    """
    data = {
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "avg_flex": avg_flex,
        "jobs": [],
        "setup_times": []
    }

    jobs_list = []
    tasks = []          # 记录每个任务对应的 (job, op) 索引，用于后续映射准备时间

    task_index = 0

    for j in range(num_jobs):
        num_operations = random.randint(2, 5)
        operations = []

        for o in range(num_operations):
            # 可选机器数围绕 avg_flex 浮动
            lower = max(1, avg_flex - 1)
            upper = min(num_machines, avg_flex + 1)
            k = random.randint(lower, upper)

            machines = random.sample(range(1, num_machines + 1), k)
            machine_list = []
            for m in machines:
                p = random.randint(5, 30)
                machine_list.append({"machine": m, "time": p})

            operations.append({"machines": machine_list})
            tasks.append((j, o))          # 记录该任务
            task_index += 1

        jobs_list.append({"operations": operations})

    data["jobs"] = jobs_list

    T = len(tasks)   # 总工序数

    # 生成准备时间矩阵：对每个机器，生成 T x T 矩阵
    for m in range(num_machines):
        matrix = []
        for i in range(T):
            row = []
            for j in range(T):
                if i == j:
                    row.append(0)
                else:
                    row.append(random.randint(1, 20))
            matrix.append(row)
        data["setup_times"].append(matrix)

    return data


if __name__ == "__main__":
    # ========= 手动控制参数 =========
    NUM_JOBS = 30
    NUM_MACHINES = 25
    AVG_FLEX = 8
    START_INDEX = 1801
    END_INDEX = 2000
    # ==================================

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data_fjsp-sdst")
    os.makedirs(data_dir, exist_ok=True)

    print("开始批量生成 FJSP-SDST 实例（JSON 格式）")
    print(f"保存路径: {data_dir}")
    print(f"实例编号: {START_INDEX} ~ {END_INDEX}")
    print(f"平均柔性度: {AVG_FLEX}")
    print("-" * 40)

    for n in range(START_INDEX, END_INDEX + 1):
        filename = f"instance_{n:04d}.json"
        filepath = os.path.join(data_dir, filename)

        print(f"正在生成: {filename}")

        data = generate_fjsp_sdst(NUM_JOBS, NUM_MACHINES, AVG_FLEX)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    print("-" * 40)
    print("批量生成完成 ✅")