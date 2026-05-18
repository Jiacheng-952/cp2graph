import random
import os
import json

def generate_data(num_tasks, num_resources, num_types):
    """
    生成符合问题描述的随机数据。
    """
    # 资源容量
    capacities = [random.randint(2, 5) for _ in range(num_resources)]
    
    # 任务属性
    tasks = []
    for i in range(num_tasks):
        task = {
            "id": i,
            "type": random.randint(0, num_types - 1),
            "resource": random.randint(0, num_resources - 1),
            "duration": random.randint(10, 30),
            "successors": []
        }
        tasks.append(task)
        
    # 生成随机的后续任务关系（保证 DAG）
    for i in range(num_tasks):
        for j in range(i + 1, num_tasks):
            if random.random() < 0.1:
                tasks[i]["successors"].append(j)
                
    return tasks, capacities


def save_to_json(filename, tasks, capacities):
    """
    保存为 JSON 格式
    """
    data = {
        "num_tasks": len(tasks),
        "num_resources": len(capacities),
        "capacities": capacities,
        "tasks": tasks
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    # --- 配置参数 ---
    START_ID = 1
    END_ID = 2000
    
    BASE_DIR = "data_json/"
    FILE_PREFIX = "generated_instance_"
    
    N_TASKS = 20      
    N_RESOURCES = 3   
    N_TYPES = 2       

    # 创建目录
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
        print(f"创建目录: {BASE_DIR}")

    print(f"开始生成数据: 从 ID {START_ID} 到 {END_ID} ...")

    for i in range(START_ID, END_ID + 1):
        filename = f"{FILE_PREFIX}{i:02d}.json"
        full_path = os.path.join(BASE_DIR, filename)
        
        tasks_data, caps_data = generate_data(N_TASKS, N_RESOURCES, N_TYPES)
        
        save_to_json(full_path, tasks_data, caps_data)
        print(f"  [OK] 已生成: {filename}")

    print("\n所有文件生成完毕。")