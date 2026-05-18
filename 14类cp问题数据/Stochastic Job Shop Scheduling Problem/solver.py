from ortools.sat.python import cp_model
import itertools
import os
import re
import json


def natural_sort_key(filename):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]


# =========================
# 读取 JSON（适配你当前结构）
# =========================
def load_instance_from_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    num_jobs = data["num_jobs"]
    num_machines = data["num_machines"]
    num_scenarios = data["num_scenarios"]

    jobs_data = data["jobs"]

    # job_operations[j]
    job_operations = []

    # durations[s][j][m]
    durations = [
        [[0 for _ in range(num_machines)] for _ in range(num_jobs)]
        for _ in range(num_scenarios)
    ]

    for job in jobs_data:
        j = job["job_id"]
        job_operations.append(job["operations"])

        for scen in job["scenarios"]:
            s = scen["scenario_id"]
            durations[s][j] = scen["durations"]

    return num_jobs, num_machines, num_scenarios, job_operations, durations


# =========================
# 求解单个实例（OR-Tools）
# =========================
def solve_instance(file_path):

    num_jobs, num_machines, num_scenarios, job_operations, durations = load_instance_from_json(file_path)

    jobs = range(num_jobs)
    machines = range(num_machines)
    scenarios = range(num_scenarios)

    model = cp_model.CpModel()

    # Big-M
    M = sum(
        max(durations[s][j][m] for s in scenarios)
        for j in jobs for m in machines
    )

    horizon = M

    # start time
    start = {}
    for s in scenarios:
        for j in jobs:
            for m in machines:
                start[s, j, m] = model.NewIntVar(0, horizon, f"start_{s}_{j}_{m}")

    # 排序变量
    z = {}
    for i in jobs:
        for j in jobs:
            if i != j:
                for m in machines:
                    z[i, j, m] = model.NewBoolVar(f"z_{i}_{j}_{m}")

    # makespan
    Cmax = model.NewIntVar(0, horizon, "Cmax")

    # ---------- 约束 ----------
    for s in scenarios:

        # 工艺顺序
        for j in jobs:
            for k in range(num_machines - 1):
                m1 = job_operations[j][k]
                m2 = job_operations[j][k + 1]

                model.Add(
                    start[s, j, m1] + durations[s][j][m1]
                    <= start[s, j, m2]
                )

        # 机器冲突
        for m in machines:
            for i, j in itertools.combinations(jobs, 2):

                model.Add(
                    start[s, i, m] + durations[s][i][m]
                    <= start[s, j, m] + M * (1 - z[i, j, m])
                )

                model.Add(
                    start[s, j, m] + durations[s][j][m]
                    <= start[s, i, m] + M * z[i, j, m]
                )

        # makespan
        for j in jobs:
            last_machine = job_operations[j][-1]

            model.Add(
                Cmax >= start[s, j, last_machine] + durations[s][j][last_machine]
            )

    # 排序一致性
    for m in machines:
        for i, j in itertools.combinations(jobs, 2):
            model.Add(z[i, j, m] + z[j, i, m] == 1)

    # ---------- 目标 ----------
    model.Minimize(Cmax)

    # ---------- 求解 ----------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    # ---------- 输出 ----------
    result_text = ""
    result_dict = {}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        result_dict["status"] = "OPTIMAL"
        result_dict["robust_makespan"] = solver.Value(Cmax)

        result_text += f"Robust Makespan: {solver.Value(Cmax):.2f}\n"
        result_text += "Machine Sequences:\n"

        for m in machines:
            remaining = list(jobs)
            sequence = []

            while remaining:
                found = False
                for j1 in remaining:
                    is_first = True
                    for j2 in remaining:
                        if j1 != j2 and solver.Value(z[j2, j1, m]) == 1:
                            is_first = False
                            break
                    if is_first:
                        sequence.append(j1)
                        remaining.remove(j1)
                        found = True
                        break

                if not found:
                    sequence.append(remaining[0])
                    remaining.remove(remaining[0])

            result_text += f"Machine {m}: " + " -> ".join(map(str, sequence)) + "\n"

    else:
        result_dict["status"] = "INFEASIBLE"
        result_text = "Infeasible\n"

    return result_dict, result_text


# =========================
# 批量求解
# =========================
def solve_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    instances_dir = os.path.join(current_dir, "data")
    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    files = [f for f in os.listdir(instances_dir) if f.endswith(".json")]
    files.sort(key=natural_sort_key)

    infeasible_list = []
    counter = 1

    for filename in files:
        print(f"Solving {filename} ...")
        file_path = os.path.join(instances_dir, filename)

        try:
            result_dict, result_text = solve_instance(file_path)
        except Exception as e:
            print(f"跳过 {filename}，错误: {e}")
            infeasible_list.append(filename)
            continue

        result_filename = f"result{counter}.txt"
        counter += 1
        result_path = os.path.join(results_dir, result_filename)

        with open(result_path, "w", encoding="utf-8") as f:
            f.write(result_text)

        if result_dict.get("status") != "OPTIMAL":
            infeasible_list.append(filename)

    if infeasible_list:
        with open(os.path.join(results_dir, "infeasible_instances.txt"), "w") as f:
            for name in infeasible_list:
                f.write(f"{name} is INFEASIBLE\n")
        print(f"\n发现 {len(infeasible_list)} 个不可行实例")
    else:
        print("\n全部实例均可行")

    print(f"结果已保存至 {results_dir}")


if __name__ == "__main__":
    solve_all()