import sys
import os
import glob
import json
import time
import re
from ortools.sat.python import cp_model

def parse_jsspi_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    num_jobs = data["num_jobs"]
    num_machines = data["num_machines"]
    max_intensity = data["max_intensity"]
    jobs_data = []
    
    for job in data["jobs"]:
        operations = []
        for op in job["operations"]:
            operations.append((op["machine"], op["duration"], op["intensity"]))
        jobs_data.append(operations)
    
    return num_jobs, num_machines, max_intensity, jobs_data, data.get("id", os.path.basename(file_path))

def solve_jsspi(file_path, time_limit=60):
    print(f"正在求解: {file_path}")
    num_jobs, num_machines, max_intensity, jobs_data, instance_id = parse_jsspi_json(file_path)
    
    model = cp_model.CpModel()

    horizon = sum(task[1] for job in jobs_data for task in job)

    all_intervals = []
    all_intensities = []

    machine_intervals = {m: [] for m in range(num_machines)}
    job_ends = []
    
    start_vars = {}
    end_vars = {}

    for job_id, job in enumerate(jobs_data):
        previous_end = None
        for task_id, (machine, duration, intensity) in enumerate(job):
            start_var = model.NewIntVar(0, horizon, f'start_{job_id}_{task_id}')
            end_var = model.NewIntVar(0, horizon, f'end_{job_id}_{task_id}')
            interval_var = model.NewIntervalVar(start_var, duration, end_var, f'interval_{job_id}_{task_id}')
            
            start_vars[(job_id, task_id)] = start_var
            end_vars[(job_id, task_id)] = end_var
            
            machine_intervals[machine].append(interval_var)
            
            all_intervals.append(interval_var)
            all_intensities.append(intensity)
            
            if previous_end is not None:
                model.Add(start_var >= previous_end)
            
            previous_end = end_var
        
        job_ends.append(previous_end)

    for m in range(num_machines):
        model.AddNoOverlap(machine_intervals[m])

    model.AddCumulative(all_intervals, all_intensities, max_intensity)

    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, job_ends)
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    
    start_time = time.time()
    status = solver.Solve(model)
    end_time = time.time()
    solve_time = end_time - start_time

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"求解状态: {solver.StatusName(status)}")
        print(f"Makespan: {solver.ObjectiveValue()}")
        
        results = []
        for job_id, job in enumerate(jobs_data):
            for task_id, (machine, duration, intensity) in enumerate(job):
                start_val = solver.Value(start_vars[(job_id, task_id)])
                end_val = solver.Value(end_vars[(job_id, task_id)])
                results.append({
                    "job": job_id,
                    "task": task_id,
                    "machine": machine,
                    "intensity": intensity,
                    "start": start_val,
                    "duration": duration,
                    "end": end_val
                })
        
        return {
            "instance_id": instance_id,
            "status": solver.StatusName(status),
            "makespan": int(solver.ObjectiveValue()),
            "time": solve_time,
            "results": results
        }
    else:
        print("未找到解")
        return {
            "instance_id": instance_id,
            "status": solver.StatusName(status),
            "makespan": None,
            "time": solve_time,
            "results": None
        }

def write_solution(instance_name, solution_data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{instance_name}_solution.json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(solution_data, f, indent=2, ensure_ascii=False)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    results_dir = os.path.join(base_dir, "results")
    
    data_files = glob.glob(os.path.join(data_dir, "*.json"))
    data_files = [f for f in data_files if not f.endswith("generation_stats.json")]
    
    # 只保留编号 >= 31 的文件
    filtered_files = []
    for f in data_files:
        filename = os.path.splitext(os.path.basename(f))[0]
        match = re.search(r'(\d+)', filename)
        if match:
            num = int(match.group(1))
            if num >= 31:
                filtered_files.append(f)
    filtered_files.sort()
    
    if not filtered_files:
        print(f"在 {data_dir} 未找到编号 >= 31 的数据文件")
        return

    summary = []
    
    for file_path in filtered_files:
        instance_name = os.path.splitext(os.path.basename(file_path))[0]
        print(f"\nProcessing {instance_name}...")
        
        solution = solve_jsspi(file_path)
        
        write_solution(instance_name, solution, results_dir)
        
        summary.append({
            "instance": instance_name,
            "status": solution["status"],
            "makespan": solution["makespan"],
            "time": round(solution["time"], 4)
        })
    
    summary_file = os.path.join(results_dir, "summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n完成! 共处理 {len(filtered_files)} 个实例")
    print(f"结果保存在 {results_dir}/ 目录")

if __name__ == "__main__":
    main()