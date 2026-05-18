# -*- coding: utf-8 -*-
"""
批量求解 JSON 格式的 FRCPSP 实例
使用 OR-Tools CP-SAT 求解器
"""

import os
import json
from ortools.sat.python import cp_model

def solve_frcpsp_instance(data):
    """单个 JSON 实例求解"""
    num_tasks = data['num_tasks']
    num_resources = data['num_resources']
    capacities = data['capacities']
    tasks_data = data['tasks']

    model = cp_model.CpModel()

    # --- 1. 决策变量 ---
    x = {}
    s = {}
    e = {}
    all_modes = {}

    horizon = sum(max(m['duration'] for m in task['modes']) for task in tasks_data) * 2

    for task in tasks_data:
        task_id = task['id'] - 1
        modes = task['modes']
        all_modes[task_id] = modes
        x[task_id] = []
        for m_idx, mode in enumerate(modes):
            var = model.NewBoolVar(f"x_{task_id}_{m_idx}")
            x[task_id].append(var)
        s[task_id] = model.NewIntVar(0, horizon, f"s_{task_id}")
        e[task_id] = model.NewIntVar(0, horizon, f"e_{task_id}")
        # 选择一个模式
        model.Add(sum(x[task_id]) == 1)
        # 结束时间
        duration_expr = sum(x[task_id][m_idx]*mode['duration'] for m_idx, mode in enumerate(modes))
        model.Add(e[task_id] == s[task_id] + duration_expr)

    # --- 2. 前置依赖约束 ---
    for task in tasks_data:
        task_id = task['id'] - 1
        for succ in task.get('successors', []):
            succ_id = succ - 1
            model.Add(s[succ_id] >= e[task_id])

    # --- 3. 资源容量约束 ---
    for r in range(num_resources):
        intervals = []
        demands = []
        for task_id, modes in all_modes.items():
            for m_idx, mode in enumerate(modes):
                if mode['resource'] == r:
                    interval = model.NewOptionalIntervalVar(
                        s[task_id],
                        mode['duration'],
                        e[task_id],
                        x[task_id][m_idx],
                        f"interval_{task_id}_{m_idx}_r{r}"
                    )
                    intervals.append(interval)
                    demands.append(mode['weight'])
        if intervals:
            model.AddCumulative(intervals, demands, capacities[r])

    # --- 4. 目标函数 ---
    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [e[task_id] for task_id in range(num_tasks)])
    model.Minimize(makespan)

    # --- 5. 求解 ---
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # --- 6. 输出结果 ---
    result = {}
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        result['makespan'] = solver.Value(makespan)
        result['schedule'] = []
        for task_id, modes in all_modes.items():
            for m_idx, mode in enumerate(modes):
                if solver.Value(x[task_id][m_idx]):
                    result['schedule'].append({
                        'task': task_id+1,
                        'mode': m_idx,
                        'resource': mode['resource'],
                        'start': solver.Value(s[task_id]),
                        'end': solver.Value(e[task_id]),
                        'duration': mode['duration']
                    })
    else:
        result['makespan'] = None
        result['schedule'] = []
    return result

def batch_solve_folder(folder_path, output_path=None):
    """批量求解文件夹下所有 JSON 文件"""
    files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    summary = []

    for f in files:
        file_path = os.path.join(folder_path, f)
        with open(file_path, 'r', encoding='utf-8') as fin:
            data = json.load(fin)
        print(f"求解实例 {f} ...")
        result = solve_frcpsp_instance(data)
        print(f"  -> Makespan: {result['makespan']}")
        summary.append({'file': f, 'makespan': result['makespan'], 'schedule': result['schedule']})
        # 可选：保存每个结果到单独 JSON 文件
        if output_path:
            out_file = os.path.join(output_path, f.replace('.json', '_solution.json'))
            with open(out_file, 'w', encoding='utf-8') as fout:
                json.dump(result, fout, ensure_ascii=False, indent=4)

    return summary

if __name__ == "__main__":
    input_folder = "data"  # 你的 JSON 文件夹路径
    output_folder = "results"   # 可选：保存结果
    os.makedirs(output_folder, exist_ok=True)
    results = batch_solve_folder(input_folder, output_folder)
    print("批量求解完成！")