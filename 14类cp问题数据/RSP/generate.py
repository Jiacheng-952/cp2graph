# -*- coding: utf-8 -*-
"""
批量生成100条铁路调度实例数据
包含简单、中等、复杂三种难度
每个实例的所有数据保存在单个JSON文件中
"""

import json
import random
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

class RailwayDataGenerator:
    """铁路调度问题数据生成器类"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)
        random.seed(seed)
        self.difficulty_config = {}
        self.current_difficulty = ""
        
    def set_difficulty(self, difficulty: str):
        """根据数学模型设置难度参数"""
        if difficulty == "简单":
            self.difficulty_config = {
                "num_stations": 3,
                "num_trains": 3,
                "station_capacity": 3,
                "station_duration": 1,
                "track_duration": 2,
                "track_capacity": 2,
                "maintenance_track_offset": 2,
                "description": "简单网络 - 所有约束宽松"
            }
        elif difficulty == "中等":
            self.difficulty_config = {
                "num_stations": 4,
                "num_trains": 4,
                "station_capacity": 2,
                "station_duration": 2,
                "track_duration": 3,
                "track_capacity": 2,
                "maintenance_track_offset": 2,
                "description": "中等网络 - 有一定竞争"
            }
        elif difficulty == "复杂":
            self.difficulty_config = {
                "num_stations": 5,
                "num_trains": 4,
                "station_capacity": 2,
                "station_duration": 2,
                "track_duration": 4,
                "track_capacity": 1,
                "maintenance_track_offset": 3,
                "description": "复杂网络 - 单线运行，但保证可解"
            }
        else:
            self.difficulty_config = {
                "num_stations": 4,
                "num_trains": 4,
                "station_capacity": 2,
                "station_duration": 2,
                "track_duration": 3,
                "track_capacity": 2,
                "maintenance_track_offset": 2,
                "description": "自定义网络"
            }
        
        self.current_difficulty = difficulty
        
    def generate_railway_network(self):
        """生成铁路网络数据"""
        config = self.difficulty_config
        
        stations_data = []
        station_y_values = np.linspace(0, 20, config['num_stations'])
        
        for i in range(config['num_stations']):
            station = {
                'id': i * 2,
                'capacity': config['station_capacity'],
                'duration': config['station_duration'],
                'y': float(station_y_values[i] + random.uniform(-1, 1))
            }
            stations_data.append(station)
        
        tracks_data = []
        station_ids = [station['id'] for station in stations_data]
        
        for i in range(len(station_ids) - 1):
            track = {
                'id': station_ids[i] + 1,
                'start': station_ids[i],
                'end': station_ids[i + 1],
                'capacity': config['track_capacity'],
                'duration': config['track_duration'] + random.randint(0, 1)
            }
            tracks_data.append(track)
        
        return {
            'stations': stations_data,
            'tracks': tracks_data
        }
    
    def generate_routes(self, network_data: Dict):
        """生成路线数据"""
        stations = network_data['stations']
        tracks = network_data['tracks']
        
        routes_data = []
        
        forward_resources = []
        for i in range(len(stations)):
            forward_resources.append(str(stations[i]['id']))
            if i < len(tracks):
                forward_resources.append(str(tracks[i]['id']))
        
        reverse_resources = list(reversed(forward_resources))
        
        routes_data.append({'id': 0, 'resources': '-'.join(forward_resources)})
        routes_data.append({'id': 1, 'resources': '-'.join(reverse_resources)})
        
        return routes_data
    
    def generate_trains(self, routes_data: List[Dict], network_data: Dict):
        """生成列车数据"""
        config = self.difficulty_config
        num_trains = config['num_trains']
        
        routes = {}
        for route in routes_data:
            resources = [int(r) for r in route['resources'].split('-')]
            routes[route['id']] = resources
        
        trains_data = []
        train_ids = [chr(ord('A') + i) for i in range(num_trains)]
        
        up_trains = num_trains // 2
        down_trains = num_trains - up_trains
        
        for i in range(up_trains):
            trains_data.append({
                'id': train_ids[i],
                'route': 0,
                'start': routes[0][0]
            })
        
        for i in range(down_trains):
            trains_data.append({
                'id': train_ids[up_trains + i],
                'route': 1,
                'start': routes[1][0]
            })
        
        max_completion_time = 0
        train_times = {}
        
        for train in trains_data:
            route_id = train['route']
            full_route = routes[route_id]
            
            train_time = 0
            for res in full_route:
                if res % 2 == 1:
                    duration = network_data['tracks'][(res-1)//2]['duration']
                else:
                    duration = network_data['stations'][res//2]['duration']
                train_time += duration
            
            train_times[train['id']] = train_time
            max_completion_time = max(max_completion_time, train_time)
        
        return trains_data, max_completion_time, train_times
    
    def generate_maintenance_info(self, network_data: Dict, trains_data: List[Dict], 
                                 routes_data: List[Dict], max_completion_time: int,
                                 train_times: Dict):
        """生成维修信息"""
        config = self.difficulty_config
        tracks_data = network_data['tracks']
        
        routes = {}
        for route in routes_data:
            routes[route['id']] = [int(r) for r in route['resources'].split('-')]
        
        if len(tracks_data) >= config['maintenance_track_offset']:
            maintenance_track = tracks_data[-1]
        else:
            maintenance_track = tracks_data[-1]
        
        affected_trains = []
        unaffected_trains = []
        
        for train in trains_data:
            route_id = train['route']
            route = routes[route_id]
            if maintenance_track['id'] in route:
                affected_trains.append(train['id'])
            else:
                unaffected_trains.append(train['id'])
        
        latest_pass_time = 0
        for train in trains_data:
            if train['id'] in affected_trains:
                route_id = train['route']
                route = routes[route_id]
                
                pass_time = 0
                for res in route:
                    if res == maintenance_track['id']:
                        pass_time += maintenance_track['duration']
                        break
                    if res % 2 == 1:
                        pass_time += next(t['duration'] for t in tracks_data if t['id'] == res)
                    else:
                        pass_time += next(s['duration'] for s in network_data['stations'] if s['id'] == res)
                
                latest_pass_time = max(latest_pass_time, pass_time)
        
        maintenance_start = max(max_completion_time, latest_pass_time) + 50
        maintenance_duration = 20
        maintenance_end = maintenance_start + maintenance_duration
        
        maintenance_info = {
            'track_id': maintenance_track['id'],
            'start_time': maintenance_start,
            'end_time': maintenance_end,
            'duration': maintenance_duration,
            'track_info': {
                'start_station': maintenance_track['start'],
                'end_station': maintenance_track['end'],
                'track_duration': maintenance_track['duration']
            },
            'affected_trains': affected_trains,
            'unaffected_trains': unaffected_trains,
            'latest_pass_time': latest_pass_time,
            'max_completion_time': max_completion_time
        }
        
        return maintenance_info


def create_data_directory() -> Path:
    """创建数据目录"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    return data_dir


def generate_instance(data_dir: Path, instance_name: str, 
                     generator: RailwayDataGenerator, seed: int):
    """生成单个实例，所有数据保存在一个JSON文件中"""
    generator.seed = seed
    np.random.seed(seed)
    random.seed(seed)
    
    network_data = generator.generate_railway_network()
    routes_data = generator.generate_routes(network_data)
    trains_data, max_completion_time, train_times = generator.generate_trains(routes_data, network_data)
    maintenance_info = generator.generate_maintenance_info(
        network_data=network_data,
        trains_data=trains_data,
        routes_data=routes_data,
        max_completion_time=max_completion_time,
        train_times=train_times
    )
    
    instance_data = {
        "instance_name": instance_name,
        "difficulty": generator.current_difficulty,
        "seed": seed,
        "stations": network_data['stations'],
        "tracks": network_data['tracks'],
        "routes": routes_data,
        "trains": trains_data,
        "maintenance": maintenance_info
    }
    
    instance_file = data_dir / f"{instance_name}.json"
    with open(instance_file, 'w', encoding='utf-8') as f:
        json.dump(instance_data, f, indent=2, ensure_ascii=False)
    
    return instance_data


def generate_100_instances():
    """生成100条实例数据"""
    print("="*80)
    print("生成100条铁路调度实例数据")
    print("="*80)
    
    data_dir = create_data_directory()
    
    print(f"\n数据目录: {data_dir}")
    print(f"总实例数: 100")
    print(f"  - 简单: 34个")
    print(f"  - 中等: 33个")
    print(f"  - 复杂: 33个")
    
    instances_info = []
    
    difficulties = ["简单", "中等", "复杂"]
    num_per_difficulty = [34, 33, 33]
    
    for difficulty, num_instances in zip(difficulties, num_per_difficulty):
        print(f"\n{'='*70}")
        print(f"生成 {difficulty} 难度实例 ({num_instances}个)")
        print(f"{'='*70}")
        
        for i in range(num_instances):
            if (i + 1) % 10 == 0:
                print(f"  已生成: {i + 1}/{num_instances}")
            
            seed = 10000 + (i + 1) * 7
            generator = RailwayDataGenerator(seed=seed)
            generator.set_difficulty(difficulty)
            
            instance_name = f"{difficulty}_{i + 1}"
            
            instance_data = generate_instance(
                data_dir=data_dir,
                instance_name=instance_name,
                generator=generator,
                seed=seed
            )
            instances_info.append(instance_data)
    
    print(f"\n{'='*70}")
    print(f"✅ 100条实例数据生成完成！")
    print(f"{'='*70}")
    print(f"总实例数: {len(instances_info)}")
    print(f"  - 简单: {num_per_difficulty[0]}个")
    print(f"  - 中等: {num_per_difficulty[1]}个")
    print(f"  - 复杂: {num_per_difficulty[2]}个")
    print(f"所有文件保存在: {data_dir}")


if __name__ == "__main__":
    generate_100_instances()
