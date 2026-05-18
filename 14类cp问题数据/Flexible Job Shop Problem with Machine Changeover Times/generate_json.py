import random
import json
import os


def generate_fjspc_json(num_jobs, num_machines, avg_flex):
    data = {
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "jobs": [],
        "setup_times": []
    }

    print(f"开始生成 {num_jobs} 个工件...")

    for j in range(num_jobs):
        num_ops = random.randint(4, 7)

        job = {
            "job_id": j + 1,
            "operations": []
        }

        for o in range(num_ops):
            k = random.randint(1, int(min(num_machines, avg_flex * 2)))

            selected_machines = random.sample(range(1, num_machines + 1), k)

            modes = []
            for m_id in selected_machines:
                modes.append({
                    "machine": m_id,
                    "time": random.randint(1, 10)
                })

            operation = {
                "op_id": o + 1,
                "modes": modes
            }

            job["operations"].append(operation)

        data["jobs"].append(job)

    print(f"正在生成 {num_machines}x{num_machines} 的 SDST 矩阵...")

    for i in range(num_machines):
        row = []
        for j in range(num_machines):
            if i == j:
                row.append(0)
            else:
                row.append(random.randint(1, 5))
        data["setup_times"].append(row)

    return data


# ---------- 主程序 ----------
if __name__ == "__main__":
    output_dir = "data_json"
    os.makedirs(output_dir, exist_ok=True)

    for n in range(1, 2000):
        filename = f"generate_MK{n:03d}.json"
        filepath = os.path.join(output_dir, filename)

        print(f"正在生成第 {n} 个实例: {filename}")

        data = generate_fjspc_json(
            num_jobs=30,
            num_machines=20,
            avg_flex=3.5
        )

        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

    print(f"\n🎉 完成！已生成 JSON 数据，保存在 {output_dir}")