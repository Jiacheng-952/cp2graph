# -*- coding: utf-8 -*-
import os
import json
import time
from ortools.sat.python import cp_model


# =========================
# 单个实例求解
# =========================
def solve_instance(json_path):

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    unfulfilled_cost = metadata.get("unfulfilled_cost", 100)

    sets = data.get("sets", {})
    restaurants = sets.get("restaurants", [])
    employees = sets.get("employees", [])
    shifts = sets.get("shifts", [])
    skills = sets.get("skills", [])

    demand = {
        (d["restaurant"], d["shift"], d["skill"]): d["required"]
        for d in data.get("demand", [])
    }

    employee_has_skill = {
        (d["employee"], d["skill"]): d["has_skill"]
        for d in data.get("employee_skills", [])
    }

    employee_does_shift = {
        (d["employee"], d["shift"]): d["available"]
        for d in data.get("employee_availability", [])
    }

    preference_cost = {
        (d["employee"], d["skill"]): d["cost"]
        for d in data.get("preference_costs", [])
    }

    # 默认 cost
    for e in employees:
        for k in skills:
            if (e, k) not in preference_cost:
                preference_cost[(e, k)] = 1

    # ---------- 建模 ----------
    model = cp_model.CpModel()

    x = {}
    for r in restaurants:
        for e in employees:
            for s in shifts:
                for k in skills:
                    x[r, e, s, k] = model.NewBoolVar(f"x_{r}_{e}_{s}_{k}")

    max_demand = max(demand.values()) if demand else 10

    u = {}
    for r in restaurants:
        for s in shifts:
            for k in skills:
                u[r, s, k] = model.NewIntVar(0, max_demand, f"u_{r}_{s}_{k}")

    # ---------- 约束 ----------
    for r in restaurants:
        for s in shifts:
            for k in skills:
                model.Add(
                    sum(x[r, e, s, k] for e in employees) + u[r, s, k]
                    == demand.get((r, s, k), 0)
                )

    for e in employees:
        for s in shifts:
            model.Add(
                sum(x[r, e, s, k] for r in restaurants for k in skills)
                <= employee_does_shift.get((e, s), 0)
            )

    for r in restaurants:
        for e in employees:
            for s in shifts:
                for k in skills:
                    model.Add(
                        x[r, e, s, k]
                        <= employee_has_skill.get((e, k), 0)
                    )

    for e in employees:
        model.Add(
            sum(x[r, e, s, k] for r in restaurants for s in shifts for k in skills)
            <= 1
        )

    # ---------- 目标 ----------
    model.Minimize(
        sum(
            preference_cost[(e, k)] * x[r, e, s, k]
            for r in restaurants for e in employees
            for s in shifts for k in skills
        )
        +
        sum(
            unfulfilled_cost * u[r, s, k]
            for r in restaurants for s in shifts for k in skills
        )
    )

    # ---------- 求解 ----------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 8

    t0 = time.time()
    status = solver.Solve(model)
    t1 = time.time()

    solve_time = t1 - t0

    # ---------- 结果文本 ----------
    output_lines = []

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        obj = solver.ObjectiveValue()

        output_lines.append(f"Status: Feasible")
        output_lines.append(f"Objective: {obj:.2f}")
        output_lines.append(f"Solve Time: {solve_time:.2f} sec\n")

        # 分配结果
        output_lines.append("=== Assignment ===")
        for r in restaurants:
            output_lines.append(f"\nRestaurant {r}")
            for s in shifts:
                output_lines.append(f"  Shift {s}")
                for k in skills:
                    assigned = [
                        e for e in employees
                        if solver.Value(x[r, e, s, k]) == 1
                    ]
                    if assigned:
                        output_lines.append(
                            f"    Skill {k}: {len(assigned)} -> {', '.join(assigned)}"
                        )

        # 未满足需求
        output_lines.append("\n=== Unfulfilled Demand ===")
        for r in restaurants:
            for s in shifts:
                for k in skills:
                    val = solver.Value(u[r, s, k])
                    if val > 0:
                        output_lines.append(
                            f"{r}, {s}, {k}: {val}"
                        )

        return True, obj, solve_time, "\n".join(output_lines)

    else:
        output_lines.append("Status: Infeasible")
        output_lines.append(f"Solve Time: {solve_time:.2f} sec")

        return False, None, solve_time, "\n".join(output_lines)


# =========================
# 批量求解
# =========================
def solve_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(current_dir, "data")
    output_dir = os.path.join(current_dir, "results")
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
    files.sort()

    summary_path = os.path.join(output_dir, "summary.txt")

    infeasible_count = 0

    with open(summary_path, "w", encoding="utf-8") as summary:
        summary.write("Instance\tStatus\tTime(sec)\tObjective\n")

        for file in files:
            print(f"Solving {file} ...")

            path = os.path.join(input_dir, file)

            try:
                feasible, obj, solve_time, result_text = solve_instance(path)
            except Exception as e:
                print(f"错误: {e}")
                feasible = False
                obj = None
                solve_time = 0
                result_text = f"Error: {e}"

            # 写单独结果文件
            result_file = os.path.join(output_dir, file.replace(".json", "_result.txt"))
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(result_text)

            status = "Feasible" if feasible else "Infeasible"
            if not feasible:
                infeasible_count += 1

            obj_str = f"{obj:.2f}" if obj is not None else "NA"

            summary.write(f"{file}\t{status}\t{solve_time:.2f}\t{obj_str}\n")

            print(f" -> {status}, time={solve_time:.2f}s, obj={obj_str}")

    print("\n======================")
    print("批量求解完成")
    print(f"不可行数量: {infeasible_count}")
    print(f"汇总文件: {summary_path}")


if __name__ == "__main__":
    solve_all()