# -*- coding: utf-8 -*-
"""
批量求解 JSON FJSP 实例（每个作业多工序，多机器可选）
使用 OR-Tools CP-SAT 求解器
"""

import os
import time
import json
from ortools.sat.python import cp_model

# ---------- 1. 解析 JSON 文件 ----------
def parse_json_file(filepath):
    """
    读取 JSON 文件，返回 jobs_operations, num_machines
    格式示例：
    {
      "num_jobs": 10,
      "num_machines": 6,
      "jobs": [
        {"operations":[{"machines":[{"machine":3,"time":7}, ...]}, ...]},
        ...
      ]
    }
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    num_jobs = data['num_jobs']
    num_machines = data['num_machines']
    jobs_operations = []

    for job in data['jobs']:
        ops = []
        for op in job['operations']:
            m_dict = {m['machine']-1: m['time'] for m in op['machines']}  # 转 0-based
            ops.append(m_dict)
        jobs_operations.append(ops)

    return jobs_operations, num_machines


# ---------- 2. OR-Tools 求解 ----------
def solve_fjsp_ortools(jobs_operations, num_machines, time_limit=600):
    num_jobs = len(jobs_operations)
    model = cp_model.CpModel()

    horizon = sum(sum(op.values()) for job in jobs_operations for op in job) * 2

    start_vars, end_vars, assign_vars, interval_vars = {}, {}, {}, {}
    all_ops = [(j, o) for j in range(num_jobs) for o in range(len(jobs_operations[j]))]

    for j, o in all_ops:
        start_vars[(j, o)] = model.NewIntVar(0, horizon, f'start_{j}_{o}')
        end_vars[(j, o)] = model.NewIntVar(0, horizon, f'end_{j}_{o}')
        assign_vars[(j, o)] = {}
        interval_vars[(j, o)] = {}

        for m, pt in jobs_operations[j][o].items():
            assign_vars[(j, o)][m] = model.NewBoolVar(f'assign_{j}_{o}_{m}')
            interval_vars[(j, o)][m] = model.NewOptionalIntervalVar(
                start_vars[(j, o)], pt, end_vars[(j, o)], assign_vars[(j, o)][m],
                f'interval_{j}_{o}_{m}'
            )

    makespan = model.NewIntVar(0, horizon, 'makespan')

    # 约束
    for j, o in all_ops:
        model.Add(sum(assign_vars[(j, o)][m] for m in jobs_operations[j][o].keys()) == 1)
        proc_expr = sum(assign_vars[(j, o)][m] * jobs_operations[j][o][m] for m in jobs_operations[j][o].keys())
        model.Add(end_vars[(j, o)] == start_vars[(j, o)] + proc_expr)

    for j in range(num_jobs):
        for o in range(len(jobs_operations[j])-1):
            model.Add(start_vars[(j, o+1)] >= end_vars[(j, o)])

    for m in range(num_machines):
        intervals_on_machine = [interval_vars[(j, o)][m] for j, o in all_ops if m in interval_vars[(j, o)]]
        if intervals_on_machine:
            model.AddNoOverlap(intervals_on_machine)

    for j in range(num_jobs):
        last_op = len(jobs_operations[j])-1
        model.Add(makespan >= end_vars[(j, last_op)])

    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    start_time = time.time()
    status = solver.Solve(model)
    runtime = time.time() - start_time

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        makespan_val = solver.ObjectiveValue()
        results = []
        for j, o in all_ops:
            start = solver.Value(start_vars[(j, o)])
            end = solver.Value(end_vars[(j, o)])
            assigned_m, proc = -1, 0
            for m, pt in jobs_operations[j][o].items():
                if solver.Value(assign_vars[(j, o)][m]) == 1:
                    assigned_m, proc = m+1, pt  # 输出 1-based
                    break
            results.append({"Job": j+1, "Operation": o+1, "Machine": assigned_m,
                            "Start": start, "Processing": proc, "End": end})
        return results, makespan_val, runtime, status
    else:
        return None, None, runtime, status


# ---------- 3. 写入结果 ----------
def write_solution_to_txt(results, makespan, filepath, status):
    with open(filepath, 'w', encoding='utf-8') as f:
        if status == cp_model.OPTIMAL:
            f.write(f"makespan: {makespan} (最优解)\n")
        elif status == cp_model.FEASIBLE:
            f.write(f"makespan: {makespan} (可行解)\n")
        else:
            f.write("makespan: 无解\n")
        if results is None:
            f.write("无可行解\n")
            return
        f.write("机器\t工件\t工序\t开始时间\t加工时间\t结束时间\n")
        sorted_res = sorted(results, key=lambda x: (x['Machine'], x['Start']))
        for r in sorted_res:
            f.write(f"{r['Machine']}\t{r['Job']}\t{r['Operation']}\t"
                    f"{r['Start']}\t{r['Processing']}\t{r['End']}\n")


# ---------- 4. 单文件处理 ----------
def process_single_file(input_path, output_dir, time_limit=600):
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.basename(input_path).replace('.json', '')
    output_path = os.path.join(output_dir, f"{base}_solution.txt")
    try:
        jobs_ops, num_machines = parse_json_file(input_path)
    except Exception as e:
        print(f"解析失败 {input_path}: {e}")
        return False, base, None, None, None

    results, makespan, runtime, status = solve_fjsp_ortools(jobs_ops, num_machines, time_limit)
    write_solution_to_txt(results, makespan, output_path, status)
    return results is not None, base, makespan, runtime, status


# ---------- 5. 批量求解 ----------
def batch_solve(input_dir="json_data", output_dir="results_json", time_limit=600):
    print("开始批量求解 JSON FJSP 实例")
    summary = []
    files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    for f in files:
        input_file = os.path.join(input_dir, f)
        success, file_num, makespan, runtime, status = process_single_file(input_file, output_dir, time_limit)
        summary.append({"文件编号": file_num, "状态": "成功" if success else "失败",
                        "Makespan": makespan if makespan else "无解",
                        "求解时间(秒)": f"{runtime:.2f}" if runtime else "N/A",
                        "状态码": status})
        print(f"{file_num}: Makespan={makespan}, 时间={runtime:.2f}s, 状态={status}")

    summary_file = os.path.join(output_dir, "batch_summary.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("批量求解 JSON FJSP 问题汇总报告\n")
        f.write("="*50 + "\n")
        f.write(f"处理文件数量: {len(files)}\n\n")
        f.write(f"{'文件编号':<15}{'状态':<10}{'Makespan':<15}{'求解时间(秒)':<15}\n")
        f.write("-"*55 + "\n")
        for item in summary:
            f.write(f"{item['文件编号']:<15}{item['状态']:<10}{str(item['Makespan']):<15}{item['求解时间(秒)']:<15}\n")
    print(f"汇总报告已保存至: {summary_file}")


# ---------- 6. 主入口 ----------
if __name__ == "__main__":
    INPUT_DIR = "data"    # 放你的 JSON 文件夹
    OUTPUT_DIR = "results"
    TIME_LIMIT = 600           # 每个实例最大求解时间（秒）

    total_start = time.time()
    batch_solve(INPUT_DIR, OUTPUT_DIR, TIME_LIMIT)
    total_end = time.time()
    print(f"总运行时间: {total_end - total_start:.2f} 秒 ({(total_end - total_start)/60:.2f} 分钟)")