# -*- coding: utf-8 -*-
"""
开放车间调度问题（OSSP）数据生成脚本 - 增强版
可以生成不同的随机实例
"""

import random
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

class OSSPDataGenerator:
    """OSSP数据生成器类"""
    
    def __init__(self, seed: int = None):
        """初始化生成器
        
        Args:
            seed: 随机种子，如果为None则使用当前时间作为种子（每次不同）
        """
        if seed is None:
            # 使用当前时间作为种子，确保每次运行都不同
            seed = int(datetime.now().timestamp() * 1000) % 10000
        self.seed = seed
        random.seed(seed)
        print(f"使用随机种子: {seed}")
    
    def generate_processing_times(self, 
                                  num_jobs: int = 3, 
                                  num_machines: int = 3,
                                  min_time: int = 1,
                                  max_time: int = 10) -> List[List[int]]:
        """生成加工时间矩阵
        
        Args:
            num_jobs: 工件数量
            num_machines: 机器数量
            min_time: 最小加工时间
            max_time: 最大加工时间
            
        Returns:
            加工时间矩阵
        """
        print(f"生成 {num_jobs}×{num_machines} OSSP 实例...")
        print(f"加工时间范围: [{min_time}, {max_time}]")
        
        processing_times = []
        for job_id in range(num_jobs):
            job_times = [random.randint(min_time, max_time) 
                        for _ in range(num_machines)]
            processing_times.append(job_times)
        
        return processing_times
    
    def save_to_json(self, 
                     processing_times: List[List[int]], 
                     filename: str = None,
                     statistics: Dict = None) -> str:
        """将加工时间矩阵保存为JSON文件
        
        Args:
            processing_times: 加工时间矩阵
            filename: 输出文件名，如果为None则自动生成
            statistics: 统计信息字典，如果为None则不包含
            
        Returns:
            保存的文件路径
        """
        # 创建目录
        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(exist_ok=True)
        
        # 生成文件名
        if filename is None:
            num_jobs = len(processing_times)
            num_machines = len(processing_times[0]) if processing_times else 0
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ossp_{num_jobs}j_{num_machines}m_{timestamp}.json"
        
        filepath = data_dir / filename
        
        # 构建数据字典
        data = {
            "num_jobs": len(processing_times),
            "num_machines": len(processing_times[0]) if processing_times else 0,
            "processing_times": processing_times
        }
        
        if statistics is not None:
            data["statistics"] = statistics
        
        # 写入JSON文件
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"数据已保存到: {filepath}")
        return str(filepath)
    
    def print_matrix(self, processing_times: List[List[int]]) -> None:
        """打印加工时间矩阵"""
        num_jobs = len(processing_times)
        num_machines = len(processing_times[0]) if processing_times else 0
        
        print("\n生成的加工时间矩阵:")
        print("=" * (num_machines * 8 + 10))
        
        # 打印表头
        header = "job_id | " + " | ".join(f"m{m:2d}" for m in range(num_machines))
        print(header)
        print("-" * (num_machines * 8 + 10))
        
        # 打印数据
        for job_id, times in enumerate(processing_times):
            row = f"  {job_id:3d}  | " + " | ".join(f"{t:3d}" for t in times)
            print(row)
        
        print("=" * (num_machines * 8 + 10))
    
    def calculate_statistics(self, processing_times: List[List[int]]) -> Dict:
        """计算数据统计信息"""
        num_jobs = len(processing_times)
        num_machines = len(processing_times[0]) if processing_times else 0
        
        total_operations = num_jobs * num_machines
        total_processing_time = sum(sum(job) for job in processing_times)
        avg_processing_time = total_processing_time / total_operations if total_operations > 0 else 0
        
        all_times = [time for job in processing_times for time in job]
        min_time = min(all_times) if all_times else 0
        max_time = max(all_times) if all_times else 0
        
        job_totals = [sum(job) for job in processing_times]
        job_averages = [total / num_machines for total in job_totals]
        
        machine_totals = []
        for m in range(num_machines):
            machine_total = sum(job[m] for job in processing_times)
            machine_totals.append(machine_total)
        
        machine_averages = [total / num_jobs for total in machine_totals]
        
        machine_lower_bound = max(machine_totals) if machine_totals else 0
        job_lower_bound = max(job_totals) if job_totals else 0
        combined_lower_bound = max(machine_lower_bound, job_lower_bound)
        
        statistics = {
            "num_jobs": num_jobs,
            "num_machines": num_machines,
            "total_operations": total_operations,
            "total_processing_time": total_processing_time,
            "average_processing_time": avg_processing_time,
            "min_processing_time": min_time,
            "max_processing_time": max_time,
            "job_totals": job_totals,
            "job_averages": job_averages,
            "machine_totals": machine_totals,
            "machine_averages": machine_averages,
            "lower_bounds": {
                "machine_bound": machine_lower_bound,
                "job_bound": job_lower_bound,
                "combined_bound": combined_lower_bound
            }
        }
        
        return statistics
    
    def print_statistics(self, statistics: Dict) -> None:
        """打印统计信息"""
        print("\n" + "="*60)
        print("数据统计信息:")
        print("="*60)
        
        print(f"\n基本信息:")
        print(f"  工件数量: {statistics['num_jobs']}")
        print(f"  机器数量: {statistics['num_machines']}")
        print(f"  总工序数: {statistics['total_operations']}")
        
        print(f"\n加工时间统计:")
        print(f"  总加工时间: {statistics['total_processing_time']}")
        print(f"  平均加工时间: {statistics['average_processing_time']:.2f}")
        print(f"  最小加工时间: {statistics['min_processing_time']}")
        print(f"  最大加工时间: {statistics['max_processing_time']}")
        
        print(f"\n各工件加工时间统计:")
        for job_id, (total, avg) in enumerate(zip(statistics['job_totals'], 
                                                   statistics.get('job_averages', []))):
            print(f"  工件 {job_id:2d}: 总时间={total:3d}, 平均={avg:.2f}")
        
        print(f"\n各机器负荷统计:")
        for m, total in enumerate(statistics['machine_totals']):
            print(f"  机器 {m:2d}: 总时间={total:3d}, 平均={statistics.get('machine_averages', [0])[m]:.2f}")
        
        print(f"\n理论下界:")
        print(f"  机器负荷下界: {statistics['lower_bounds']['machine_bound']}")
        print(f"  工件总时间下界: {statistics['lower_bounds']['job_bound']}")
        print(f"  综合下界: {statistics['lower_bounds']['combined_bound']}")


def generate_random_instance():
    """生成随机实例（每次运行不同）"""
    print("\n" + "="*70)
    print("生成随机OSSP实例")
    print("="*70)
    
    # 随机确定问题规模
    num_jobs = random.randint(3, 8)
    num_machines = random.randint(3, 6)
    min_time = random.randint(1, 3)
    max_time = random.randint(8, 15)
    
    # 使用None种子，自动生成不同实例
    generator = OSSPDataGenerator(seed=None)
    
    # 生成数据
    processing_times = generator.generate_processing_times(
        num_jobs=num_jobs,
        num_machines=num_machines,
        min_time=min_time,
        max_time=max_time
    )
    
    # 打印矩阵
    generator.print_matrix(processing_times)
    
    # 计算并打印统计信息
    statistics = generator.calculate_statistics(processing_times)
    generator.print_statistics(statistics)
    
    # 保存文件
    generator.save_to_json(processing_times, statistics=statistics)
    
    return processing_times


def generate_fixed_instance(num_jobs=3, num_machines=3, seed=42):
    """生成固定种子实例（可复现）"""
    print("\n" + "="*70)
    print(f"生成固定种子OSSP实例 (种子: {seed})")
    print("="*70)
    
    generator = OSSPDataGenerator(seed=seed)
    
    processing_times = generator.generate_processing_times(
        num_jobs=num_jobs,
        num_machines=num_machines,
        min_time=1,
        max_time=10
    )
    
    generator.print_matrix(processing_times)
    statistics = generator.calculate_statistics(processing_times)
    generator.print_statistics(statistics)
    
    # 保存文件，包含种子信息
    filename = f"ossp_{num_jobs}j_{num_machines}m_seed{seed}.json"
    generator.save_to_json(processing_times, filename, statistics)
    
    return processing_times


def generate_batch_instances(num_instances=5):
    """批量生成多个不同实例"""
    print("\n" + "="*70)
    print(f"批量生成 {num_instances} 个OSSP实例")
    print("="*70)
    
    instances = []
    for i in range(num_instances):
        print(f"\n--- 实例 {i+1}/{num_instances} ---")
        
        # 随机生成参数
        num_jobs = random.randint(3, 8)
        num_machines = random.randint(3, 6)
        
        # 使用当前时间戳作为种子
        seed = int(datetime.now().timestamp() * 1000 + i) % 10000
        generator = OSSPDataGenerator(seed=seed)
        
        processing_times = generator.generate_processing_times(
            num_jobs=num_jobs,
            num_machines=num_machines,
            min_time=1,
            max_time=10
        )
        
        # 保存文件
        filename = f"ossp_{num_jobs}j_{num_machines}m_{i+1:02d}.json"
        generator.save_to_json(processing_times, filename)
        
        instances.append(processing_times)
    
    print(f"\n已生成 {num_instances} 个实例")
    return instances


def generate_2000_instances():
    """生成2000条随机实例数据"""
    print("\n" + "="*70)
    print("生成2000条随机OSSP实例数据")
    print("="*70)
    
    instances = []
    
    for i in range(2000):
        if (i + 1) % 100 == 0:
            print(f"已生成 {i+1}/2000 个实例...")
        
        # 随机生成参数
        num_jobs = random.randint(3, 8)
        num_machines = random.randint(3, 6)
        min_time = random.randint(1, 5)
        max_time = random.randint(10, 20)
        
        # 使用随机种子确保每次生成不同的实例
        seed = random.randint(0, 999999)
        generator = OSSPDataGenerator(seed=seed)
        
        processing_times = generator.generate_processing_times(
            num_jobs=num_jobs,
            num_machines=num_machines,
            min_time=min_time,
            max_time=max_time
        )
        
        # 保存文件
        filename = f"ossp_{num_jobs}j_{num_machines}m_{i+1:04d}.json"
        generator.save_to_json(processing_times, filename)
        
        instances.append(processing_times)
    
    print(f"\n已成功生成 2000 个实例，保存在 data 目录中")
    return instances


def main():
    """主函数：交互式菜单"""
    print("="*70)
    print("开放车间调度问题 (OSSP) 数据生成器")
    print("="*70)
    
    while True:
        print("\n请选择生成模式:")
        print("1. 生成随机实例（每次运行不同）")
        print("2. 生成固定种子实例（可复现）")
        print("3. 批量生成多个实例")
        print("4. 生成示例实例（3×3，种子42）")
        print("5. 生成2000个随机实例")
        print("6. 退出")
        
        choice = input("\n请输入选项 (1-6): ").strip()
        
        if choice == '1':
            generate_random_instance()
            
        elif choice == '2':
            try:
                num_jobs = int(input("请输入工件数量 (默认3): ") or "3")
                num_machines = int(input("请输入机器数量 (默认3): ") or "3")
                seed = int(input("请输入随机种子 (默认42): ") or "42")
                generate_fixed_instance(num_jobs, num_machines, seed)
            except ValueError:
                print("输入无效，请重新输入数字。")
                
        elif choice == '3':
            try:
                num_instances = int(input("请输入要生成的实例数量 (默认5): ") or "5")
                generate_batch_instances(num_instances)
            except ValueError:
                print("输入无效，请重新输入数字。")
                
        elif choice == '4':
            # 生成示例实例
            print("\n生成示例实例 (3×3, 种子42)")
            generate_fixed_instance(3, 3, 42)
            
        elif choice == '5':
            # 生成2000个随机实例
            generate_2000_instances()
            
        elif choice == '6':
            print("感谢使用OSSP数据生成器！")
            break
            
        else:
            print("无效选项，请重新选择。")


if __name__ == "__main__":
    # 运行交互式菜单
    main()