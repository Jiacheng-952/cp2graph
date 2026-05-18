import json
import os
from ortools.sat.python import cp_model
import time

def solve_fjsp(file_path, time_limit=300):
    with open(file_path, 'r') as f:
        data = json.load(f)

    num_jobs = data['num_jobs']
    num_machines = data['num_machines']
    jobs_data = data['jobs']
    # setup_times 预留，可根据需要添加约束
    # setup_times = data['setup_times']

    model = cp_model.CpModel()

    all_machines = range(1, num_machines + 1)
    all_jobs = range(num_jobs)

    # 创建变量
    task_starts = {}
    task_ends = {}
    task_durations = {}
    task_machines = {}

    for j, job in enumerate(jobs_data):
        # 计算该作业所有操作的最大加工时间之和，作为该作业内所有任务的上界
        job_upper_bound = sum(max(d['time'] for d in op['machines']) for op in job['operations'])
        for t, task in enumerate(job['operations']):
            machines = [m['machine'] for m in task['machines']]
            durations = [m['time'] for m in task['machines']]

            duration_var = model.NewIntVar(min(durations), max(durations), f'duration_j{j}_t{t}')
            machine_var = model.NewIntVarFromDomain(
                cp_model.Domain.FromValues(machines), f'machine_j{j}_t{t}')

            start_var = model.NewIntVar(0, job_upper_bound, f'start_j{j}_t{t}')
            end_var = model.NewIntVar(0, job_upper_bound, f'end_j{j}_t{t}')

            # 创建布尔变量控制 duration 与 machine
            for m_id, dur in zip(machines, durations):
                selected = model.NewBoolVar(f"selected_j{j}_t{t}_m{m_id}")
                model.Add(machine_var == m_id).OnlyEnforceIf(selected)
                model.Add(machine_var != m_id).OnlyEnforceIf(selected.Not())
                model.Add(duration_var == dur).OnlyEnforceIf(selected)

            model.Add(end_var == start_var + duration_var)

            task_starts[(j, t)] = start_var
            task_ends[(j, t)] = end_var
            task_durations[(j, t)] = duration_var
            task_machines[(j, t)] = machine_var

    # 同一工作任务顺序约束
    for j, job in enumerate(jobs_data):
        for t in range(len(job['operations']) - 1):
            model.Add(task_starts[(j, t + 1)] >= task_ends[(j, t)])

    # 同一机器不同时处理任务
    for m in all_machines:
        intervals_on_m = []
        for j, job in enumerate(jobs_data):
            for t, task in enumerate(job['operations']):
                # 判断机器 m 是否属于该任务的候选机器
                if m in [mach['machine'] for mach in task['machines']]:
                    # 任务是否在该机器上加工：machine_var == m
                    is_present = model.NewBoolVar(f"is_j{j}_t{t}_on_m{m}")
                    model.Add(task_machines[(j, t)] == m).OnlyEnforceIf(is_present)
                    model.Add(task_machines[(j, t)] != m).OnlyEnforceIf(is_present.Not())
                    # 可选区间：开始、持续时间、结束、存在标志
                    interval = model.NewOptionalIntervalVar(
                        task_starts[(j, t)],
                        task_durations[(j, t)],
                        task_ends[(j, t)],
                        is_present,
                        f"interval_j{j}_t{t}_m{m}"
                    )
                    intervals_on_m.append(interval)
        if intervals_on_m:
            model.AddNoOverlap(intervals_on_m)

    # makespan
    makespan = model.NewIntVar(0, 1000000, "makespan")
    model.AddMaxEquality(makespan, [task_ends[(j, len(job['operations']) - 1)] for j, job in enumerate(jobs_data)])

    # 求解
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit

    start_time = time.time()
    status = solver.Solve(model)
    runtime = time.time() - start_time

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        results = {}
        for j, job in enumerate(jobs_data):
            results[j] = []
            for t, task in enumerate(job['operations']):
                results[j].append({
                    'start': solver.Value(task_starts[(j, t)]),
                    'end': solver.Value(task_ends[(j, t)]),
                    'machine': solver.Value(task_machines[(j, t)]),
                    'duration': solver.Value(task_durations[(j, t)])
                })
        return results, solver.Value(makespan), runtime, solver.StatusName(status)
    else:
        return None, None, runtime, solver.StatusName(status)

def batch_solve_fjsp(data_dir="data", output_dir="results", time_limit=300):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for file_name in os.listdir(data_dir):
        if file_name.endswith(".json"):
            input_path = os.path.join(data_dir, file_name)
            results, makespan, runtime, status = solve_fjsp(input_path, time_limit)
            output_path = os.path.join(output_dir, file_name.replace(".json", "_result.json"))
            if results is not None:
                with open(output_path, 'w') as f:
                    json.dump({
                        'results': results,
                        'makespan': makespan,
                        'runtime': runtime,
                        'status': status
                    }, f, indent=2)
                print(f"Solved {file_name}: makespan={makespan}, time={runtime:.2f}s, status={status}")
            else:
                print(f"Failed to solve {file_name}: status={status}, time={runtime:.2f}s")
                # 也可保存错误信息
                with open(output_path, 'w') as f:
                    json.dump({
                        'error': 'No feasible solution found',
                        'runtime': runtime,
                        'status': status
                    }, f, indent=2)

if __name__ == "__main__":
    batch_solve_fjsp(data_dir="data", output_dir="results", time_limit=300)