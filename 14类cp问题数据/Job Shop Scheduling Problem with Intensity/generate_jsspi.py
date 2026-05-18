import random
import json
import os
import argparse
from datetime import datetime

DIFFICULTY_CONFIGS = {
    "easy": {
        "jobs_range": (3, 6),
        "machines_range": (2, 4),
        "duration_range": (1, 30),
        "intensity_range": (1, 5),
        "capacity_factor": (2.0, 3.0),
        "description": "小规模问题，低资源约束"
    },
    "medium": {
        "jobs_range": (6, 12),
        "machines_range": (4, 8),
        "duration_range": (5, 80),
        "intensity_range": (1, 8),
        "capacity_factor": (1.5, 2.5),
        "description": "中等规模问题，中等资源约束"
    },
    "hard": {
        "jobs_range": (10, 20),
        "machines_range": (6, 12),
        "duration_range": (10, 100),
        "intensity_range": (2, 10),
        "capacity_factor": (1.2, 2.0),
        "description": "大规模问题，较紧资源约束"
    },
    "very_hard": {
        "jobs_range": (15, 30),
        "machines_range": (8, 15),
        "duration_range": (20, 150),
        "intensity_range": (3, 12),
        "capacity_factor": (1.0, 1.5),
        "description": "超大规模问题，紧资源约束"
    }
}

def calculate_recommended_capacity(num_machines, max_intensity, capacity_factor):
    return max(int(num_machines * max_intensity / capacity_factor), max_intensity + 1)

def generate_jsspi_instance(instance_id, num_jobs, num_machines, min_duration, max_duration,
                            min_intensity, max_intensity, max_intensity_global, 
                            mode="random", seed=None):
    if seed is not None:
        random.seed(seed)
    
    jobs = []
    for j in range(num_jobs):
        machines = list(range(num_machines))
        
        if mode == "random":
            random.shuffle(machines)
        elif mode == "flowshop":
            pass
        elif mode == "reverse_flowshop":
            machines.reverse()
        
        operations = []
        for m in machines:
            duration = random.randint(min_duration, max_duration)
            intensity = random.randint(min_intensity, max_intensity)
            operations.append({
                "machine": m,
                "duration": duration,
                "intensity": intensity
            })
        
        jobs.append({"operations": operations})
    
    instance = {
        "id": instance_id,
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "max_intensity": max_intensity_global,
        "jobs": jobs,
        "metadata": {
            "mode": mode,
            "duration_range": [min_duration, max_duration],
            "intensity_range": [min_intensity, max_intensity],
            "generated_at": datetime.now().isoformat()
        }
    }
    
    return instance

def generate_batch(num_instances=2000, difficulty_distribution=None, output_dir="data"):
    os.makedirs(output_dir, exist_ok=True)
    
    if difficulty_distribution is None:
        difficulty_distribution = {
            "easy": 0.15,
            "medium": 0.45,
            "hard": 0.30,
            "very_hard": 0.10
        }
    
    difficulties = list(difficulty_distribution.keys())
    weights = list(difficulty_distribution.values())
    
    print(f"开始生成 {num_instances} 个 JSSPI 实例...")
    print(f"难度分布: {difficulty_distribution}")
    
    generated_count = 0
    instance_id = 1
    
    while generated_count < num_instances:
        difficulty = random.choices(difficulties, weights=weights, k=1)[0]
        config = DIFFICULTY_CONFIGS[difficulty]
        
        num_jobs = random.randint(*config["jobs_range"])
        num_machines = random.randint(*config["machines_range"])
        min_duration, max_duration = config["duration_range"]
        min_intensity, max_intensity = config["intensity_range"]
        capacity_factor = random.uniform(*config["capacity_factor"])
        
        max_intensity_global = calculate_recommended_capacity(
            num_machines, max_intensity, capacity_factor
        )
        
        instance_id_str = f"jsspi_{instance_id:05d}"
        
        instance = generate_jsspi_instance(
            instance_id=instance_id_str,
            num_jobs=num_jobs,
            num_machines=num_machines,
            min_duration=min_duration,
            max_duration=max_duration,
            min_intensity=min_intensity,
            max_intensity=max_intensity,
            max_intensity_global=max_intensity_global,
            mode="random",
            seed=instance_id
        )
        
        instance["metadata"]["difficulty"] = difficulty
        instance["metadata"]["capacity_factor"] = round(capacity_factor, 2)
        
        filepath = os.path.join(output_dir, f"{instance_id_str}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(instance, f, indent=2, ensure_ascii=False)
        
        generated_count += 1
        instance_id += 1
        
        if generated_count % 500 == 0:
            print(f"已生成 {generated_count}/{num_instances} 个实例...")
    
    print(f"\n完成! 已将 {num_instances} 个实例保存到 {output_dir}/ 目录")
    
    stats_file = os.path.join(output_dir, "generation_stats.json")
    stats = {
        "total_instances": num_instances,
        "difficulty_distribution": difficulty_distribution,
        "difficulty_configs": DIFFICULTY_CONFIGS,
        "generated_at": datetime.now().isoformat()
    }
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def validate_instance(instance):
    num_jobs = instance["num_jobs"]
    num_machines = instance["num_machines"]
    max_intensity = instance["max_intensity"]
    jobs = instance["jobs"]
    
    if len(jobs) != num_jobs:
        return False, f"作业数量不匹配: 声明 {num_jobs}, 实际 {len(jobs)}"
    
    if max_intensity <= 0:
        return False, f"资源容量必须为正数: {max_intensity}"
    
    for job_idx, job in enumerate(jobs):
        operations = job["operations"]
        if len(operations) != num_machines:
            return False, f"作业 {job_idx} 的工序数量不等于机器数"
        
        machines_in_job = set()
        for op in operations:
            machine = op["machine"]
            duration = op["duration"]
            intensity = op["intensity"]
            
            if machine < 0 or machine >= num_machines:
                return False, f"作业 {job_idx} 包含无效机器编号 {machine}"
            
            if machine in machines_in_job:
                return False, f"作业 {job_idx} 中机器 {machine} 重复"
            machines_in_job.add(machine)
            
            if duration <= 0:
                return False, f"作业 {job_idx} 包含非正加工时间 {duration}"
            
            if intensity <= 0:
                return False, f"作业 {job_idx} 包含非正资源强度 {intensity}"
            
            if intensity > max_intensity:
                return False, f"作业 {job_idx} 资源强度 {intensity} 超过全局容量 {max_intensity}"
    
    return True, "验证通过"

def main():
    parser = argparse.ArgumentParser(description="生成 JSSPI (资源受限作业车间调度问题) JSON 格式数据")
    
    parser.add_argument("--batch", action="store_true", help="批量生成模式")
    parser.add_argument("--num_instances", "-n", type=int, default=2000, help="生成的实例数量")
    parser.add_argument("--output", "-o", type=str, default="data", help="输出目录")
    
    parser.add_argument("--jobs", "-j", type=int, default=10, help="作业数量 (单实例模式)")
    parser.add_argument("--machines", "-m", type=int, default=5, help="机器数量 (单实例模式)")
    parser.add_argument("--min_duration", type=int, default=1, help="最小工序时长")
    parser.add_argument("--max_duration", type=int, default=100, help="最大工序时长")
    parser.add_argument("--min_intensity", type=int, default=1, help="最小资源强度")
    parser.add_argument("--max_intensity", type=int, default=10, help="最大资源强度")
    parser.add_argument("--capacity", "-c", type=int, help="全局资源容量")
    parser.add_argument("--mode", type=str, default="random", 
                        choices=["random", "flowshop", "reverse_flowshop"],
                        help="机器顺序模式")
    parser.add_argument("--seed", type=int, help="随机种子")
    parser.add_argument("--validate", action="store_true", help="验证生成的数据")
    
    args = parser.parse_args()
    
    if args.batch:
        generate_batch(num_instances=args.num_instances, output_dir=args.output)
    else:
        if args.capacity is None:
            args.capacity = args.machines * 3
        
        instance = generate_jsspi_instance(
            instance_id="jsspi_single",
            num_jobs=args.jobs,
            num_machines=args.machines,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            min_intensity=args.min_intensity,
            max_intensity=args.max_intensity,
            max_intensity_global=args.capacity,
            mode=args.mode,
            seed=args.seed
        )
        
        if args.validate:
            valid, msg = validate_instance(instance)
            print(f"验证结果: {msg}")
        
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(instance, f, indent=2, ensure_ascii=False)
            print(f"实例已保存至 {args.output}")
        else:
            print(json.dumps(instance, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
