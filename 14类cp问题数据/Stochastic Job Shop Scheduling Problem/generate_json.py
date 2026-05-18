import numpy as np
import os
import json


def generate_single_instance_json(num_jobs, num_machines, num_scenarios,
                                  min_duration, max_duration):
    """
    生成单个 SJSSP 实例（JSON格式）
    """

    instance = {
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "num_scenarios": num_scenarios,
        "jobs": []
    }

    # 每个工件的机器顺序
    job_operations_list = [
        np.random.permutation(num_machines).tolist()
        for _ in range(num_jobs)
    ]

    for j in range(num_jobs):

        job_data = {
            "job_id": j,
            "operations": job_operations_list[j],
            "scenarios": []
        }

        for s in range(num_scenarios):

            durations = np.random.randint(
                min_duration,
                max_duration + 1,
                size=num_machines
            ).tolist()

            job_data["scenarios"].append({
                "scenario_id": s,
                "durations": durations
            })

        instance["jobs"].append(job_data)

    return instance


def generate_multiple_instances_json(num_instances,
                                     num_jobs,
                                     num_machines,
                                     num_scenarios,
                                     min_duration,
                                     max_duration,
                                     output_dir="data"):

    os.makedirs(output_dir, exist_ok=True)

    for i in range(1, num_instances + 1):

        instance = generate_single_instance_json(
            num_jobs,
            num_machines,
            num_scenarios,
            min_duration,
            max_duration
        )

        file_path = os.path.join(output_dir, f"data_{i}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(instance, f, indent=4)

    print(f"{num_instances} 个JSON实例已生成，保存在 '{output_dir}' 文件夹中。")


# 测试生成
if __name__ == "__main__":

    generate_multiple_instances_json(
        num_instances=500,
        num_jobs=6,
        num_machines=5,
        num_scenarios=8,
        min_duration=3,
        max_duration=15,
        output_dir="data_large_json"
    )

    # data_small 中的数据有3种场景
    # data_medium 中的数据有5种场景
    # data_large 中的数据有8种场景