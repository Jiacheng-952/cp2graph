# -*- coding: utf-8 -*-
"""
批量求解开放车间调度问题 (OSSP) JSON 数据
使用 OR-Tools CP-SAT
"""

import json
import os
from datetime import datetime
import itertools
from ortools.sat.python import cp_model
import pandas as pd

def solve_ossp_instance(data_file, time_limit=300):
    """求解单个 OSSP 实例"""
    if not os.path.exists(data_file):
        print(f"数据文件不存在: {data_file}")
        return None

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    num_jobs = data["num_jobs"]
    num_machines = data["num_machines"]
    processing_times = data["processing_times"]

    jobs = range(num_jobs)
    machines = range(num_machines)

    model = cp_model.CpModel()
    horizon = sum(sum(pt for pt in row) for row in processing_times)

    # 决策变量
    start = {}
    end = {}
    intervals = {}
    for j in jobs:
        for m in machines:
            s = model.NewIntVar(0, horizon, f'start_{j}_{m}')
            e = model.NewIntVar(0, horizon, f'end_{j}_{m}')
            interval = model.NewIntervalVar(s, processing_times[j][m], e, f'interval_{j}_{m}')
            start[(j, m)] = s
            end[(j, m)] = e
            intervals[(j, m)] = interval

    # 工件约束：同一工件的工序不能重叠
    for j in jobs:
        for m1, m2 in itertools.combinations(machines, 2):
            model.AddNoOverlap([intervals[(j, m1)], intervals[(j, m2)]])

    # 机器约束：同一机器上工件不能重叠
    for m in machines:
        model.AddNoOverlap([intervals[(j, m)] for j in jobs])

    # Cmax 完工时间
    makespan = model.NewIntVar(0, horizon, "Cmax")
    for j in jobs:
        for m in machines:
            model.Add(end[(j, m)] <= makespan)
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    # 处理 start_times 为字符串 key，避免 JSON 报错
    start_times_serializable = None
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        start_times_serializable = {
            f"job_{j}_machine_{m}": solver.Value(start[(j, m)])
            for j in jobs
            for m in machines
        }

    result = {
        "data_file": os.path.basename(data_file),
        "status": solver.StatusName(status),
        "solve_time": solver.WallTime(),
        "makespan": solver.Value(makespan) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
        "start_times": start_times_serializable
    }

    return result


def batch_solve(data_dir="data", time_limit=300, output_dir="results"):
    """批量求解 data 目录下的 JSON 文件"""
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
    if not files:
        print(f"{data_dir} 目录下未找到 JSON 文件")
        return

    all_results = []

    for i, f in enumerate(sorted(files)):
        path = os.path.join(data_dir, f)
        print(f"\n[{i+1}/{len(files)}] 求解: {f}")
        res = solve_ossp_instance(path, time_limit=time_limit)
        if res:
            # 保存单实例 JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(f)[0]
            result_file = os.path.join(output_dir, f"{base_name}_result_{timestamp}.json")
            with open(result_file, 'w', encoding='utf-8') as rf:
                json.dump(res, rf, indent=2, ensure_ascii=False)
            print(f"  已保存结果: {result_file}")
            all_results.append(res)

    # 汇总 CSV
    if all_results:
        summary_file = os.path.join(output_dir, "batch_summary.csv")
        summary_rows = []
        for r in all_results:
            summary_rows.append({
                "file": r["data_file"],
                "status": r["status"],
                "makespan": r["makespan"],
                "solve_time": r["solve_time"]
            })
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_csv(summary_file, index=False)
        print(f"\n批量求解完成，汇总文件已保存: {summary_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='批量求解 OSSP JSON 文件')
    parser.add_argument('--data-dir', type=str, default='data', help='JSON 数据文件目录')
    parser.add_argument('--time-limit', type=int, default=300, help='每个实例求解时间限制 (秒)')
    parser.add_argument('--output-dir', type=str, default='results', help='结果输出目录')

    args = parser.parse_args()
    batch_solve(data_dir=args.data_dir, time_limit=args.time_limit, output_dir=args.output_dir)