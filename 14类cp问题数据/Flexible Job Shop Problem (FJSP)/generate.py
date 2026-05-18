import random
import os
import json  # 新增导入


def generate_fjsp_data(num_jobs, num_machines, avg_flex):
    """
    生成标准 FJSP 数据，返回字典格式。
    """
    jobs = []
    print(f"开始生成 {num_jobs} 个工件...")
    print(f"目标平均柔性度 = {avg_flex}")

    for j in range(num_jobs):
        # 每个作业 2~5 道工序
        num_operations = random.randint(2, 5)
        operations = []

        for op in range(num_operations):
            # 让机器可选数围绕 avg_flex 浮动
            lower = max(1, int(avg_flex - 1))
            upper = min(num_machines, int(avg_flex + 1))
            k = random.randint(lower, upper)

            # 随机选择 k 台机器
            machines = random.sample(range(1, num_machines + 1), k)
            machine_list = []
            for m in machines:
                processing_time = random.randint(5, 20)
                machine_list.append({"machine": m, "time": processing_time})

            operations.append({"machines": machine_list})

        jobs.append({"operations": operations})

    data = {
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "avg_flex": avg_flex,
        "jobs": jobs
    }
    return data


# ===================================
# 批量生成 MK001 ~ MK010
# ===================================

os.makedirs("CP_random_data/data/fjsp/data_fjsp", exist_ok=True)

for n in range(1801, 2001):
    filename = f"generate_MK{n:04d}.json"  # 扩展名改为 .json
    filepath = f"CP_random_data/data/fjsp/data_fjsp/{filename}"

    print(f"\n正在生成实例: {filename}")

    data = generate_fjsp_data(
        num_jobs=40,
        num_machines=20,
        avg_flex=4
    )

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)  # indent=2 使输出可读

print("\n完成! 已生成 MK01~MK10，保存在 CP_random_data/data/fjsp/data_fjsp")