# -*- coding: utf-8 -*-
"""
铁路调度问题求解器 - 基于OR-Tools
读取data文件夹中的所有实例JSON文件并求解
每个实例的结果保存到单个JSON文件中
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("请安装OR-Tools: pip install ortools")
    sys.exit(1)


def find_instances_in_data_folder():
    """查找data文件夹中的所有实例JSON文件"""
    current_dir = Path(__file__).parent
    data_dir = current_dir / "data"
    
    if not data_dir.exists():
        print(f"错误: data文件夹不存在: {data_dir}")
        return {'简单': [], '中等': [], '复杂': []}
    
    instances_by_difficulty = {
        '简单': [],
        '中等': [],
        '复杂': []
    }
    
    json_files = list(data_dir.glob("*.json"))
    
    for json_file in json_files:
        instance_name = json_file.stem
        difficulty = '未知'
        if instance_name.startswith('简单_'):
            difficulty = '简单'
        elif instance_name.startswith('中等_'):
            difficulty = '中等'
        elif instance_name.startswith('复杂_'):
            difficulty = '复杂'
        
        instance_info = {
            'name': instance_name,
            'difficulty': difficulty,
            'file': json_file
        }
        
        if difficulty in instances_by_difficulty:
            instances_by_difficulty[difficulty].append(instance_info)
    
    def sort_key(x):
        parts = x['name'].split('_')
        if len(parts) == 2 and parts[1].isdigit():
            return (parts[0], int(parts[1]))
        return (parts[0], 0)
    
    for diff in instances_by_difficulty:
        instances_by_difficulty[diff].sort(key=sort_key)
    
    return instances_by_difficulty


def load_instance_data(instance_info):
    """加载单个实例的数据"""
    instance_file = instance_info['file']
    
    with open(instance_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stations_data = data['stations']
    df_stations = {item['id']: item for item in stations_data}
    
    tracks_data = data['tracks']
    df_tracks = {item['id']: item for item in tracks_data}
    
    routes_data = data['routes']
    df_routes = {item['id']: [int(res) for res in item['resources'].split('-')] for item in routes_data}
    
    trains_data = data['trains']
    
    trains = {}
    for item in trains_data:
        route_id = item['route']
        start_resource = item['start']
        full_route = df_routes[route_id]
        try:
            start_idx = full_route.index(start_resource)
            trains[item['id']] = full_route[start_idx:]
        except ValueError:
            trains[item['id']] = full_route
    
    duration = {}
    for track_id, track_info in df_tracks.items():
        duration[track_id] = track_info['duration']
    for station_id, station_info in df_stations.items():
        duration[station_id] = station_info['duration']
    
    capacity = {}
    for track_id, track_info in df_tracks.items():
        capacity[track_id] = track_info['capacity']
    for station_id, station_info in df_stations.items():
        capacity[station_id] = station_info['capacity']
    
    maintenance_info = data.get('maintenance', None)
    
    resource_type = {key: 'S' for key in df_stations.keys()} | {key: 'T' for key in df_tracks.keys()}
    resources = list(resource_type.keys())
    
    return {
        'trains': trains,
        'duration': duration,
        'capacity': capacity,
        'resources': resources,
        'maintenance_info': maintenance_info,
        'resource_type': resource_type,
        'num_stations': len(df_stations),
        'num_tracks': len(df_tracks)
    }


def solve_with_ortools(data, time_limit=300):
    """使用OR-Tools CP-SAT求解器求解"""
    trains = data['trains']
    duration = data['duration']
    capacity = data['capacity']
    resources = data['resources']
    maintenance_info = data['maintenance_info']
    resource_type = data['resource_type']
    
    model = cp_model.CpModel()
    
    events = [(train, resource) for train, route in trains.items() for resource in route]
    
    t = {}
    for train, resource in events:
        t[train, resource] = model.NewIntVar(0, 10000, f't_{train}_{resource}')
    
    tf = {}
    for train in trains:
        tf[train] = model.NewIntVar(0, 10000, f'tf_{train}')
    
    def tvar(train, resource):
        return t[train, resource] if resource is not None else tf[train]
    
    for train, route in trains.items():
        for i in range(len(route) - 1):
            model.Add(t[train, route[i+1]] - t[train, route[i]] >= duration[route[i]])
        
        model.Add(tf[train] - t[train, route[-1]] >= duration[route[-1]])
        
        model.Add(t[train, route[0]] == 0)
    
    M = sum(duration.values()) * len(trains) * 2
    
    for r in resources:
        resource_trains = [train for train, res in events if res == r]
        
        if len(resource_trains) <= capacity[r]:
            continue
        
        train_pairs = [(resource_trains[i], resource_trains[j]) 
                      for i in range(len(resource_trains)) 
                      for j in range(i+1, len(resource_trains))]
        
        y_vars = {}
        x_vars = {}
        
        for train_i, train_j in train_pairs:
            y_vars[train_i, train_j, 0] = model.NewBoolVar(f'y_{r}_{train_i}_{train_j}_0')
            y_vars[train_i, train_j, 1] = model.NewBoolVar(f'y_{r}_{train_i}_{train_j}_1')
            x_vars[train_i, train_j] = model.NewBoolVar(f'x_{r}_{train_i}_{train_j}')
            
            route_i = trains[train_i]
            route_j = trains[train_j]
            
            try:
                idx_i = route_i.index(r)
                next_i = route_i[idx_i + 1] if idx_i < len(route_i) - 1 else None
            except ValueError:
                continue
            
            try:
                idx_j = route_j.index(r)
                next_j = route_j[idx_j + 1] if idx_j < len(route_j) - 1 else None
            except ValueError:
                continue
            
            t_ir = t[train_i, r]
            t_iu = t[train_i, next_i] if next_i else tf[train_i]
            t_jr = t[train_j, r]
            t_jv = t[train_j, next_j] if next_j else tf[train_j]
            
            model.Add(t_jr - t_iu >= -M * (1 - y_vars[train_i, train_j, 0]))
            model.Add(t_ir - t_jv >= -M * (1 - y_vars[train_i, train_j, 1]))
            model.Add(t_jv - t_ir >= -M * (1 - x_vars[train_i, train_j]))
            model.Add(t_iu - t_jr >= -M * (1 - x_vars[train_i, train_j]))
            model.Add(y_vars[train_i, train_j, 0] + y_vars[train_i, train_j, 1] + x_vars[train_i, train_j] == 1)
        
        if capacity[r] == 1:
            for train_i, train_j in train_pairs:
                model.Add(x_vars[train_i, train_j] == 0)
        else:
            for subset in [(resource_trains[i], resource_trains[j], resource_trains[k]) 
                          for i in range(len(resource_trains)) 
                          for j in range(i+1, len(resource_trains)) 
                          for k in range(j+1, len(resource_trains))]:
                if len(subset) >= capacity[r] + 1:
                    subset_pairs = [(subset[i], subset[j]) 
                                   for i in range(len(subset)) 
                                   for j in range(i+1, len(subset))]
                    model.Add(sum(x_vars[u, v] for u, v in subset_pairs) <= len(subset_pairs) - 1)
    
    if maintenance_info:
        maintenance_track_id = maintenance_info['track_id']
        maintenance_start_time = maintenance_info['start_time']
        maintenance_end_time = maintenance_info['end_time']
        
        trains_on_maintenance = [train for train, route in trains.items() if maintenance_track_id in route]
        
        if trains_on_maintenance:
            m_vars = {}
            for train in trains_on_maintenance:
                m_vars[train] = model.NewBoolVar(f'm_{train}')
                
                model.Add(t[train, maintenance_track_id] + duration[maintenance_track_id] <= 
                         maintenance_start_time + M * (1 - m_vars[train]))
                model.Add(t[train, maintenance_track_id] >= 
                         maintenance_end_time - M * m_vars[train])
    
    def delay(train):
        min_duration = sum(duration[resource] for resource in trains[train])
        return tf[train] - min_duration
    
    model.Minimize(sum(delay(train) for train in trains))
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    
    status = solver.Solve(model)
    
    solution = None
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        schedule = {}
        for train, resource in events:
            if (train, resource) in t:
                schedule[(train, resource)] = solver.Value(t[train, resource])
        for train in trains:
            schedule[(train, 'finish')] = solver.Value(tf[train])
        
        total_delay = sum(solver.Value(delay(train)) for train in trains)
        
        solution = {
            'status': 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
            'total_delay': total_delay,
            'solve_time': solver.ResponseStats().split(' ')[0] if 'solve_time' in solver.ResponseStats() else 'N/A',
            'schedule': {f"{k[0]}_{k[1]}": v for k, v in schedule.items()}
        }
    
    return solution


def save_results(instance_info, solution, results_dir):
    """保存求解结果到单个TXT文件"""
    instance_name = instance_info['name']
    difficulty = instance_info['difficulty']
    
    results_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = results_dir / f"{instance_name}_result.txt"
    
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f"实例名称: {instance_name}\n")
        f.write(f"难度: {difficulty}\n")
        f.write(f"求解器: OR-Tools CP-SAT\n")
        f.write(f"时间戳: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n")
        
        if solution:
            f.write(f"求解状态: {solution['status']}\n")
            f.write(f"总延误: {solution['total_delay']}\n")
            f.write(f"求解时间: {solution['solve_time']}\n")
            f.write("-"*60 + "\n")
            f.write("调度方案:\n")
            for key, value in solution['schedule'].items():
                f.write(f"  {key}: {value}\n")
        else:
            f.write("求解状态: 未找到可行解\n")
    
    return result_file


def select_100_instances(instances_by_difficulty):
    """从三个难度中各均匀选择约33-34个实例"""
    simple = instances_by_difficulty['简单']
    medium = instances_by_difficulty['中等']
    complex_instances = instances_by_difficulty['复杂']
    
    n_simple = min(34, len(simple))
    n_medium = min(33, len(medium))
    n_complex = min(33, len(complex_instances))
    
    selected = []
    
    step_simple = len(simple) / n_simple if n_simple > 0 else 0
    for i in range(n_simple):
        idx = int(i * step_simple)
        if idx < len(simple):
            selected.append(simple[idx])
    
    step_medium = len(medium) / n_medium if n_medium > 0 else 0
    for i in range(n_medium):
        idx = int(i * step_medium)
        if idx < len(medium):
            selected.append(medium[idx])
    
    step_complex = len(complex_instances) / n_complex if n_complex > 0 else 0
    for i in range(n_complex):
        idx = int(i * step_complex)
        if idx < len(complex_instances):
            selected.append(complex_instances[idx])
    
    selected.sort(key=lambda x: (x['difficulty'], x['name']))
    
    return selected


def main():
    """主函数"""
    print("="*80)
    print("🚂 铁路调度问题求解器 - OR-Tools版")
    print("读取data文件夹中的所有实例JSON文件")
    print("="*80)
    
    current_dir = Path(__file__).parent
    data_dir = current_dir / "data"
    results_dir = current_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n当前工作目录: {current_dir}")
    print(f"数据目录: {data_dir.absolute()}")
    print(f"结果保存目录: {results_dir.absolute()}")
    
    print("\n正在查找实例...")
    instances_by_difficulty = find_instances_in_data_folder()
    
    total_available = sum(len(v) for v in instances_by_difficulty.values())
    print(f"找到 {total_available} 个实例:")
    for diff, instances in instances_by_difficulty.items():
        print(f"  {diff}: {len(instances)} 个")
    
    print("\n正在均匀选择100个实例...")
    selected_instances = select_100_instances(instances_by_difficulty)
    
    print(f"\n选中 {len(selected_instances)} 个实例:")
    for inst in selected_instances:
        print(f"  [{inst['difficulty']:4s}] {inst['name']}")
    
    print("\n" + "="*80)
    print("开始求解...")
    print("="*80)
    
    results = []
    success_count = 0
    fail_count = 0
    
    for idx, instance_info in enumerate(selected_instances, 1):
        instance_name = instance_info['name']
        difficulty = instance_info['difficulty']
        
        print(f"\n[{idx}/{len(selected_instances)}] 求解实例: {instance_name} ({difficulty})")
        
        try:
            data = load_instance_data(instance_info)
            
            print(f"  数据加载完成: {data['num_stations']}个站点, {data['num_tracks']}个轨道, {len(data['trains'])}列列车")
            
            solution = solve_with_ortools(data, time_limit=300)
            
            if solution:
                result_file = save_results(instance_info, solution, results_dir)
                print(f"  ✓ 求解成功: 状态={solution['status']}, 总延误={solution['total_delay']:.2f}")
                print(f"  结果已保存: {result_file}")
                success_count += 1
            else:
                print(f"  ✗ 未找到可行解")
                fail_count += 1
            
            results.append({
                'instance': instance_name,
                'difficulty': difficulty,
                'success': solution is not None,
                'solution': solution
            })
            
        except Exception as e:
            print(f"  ✗ 求解失败: {str(e)}")
            fail_count += 1
            results.append({
                'instance': instance_name,
                'difficulty': difficulty,
                'success': False,
                'error': str(e)
            })
    
    print("\n" + "="*80)
    print("求解完成!")
    print("="*80)
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"总计: {len(selected_instances)} 个")


if __name__ == "__main__":
    main()
