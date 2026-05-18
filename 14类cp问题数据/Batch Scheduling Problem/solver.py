import os
import json
from ortools.sat.python import cp_model
import time

def read_json_instance(filename):
    """读取新格式 JSON 实例"""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nb_tasks = data['num_tasks']
    nb_resources = data['num_resources']
    capacity = data['capacities']

    types = []
    resources = []
    duration = []
    successors = []
    nb_successors = []
    tasks_in_resource = [[] for _ in range(nb_resources)]
    nb_tasks_per_resource = [0 for _ in range(nb_resources)]

    for task in data['tasks']:
        t_id = task['id']
        t_type = task['type']
        t_res = task['resource']
        t_dur = task['duration']
        t_succ = task['successors']

        types.append(t_type)
        resources.append(t_res)
        duration.append(t_dur)
        successors.append(t_succ)
        nb_successors.append(len(t_succ))

        tasks_in_resource[t_res].append(t_id)
        nb_tasks_per_resource[t_res] += 1

    types_in_resource = [[] for _ in range(nb_resources)]
    for t in range(nb_tasks):
        types_in_resource[resources[t]].append(types[t])

    task_index_in_resource = [0 for _ in range(nb_tasks)]
    time_horizon = sum(duration)

    return (nb_tasks, nb_resources, capacity, types, resources, duration,
            nb_successors, successors, nb_tasks_per_resource, task_index_in_resource,
            types_in_resource, tasks_in_resource, time_horizon)

# 其余 solve_single_instance 和 batch_solve 函数保持不变，只需确保调用 read_json_instance

def solve_single_instance(instance_file, output_dir, time_limit=60):
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.basename(instance_file).replace('.json','')
    output_file = os.path.join(output_dir, f"{base}_solution.txt")

    (nb_tasks, nb_resources, capacity, types, resources, duration,
     nb_successors, successors, nb_tasks_per_resource, task_index_in_resource,
     types_in_resource, tasks_in_resource, time_horizon) = read_json_instance(instance_file)

    model = cp_model.CpModel()

    # 决策变量
    x = {}
    for r in range(nb_resources):
        for t in tasks_in_resource[r]:
            for b in range(nb_tasks_per_resource[r]):
                x[(t,b)] = model.NewBoolVar(f'x_t{t}_b{b}')

    batch_start = {}
    batch_dur = {}
    batch_end = {}
    for r in range(nb_resources):
        for b in range(nb_tasks_per_resource[r]):
            batch_start[(r,b)] = model.NewIntVar(0, time_horizon, f'S_r{r}_b{b}')
            batch_dur[(r,b)] = model.NewIntVar(0, time_horizon, f'D_r{r}_b{b}')
            batch_end[(r,b)] = model.NewIntVar(0, time_horizon, f'E_r{r}_b{b}')
            model.Add(batch_end[(r,b)] == batch_start[(r,b)] + batch_dur[(r,b)])

    task_start = [model.NewIntVar(0, time_horizon, f'TS_t{t}') for t in range(nb_tasks)]
    task_end = [model.NewIntVar(0, time_horizon, f'TE_t{t}') for t in range(nb_tasks)]
    for t in range(nb_tasks):
        model.Add(task_end[t] == task_start[t] + duration[t])

    # 核心约束
    for r in range(nb_resources):
        for t in tasks_in_resource[r]:
            model.AddExactlyOne(x[(t,b)] for b in range(nb_tasks_per_resource[r]))

    for r in range(nb_resources):
        tasks_r = tasks_in_resource[r]
        for b in range(nb_tasks_per_resource[r]):
            model.Add(sum(x[(t,b)] for t in tasks_r) <= capacity[r])
            is_used = model.NewBoolVar(f'is_used_r{r}_b{b}')
            model.AddMaxEquality(is_used, [x[(t,b)] for t in tasks_r])
            for i in range(len(tasks_r)):
                t1 = tasks_r[i]
                for j in range(i+1, len(tasks_r)):
                    t2 = tasks_r[j]
                    if types[t1]!=types[t2] or duration[t1]!=duration[t2]:
                        model.AddImplication(x[(t1,b)], x[(t2,b)].Not())
            model.Add(batch_dur[(r,b)] == 0).OnlyEnforceIf(is_used.Not())
            for t in tasks_r:
                model.Add(batch_dur[(r,b)] == duration[t]).OnlyEnforceIf(x[(t,b)])
                model.Add(task_start[t] == batch_start[(r,b)]).OnlyEnforceIf(x[(t,b)])
            if b < nb_tasks_per_resource[r]-1:
                is_used_next = model.NewBoolVar('')
                model.AddMaxEquality(is_used_next, [x[(t,b+1)] for t in tasks_r])
                model.AddImplication(is_used_next, is_used)

    for r in range(nb_resources):
        for b in range(1, nb_tasks_per_resource[r]):
            model.Add(batch_start[(r,b)] >= batch_end[(r,b-1)])

    for t in range(nb_tasks):
        for s in successors[t]:
            model.Add(task_end[t] <= task_start[s])

    # 目标函数
    makespan = model.NewIntVar(0, time_horizon, 'makespan')
    model.AddMaxEquality(makespan, [batch_end[(r,b)] for r in range(nb_resources) for b in range(nb_tasks_per_resource[r])])
    model.Minimize(makespan)

    # 求解
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    print(f"Solving {base} ...")
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"{base}: Makespan = {int(solver.ObjectiveValue())}, Status = {solver.StatusName(status)}")
        if output_file:
            with open(output_file, 'w') as f:
                f.write(str(int(solver.ObjectiveValue())) + "\n")
                for r in range(nb_resources):
                    f.write(str(r) + "\n")
                    for b in range(nb_tasks_per_resource[r]):
                        if b < len(tasks_in_resource[r]):
                            t = tasks_in_resource[r][b]
                            f.write(f"{t} {solver.Value(task_start[t])} {solver.Value(task_end[t])}\n")
    else:
        print(f"{base}: No solution found within the time limit.")

def batch_solve(input_dir='data', output_dir='results', time_limit=60):
    os.makedirs(output_dir, exist_ok=True)
    files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    start_time = time.time()
    for f in files:
        solve_single_instance(os.path.join(input_dir,f), output_dir, time_limit)
    print(f"Batch solving done in {time.time()-start_time:.2f} seconds")

if __name__ == "__main__":
    batch_solve(input_dir='data', output_dir='results', time_limit=300)