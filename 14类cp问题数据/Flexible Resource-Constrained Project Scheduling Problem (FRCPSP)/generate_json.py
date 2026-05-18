import random
import os
import json


def generate_data(num_tasks, num_resources):
    """
    生成 FRCPSP 随机数据（JSON结构）
    """
    capacities = [random.randint(2, 8) for _ in range(num_resources)]
    
    tasks = []

    for i in range(num_tasks):
        task = {
            "id": i + 1,
            "modes": [],
            "successors": []
        }

        has_mode = False

        for r in range(num_resources):
            if random.random() < 0.6:
                duration = random.randint(1, 20)
                weight = random.randint(1, capacities[r])

                task["modes"].append({
                    "resource": r,
                    "duration": duration,
                    "weight": weight
                })
                has_mode = True

        # 兜底（保证至少一个mode）
        if not has_mode:
            r = random.randint(0, num_resources - 1)
            task["modes"].append({
                "resource": r,
                "duration": random.randint(1, 20),
                "weight": random.randint(1, capacities[r])
            })

        tasks.append(task)

    # DAG precedence
    for i in range(num_tasks):
        for j in range(i + 1, num_tasks):
            if random.random() < 0.15:
                tasks[i]["successors"].append(tasks[j]["id"])

    return tasks, capacities


def save_to_json(filename, tasks, capacities):
    data = {
        "num_tasks": len(tasks),
        "num_resources": len(capacities),
        "capacities": capacities,
        "tasks": tasks
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":

    START_ID = 1
    END_ID = 2000

    BASE_DIR = "data_json/"
    FILE_PREFIX = "data_"

    N_TASKS = 20
    N_RESOURCES = 3

    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)

    print(f"开始生成 JSON 数据: {START_ID} - {END_ID}")

    for i in range(START_ID, END_ID + 1):
        filename = f"{FILE_PREFIX}{i:02d}.json"
        full_path = os.path.join(BASE_DIR, filename)

        tasks_data, caps_data = generate_data(N_TASKS, N_RESOURCES)

        save_to_json(full_path, tasks_data, caps_data)

        print(f"[OK] {filename}")

    print("全部 JSON 生成完成")