import json
import os
import time
from ortools.sat.python import cp_model


# 1. 读取 JSON
def load_instance_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return (
        data["num_rooms"],
        data["num_nurses"],
        data["num_surgeries"],
        data["min_start"],
        data["max_end"],
        data["needed_nurses"],
        data["shift_earliest_start"],
        data["shift_latest_end"],
        data["max_shift_duration"],
        data["incompatible_rooms"],
        data["duration"],
    )


# 2. OR-Tools 求解
def solve_surgery_scheduling(instance_data):
    (num_rooms, num_nurses, num_surgeries, min_start, max_end,
     needed_nurses, shift_earliest_start, shift_latest_end,
     max_shift_duration, incompatible_rooms, duration) = instance_data

    model = cp_model.CpModel()

    # ---------- 变量 ----------
    start_time = [
        model.NewIntVar(min_start[s], max_end[s], f"start_{s}")
        for s in range(num_surgeries)
    ]

    end_time = [
        model.NewIntVar(min_start[s], max_end[s], f"end_{s}")
        for s in range(num_surgeries)
    ]

    assign_room = {}
    for s in range(num_surgeries):
        for r in range(num_rooms):
            assign_room[s, r] = model.NewBoolVar(f"assign_room_{s}_{r}")

    assign_nurse = {}
    for s in range(num_surgeries):
        for n in range(num_nurses):
            assign_nurse[s, n] = model.NewBoolVar(f"assign_nurse_{s}_{n}")

    order_room = {}
    for s1 in range(num_surgeries):
        for s2 in range(num_surgeries):
            if s1 != s2:
                order_room[s1, s2] = model.NewBoolVar(f"order_room_{s1}_{s2}")

    order_nurse = {}
    for s1 in range(num_surgeries):
        for s2 in range(num_surgeries):
            if s1 != s2:
                for n in range(num_nurses):
                    order_nurse[s1, s2, n] = model.NewBoolVar(f"order_nurse_{s1}_{s2}_{n}")

    nurse_shift_start = [
        model.NewIntVar(shift_earliest_start[n], shift_latest_end[n], f"shift_start_{n}")
        for n in range(num_nurses)
    ]

    nurse_shift_end = [
        model.NewIntVar(shift_earliest_start[n], shift_latest_end[n], f"shift_end_{n}")
        for n in range(num_nurses)
    ]

    makespan = model.NewIntVar(0, max(max_end), "makespan")

    M = sum(max_end)

    # ---------- 约束 ----------
    for s in range(num_surgeries):
        model.Add(end_time[s] == start_time[s] + duration[s])
        model.Add(start_time[s] >= min_start[s])
        model.Add(end_time[s] <= max_end[s])

        model.Add(sum(assign_room[s, r] for r in range(num_rooms)) == 1)

    # 不兼容房间
    for s in range(num_surgeries):
        for r in range(num_rooms):
            if incompatible_rooms[s][r] == 1:
                model.Add(assign_room[s, r] == 0)

    # 房间冲突（不重叠）
    for s1 in range(num_surgeries):
        for s2 in range(s1 + 1, num_surgeries):
            for r in range(num_rooms):
                model.Add(
                    order_room[s1, s2] + order_room[s2, s1]
                    >= assign_room[s1, r] + assign_room[s2, r] - 1
                )

                model.Add(
                    end_time[s1]
                    <= start_time[s2] + M * (1 - order_room[s1, s2])
                )

                model.Add(
                    end_time[s2]
                    <= start_time[s1] + M * (1 - order_room[s2, s1])
                )

    # 护士需求
    for s in range(num_surgeries):
        model.Add(sum(assign_nurse[s, n] for n in range(num_nurses)) >= needed_nurses[s])

    # 护士冲突
    for n in range(num_nurses):
        for s1 in range(num_surgeries):
            for s2 in range(s1 + 1, num_surgeries):
                model.Add(
                    order_nurse[s1, s2, n] + order_nurse[s2, s1, n]
                    >= assign_nurse[s1, n] + assign_nurse[s2, n] - 1
                )

                model.Add(
                    end_time[s1]
                    <= start_time[s2] + M * (1 - order_nurse[s1, s2, n])
                )

                model.Add(
                    end_time[s2]
                    <= start_time[s1] + M * (1 - order_nurse[s2, s1, n])
                )

        # shift 约束
        model.Add(nurse_shift_start[n] >= shift_earliest_start[n])
        model.Add(nurse_shift_end[n] <= shift_latest_end[n])
        model.Add(nurse_shift_end[n] - nurse_shift_start[n] <= max_shift_duration)

    # makespan
    for s in range(num_surgeries):
        model.Add(makespan >= end_time[s])

    # ---------- 目标 ----------
    model.Minimize(makespan)

    # ---------- 求解 ----------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60

    t0 = time.time()
    status = solver.Solve(model)
    t1 = time.time()

    python_time = t1 - t0

    output_lines = []
    feasible = False

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        feasible = True
        makespan_value = solver.Value(makespan) / 60

        output_lines.append(f"最小完工时间 (Makespan): {makespan_value:.2f} 小时")
        output_lines.append("")
        output_lines.append("--- 手术安排 ---")

        for s in range(num_surgeries):
            room = None
            for r in range(num_rooms):
                if solver.Value(assign_room[s, r]) == 1:
                    room = r
                    break

            nurses = [n for n in range(num_nurses) if solver.Value(assign_nurse[s, n]) == 1]

            start = solver.Value(start_time[s]) / 60
            end = solver.Value(end_time[s]) / 60

            output_lines.append(
                f"手术 {s}: 房间 {room}, 开始 {start:.2f}h, 结束 {end:.2f}h, 护士 {nurses}"
            )

        output_lines.append("")
        output_lines.append(f"求解时间: {python_time:.2f} 秒")

    else:
        output_lines.append("infeasible")
        output_lines.append(f"求解时间: {python_time:.2f} 秒")

    return "\n".join(output_lines), feasible, python_time


# 3. 批处理
if __name__ == "__main__":
    output_folder = "results_ortools"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(current_dir, "data")

    os.makedirs(output_folder, exist_ok=True)

    json_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".json")])

    final_txt_path = os.path.join(output_folder, "final_results_ortools.txt")
    infeasible_count = 0

    with open(final_txt_path, "w", encoding="utf-8") as final_file:
        final_file.write("Instance\tStatus\tTime(sec)\tMakespan\n")

        for json_file in json_files:
            json_path = os.path.join(input_folder, json_file)
            instance_data = load_instance_from_json(json_path)

            result_str, feasible, python_time = solve_surgery_scheduling(instance_data)

            status_str = "Feasible" if feasible else "Infeasible"
            infeasible_count += 0 if feasible else 1

            makespan_line = "infeasible"
            for line in result_str.splitlines():
                if line.startswith("最小完工时间"):
                    makespan_line = line.split(":")[1].strip().split()[0]
                    break

            final_file.write(
                f"{json_file}\t{status_str}\t{python_time:.2f}\t{makespan_line}\n"
            )

            print(f"{json_file} processed -> {status_str}")

            out_file = os.path.join(output_folder, json_file.replace(".json", "_result.txt"))
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(result_str)

    print("\n批量求解完成")
    print(f"不可行实例数量：{infeasible_count}")
    print(f"结果保存在 {final_txt_path}")