from ortools.sat.python import cp_model
import os
import json


# 文件夹配置
data_dir = "data"        # JSON 数据文件夹
output_dir = "results"  # 输出文件夹
os.makedirs(output_dir, exist_ok=True)

infeasible_files = []

json_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
json_files.sort()


# 解析 JSON 数据
def parse_nurse_json(file_path):
    """读取 JSON 并返回标准数据结构"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    shifts = data["Shifts"]
    shiftRequirements = data["shiftRequirements"]
    workers = data["Workers"]
    senior_nurses = data["SeniorNurses"]
    pay = data.get("pay", {})
    positions = data.get("Positions", {})

    # Availability 转成 (worker, shift) tuple 列表
    availability = []
    for w, s_list in data["Availability"].items():
        for s in s_list:
            availability.append((w, s))

    return shifts, shiftRequirements, workers, senior_nurses, availability, pay, positions


# 主循环
for json_file in json_files:

    file_path = os.path.join(data_dir, json_file)

    shifts, shiftRequirements, workers, senior_nurses, availability, pay, positions = parse_nurse_json(file_path)

    # 创建 OR-Tools 模型
    mdl = cp_model.CpModel()

    # 变量
    # 分配变量: x[(worker, shift)] = 1 表示分配该护士到该班次
    x = {}
    for (w, s) in availability:
        x[(w, s)] = mdl.NewBoolVar(f"assign_{w}_{s}")

    # 临时工变量 (使用整数变量模拟)
    slacks = {}
    for s in shifts:
        slacks[s] = mdl.NewIntVar(0, shiftRequirements[s], f"slack_{s}")

    # 总临时工数
    totSlack = mdl.NewIntVar(0, sum(shiftRequirements.values()), "totSlack")

    # 每位护士的总班次
    totShifts = {}
    for w in workers:
        totShifts[w] = mdl.NewIntVar(0, len(shifts), f"totShifts_{w}")

    # 最小和最大班次
    minShift = mdl.NewIntVar(0, len(shifts), "minShift")
    maxShift = mdl.NewIntVar(0, len(shifts), "maxShift")

    # 约束
    # 班次人数
    for s in shifts:
        # 计算该班次的护士人数
        assigned_nurses = sum(x[(w, ss)] for (w, ss) in availability if ss == s)
        mdl.Add(assigned_nurses + slacks[s] == shiftRequirements[s])

    # 高级护士覆盖
    for s in shifts:
        # 计算该班次的高级护士人数
        senior_coverage = sum(x[(w, s)] for w in senior_nurses if (w, s) in availability)
        mdl.Add(senior_coverage >= 1)

    # 临时工总数
    mdl.Add(totSlack == sum(slacks[s] for s in shifts))

    # 每位护士总班次
    for w in workers:
        worker_shifts = sum(x[(ww, s)] for (ww, s) in availability if ww == w)
        mdl.Add(totShifts[w] == worker_shifts)

    # 最大最小班次
    for w in workers:
        mdl.Add(minShift <= totShifts[w])
        mdl.Add(maxShift >= totShifts[w])

    # 目标函数 (使用权重来模拟多目标)
    # 首要目标：最小化临时工总数
    # 次要目标：最小化工作量差距
    objective = totSlack * 1000 + (maxShift - minShift)
    mdl.Minimize(objective)

    # 求解器配置
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120

    # 求解
    status = solver.Solve(mdl)

    out_file = os.path.join(output_dir, json_file.replace(".json", "_result.txt"))

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        infeasible_files.append(json_file)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"Data File: {json_file}\n")
            f.write("模型不可行或无解\n")
        continue

    # 输出
    output_lines = []

    # 计算目标值
    total_slack_value = solver.Value(totSlack)
    workload_gap_value = solver.Value(maxShift) - solver.Value(minShift)

    output_lines.append(f"首要目标 (临时工总数): {total_slack_value}")
    output_lines.append(f"次要目标 (工作量差距): {workload_gap_value}\n")

    output_lines.append("每位护士总班次数:")
    for w in workers:
        output_lines.append(
            f"  {w} ({positions.get(w,'Unknown')}): {solver.Value(totShifts[w])}"
        )

    output_lines.append("")

    # 甘特图数据准备
    assignments = {}
    for (w, s) in availability:
        if solver.Value(x[(w, s)]) == 1:
            assignments.setdefault(w, []).append(s)

    output_lines.append("护士排班详情（甘特图）:")
    output_lines.append("符号：'*' = 工作，'-' = 休息\n")

    # 美观甘特图输出
    # 列宽
    name_width = max(len(w) for w in workers) + 2
    pos_width = max(len(positions.get(w, 'Unknown')) for w in workers) + 2
    shift_width = max(max(len(s) for s in shifts), 1) + 2  # 符号列宽

    # 表头
    header_parts = ["护士".ljust(name_width), "职位".ljust(pos_width)]
    for s in shifts:
        header_parts.append(s.center(shift_width))
    header = "".join(header_parts)
    output_lines.append(header)

    # 分隔线
    total_width = name_width + pos_width + len(shifts) * shift_width
    output_lines.append("-" * total_width)

    # 数据行
    for w in workers:
        row = w.ljust(name_width) + positions.get(w, 'Unknown').ljust(pos_width)
        for s in shifts:
            mark = '*' if s in assignments.get(w, []) else '-'
            row += mark.center(shift_width)
        output_lines.append(row)

    # 写入结果
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


# 不可行文件汇总
if infeasible_files:
    infeasible_path = os.path.join(output_dir, "infeasible_files.txt")
    with open(infeasible_path, "w", encoding="utf-8") as f:
        f.write("不可行或无解的数据文件列表:\n")
        for fn in infeasible_files:
            f.write(fn + "\n")

print(f"所有 {len(json_files)} 个数据文件求解完成，结果已生成在 {output_dir} 文件夹中")
if infeasible_files:
    print(f"{len(infeasible_files)} 个数据文件不可行，列表已保存到 infeasible_files.txt")