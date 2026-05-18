import json
import os
from ortools.sat.python import cp_model

# ------------------------------
# 读取 JSON 文件
# ------------------------------
def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ------------------------------
# OR-Tools 求解函数
# ------------------------------
def solve_fjsp_ortools(data, time_limit=300):
    num_jobs = data['num_jobs']
    num_machines = data['num_machines']
    jobs = data['jobs']

    model = cp_model.CpModel()
    all_tasks = {}
    machine_to_intervals = [[] for _ in range(num_machines)]

    # 1. 定义变量
    for job in jobs:
        j_id = job['job_id'] - 1
        for op in job['operations']:
            o_id = op['op_id'] - 1
            op_vars = []
            for mode in op['modes']:
                m_id = mode['machine'] - 1
                dur = mode['time']
                start_var = model.NewIntVar(0, 100000, f'start_j{j_id}_o{o_id}_m{m_id}')
                end_var = model.NewIntVar(0, 100000, f'end_j{j_id}_o{o_id}_m{m_id}')
                pres_var = model.NewBoolVar(f'pres_j{j_id}_o{o_id}_m{m_id}')
                interval_var = model.NewOptionalIntervalVar(start_var, dur, end_var, pres_var,
                                                            f'int_j{j_id}_o{o_id}_m{m_id}')
                op_vars.append((interval_var, pres_var, start_var, end_var, m_id, dur))
                machine_to_intervals[m_id].append(interval_var)
            all_tasks[(j_id, o_id)] = op_vars

    # 2. 每道工序只能选择一个模式
    for (j_id, o_id), op_vars in all_tasks.items():
        pres_vars = [x[1] for x in op_vars]
        model.AddExactlyOne(pres_vars)

    # 3. 机器无重叠约束
    for m_id in range(num_machines):
        if machine_to_intervals[m_id]:
            model.AddNoOverlap(machine_to_intervals[m_id])

    # 4. 前后工序约束
    for job in jobs:
        j_id = job['job_id'] - 1
        ops = job['operations']
        for i in range(len(ops) - 1):
            cur_op = all_tasks[(j_id, i)]
            next_op = all_tasks[(j_id, i + 1)]
            for cur_mode in cur_op:
                for next_mode in next_op:
                    model.Add(next_mode[2] >= cur_mode[3]).OnlyEnforceIf([cur_mode[1], next_mode[1]])

    # 5. 目标函数：最小化 makespan
    last_ends = []
    for job in jobs:
        j_id = job['job_id'] - 1
        last_op_id = len(job['operations']) - 1
        last_op = all_tasks[(j_id, last_op_id)]
        last_ends += [x[3] for x in last_op]
    makespan = model.NewIntVar(0, 1000000, 'makespan')
    model.AddMaxEquality(makespan, last_ends)
    model.Minimize(makespan)

    # 6. 求解
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status_code = solver.Solve(model)

    results = []
    if status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for (j_id, o_id), op_vars in all_tasks.items():
            for interval_var, pres_var, start_var, end_var, m_id, dur in op_vars:
                if solver.BooleanValue(pres_var):
                    results.append({
                        "Job": j_id + 1,
                        "Operation": o_id + 1,
                        "Machine": m_id + 1,
                        "Start": solver.Value(start_var),
                        "Processing": dur,
                        "End": solver.Value(end_var)
                    })
        return results, solver.Value(makespan), solver.WallTime(), solver.StatusName(status_code)
    else:
        return None, None, None, solver.StatusName(status_code)

# ------------------------------
# 写结果到文件
# ------------------------------
def write_solution(results, makespan, filename, status):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8-sig') as f:
        f.write(f"makespan: {makespan}\n")
        f.write(f"status: {status}\n")
        if results:
            f.write("Machine\tJob\tOperation\tStart\tProcessing\tEnd\n")
            for r in sorted(results, key=lambda x: (x['Machine'], x['Start'])):
                f.write(f"{r['Machine']}\t{r['Job']}\t{r['Operation']}\t{r['Start']}\t{r['Processing']}\t{r['End']}\n")

# ------------------------------
# 批量处理文件夹
# ------------------------------
def batch_solve(data_dir='data', result_dir='results', time_limit=300):
    os.makedirs(result_dir, exist_ok=True)
    summary_file = os.path.join(result_dir, 'summary.txt')
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    summary_lines = ["File\tStatus\tMakespan\tTime(s)"]

    for file_name in json_files:
        file_path = os.path.join(data_dir, file_name)
        output_path = os.path.join(result_dir, file_name.replace('.json', '_solution.txt'))
        print(f"Processing {file_name} ...")
        try:
            data = read_json_file(file_path)
            results, makespan, runtime, status = solve_fjsp_ortools(data, time_limit)
            write_solution(results, makespan, output_path, status)
            time_str = f"{runtime:.2f}" if runtime is not None else "N/A"
            summary_lines.append(f"{file_name}\t{status}\t{makespan}\t{time_str}")
            print(f"Done {file_name}: status={status}, makespan={makespan}, time={time_str}")
        except Exception as e:
            summary_lines.append(f"{file_name}\tError\tN/A\tN/A")
            print(f"Error processing {file_name}: {e}")

    # 写汇总
    with open(summary_file, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(summary_lines))
    print(f"\nBatch processing complete! Summary saved to {summary_file}")

# ------------------------------
# 主程序
# ------------------------------
if __name__ == "__main__":
    batch_solve(data_dir='data', result_dir='results', time_limit=300)