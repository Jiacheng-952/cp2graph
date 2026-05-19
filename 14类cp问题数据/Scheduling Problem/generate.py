from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


@dataclass
class GenerationConfig:
    instance_id: int
    seed: int
    n_restaurants: int
    n_employees_range: tuple[int, int]
    n_shifts: int
    n_skills: int
    demand_range: tuple[int, int]
    skill_probability: float
    availability_probability: float
    preference_range: tuple[int, int]
    unfulfilled_cost: int


@dataclass
class ParameterGroup:
    count: int
    seed: int
    n_restaurants: int
    n_employees_range: tuple[int, int]
    n_shifts: int
    n_skills: int
    demand_range: tuple[int, int]
    skill_probability: float
    availability_probability: float
    preference_range: tuple[int, int]
    unfulfilled_cost: int


def _to_list_range(value: tuple[int, int]) -> list[int]:
    return [value[0], value[1]]


def build_instance_data(config: GenerationConfig, generated_time: str) -> dict:
    rng = random.Random(config.seed)
    n_employees = rng.randint(*config.n_employees_range)

    restaurants = [f"Rest_{i + 1}" for i in range(config.n_restaurants)]
    employees = [f"Emp_{i + 1}" for i in range(n_employees)]
    shifts = [f"Shift_{i + 1}" for i in range(config.n_shifts)]
    skills = [f"Skill_{i + 1}" for i in range(config.n_skills)]

    demand = []
    for restaurant in restaurants:
        for shift in shifts:
            for skill in skills:
                demand.append(
                    {
                        "restaurant": restaurant,
                        "shift": shift,
                        "skill": skill,
                        "required": rng.randint(*config.demand_range),
                    }
                )

    employee_skills = []
    for employee in employees:
        for skill in skills:
            employee_skills.append(
                {
                    "employee": employee,
                    "skill": skill,
                    "has_skill": 1 if rng.random() < config.skill_probability else 0,
                }
            )

    employee_availability = []
    for employee in employees:
        for shift in shifts:
            employee_availability.append(
                {
                    "employee": employee,
                    "shift": shift,
                    "available": 1 if rng.random() < config.availability_probability else 0,
                }
            )

    preference_costs = []
    for employee in employees:
        for skill in skills:
            preference_costs.append(
                {
                    "employee": employee,
                    "skill": skill,
                    "cost": rng.randint(*config.preference_range),
                }
            )

    return {
        "metadata": {
            "instance_id": config.instance_id,
            "generated_time": generated_time,
            "n_restaurants": config.n_restaurants,
            "n_employees": n_employees,
            "n_shifts": config.n_shifts,
            "n_skills": config.n_skills,
            "unfulfilled_cost": config.unfulfilled_cost,
            "parameters": {
                "demand_range": _to_list_range(config.demand_range),
                "skill_probability": config.skill_probability,
                "availability_probability": config.availability_probability,
                "preference_range": _to_list_range(config.preference_range),
            },
        },
        "sets": {
            "restaurants": restaurants,
            "employees": employees,
            "shifts": shifts,
            "skills": skills,
        },
        "demand": demand,
        "employee_skills": employee_skills,
        "employee_availability": employee_availability,
        "preference_costs": preference_costs,
    }


def default_parameter_sets() -> list[ParameterGroup]:
    return [
        ParameterGroup(1, 42, 3, (10, 15), 2, 2, (1, 4), 0.70, 0.80, (1, 5), 100),
        ParameterGroup(1, 43, 3, (12, 18), 2, 2, (1, 5), 0.75, 0.85, (1, 6), 100),
        ParameterGroup(1, 44, 4, (12, 20), 2, 2, (1, 4), 0.70, 0.75, (1, 5), 120),
        ParameterGroup(1, 45, 4, (15, 22), 3, 2, (1, 4), 0.72, 0.80, (1, 6), 120),
        ParameterGroup(1, 46, 5, (16, 24), 3, 2, (1, 5), 0.78, 0.82, (1, 7), 130),
        ParameterGroup(1, 47, 3, (10, 16), 4, 2, (1, 4), 0.68, 0.78, (1, 5), 110),
        ParameterGroup(1, 48, 4, (14, 20), 4, 2, (1, 5), 0.74, 0.80, (2, 6), 130),
        ParameterGroup(1, 49, 5, (18, 26), 2, 2, (2, 5), 0.80, 0.85, (1, 6), 140),
        ParameterGroup(1, 50, 5, (18, 28), 3, 2, (1, 5), 0.76, 0.88, (1, 7), 150),
        ParameterGroup(1, 51, 6, (20, 30), 3, 2, (2, 6), 0.82, 0.90, (1, 8), 160),
    ]


def expand_parameter_groups(parameter_groups: list[ParameterGroup], start_instance_id: int = 1) -> list[GenerationConfig]:
    expanded = []
    current_instance_id = start_instance_id
    for group in parameter_groups:
        for i in range(group.count):
            expanded.append(
                GenerationConfig(
                    instance_id=current_instance_id,
                    seed=group.seed + i,
                    n_restaurants=group.n_restaurants,
                    n_employees_range=group.n_employees_range,
                    n_shifts=group.n_shifts,
                    n_skills=group.n_skills,
                    demand_range=group.demand_range,
                    skill_probability=group.skill_probability,
                    availability_probability=group.availability_probability,
                    preference_range=group.preference_range,
                    unfulfilled_cost=group.unfulfilled_cost,
                )
            )
            current_instance_id += 1
    return expanded


def generate_dataset(
    parameter_groups: list[ParameterGroup],
    output_dir: Optional[Union[str, Path]] = None,
    start_instance_id: int = 1,
) -> None:
    parameter_sets = expand_parameter_groups(parameter_groups, start_instance_id=start_instance_id)
    base_dir = Path(__file__).resolve().parent
    target_dir = Path(output_dir) if output_dir else base_dir / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    index_items = []

    for config in parameter_sets:
        data = build_instance_data(config, generated_time)
        filename = f"employee_assignment_instance_{config.instance_id:03d}.json"
        output_path = target_dir / filename
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        file_size_kb = round(output_path.stat().st_size / 1024, 2)
        index_items.append(
            {
                "id": config.instance_id,
                "filename": filename,
                "size_kb": file_size_kb,
                "path": (Path("data") / filename).as_posix(),
                "parameters": asdict(config),
            }
        )

    index_data = {
        "generated_time": generated_time,
        "total_instances": len(parameter_sets),
        "instances": sorted(index_items, key=lambda item: item["id"]),
    }
    index_path = target_dir / "index.json"
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {len(parameter_sets)} 个实例到: {target_dir}")


def solve_employee_assignment(parameter_groups: Optional[list[ParameterGroup]] = None, start_instance_id: int = 1) -> None:
    active_groups = parameter_groups or default_parameter_sets()
    generate_dataset(active_groups, start_instance_id=start_instance_id)


if __name__ == "__main__":
    solve_employee_assignment()
'''
你可以在 Python 里直接传参运行：
from generate import solve_employee_assignment, ParameterGroup

solve_employee_assignment(
    parameter_groups=[
        ParameterGroup(2, 100, 3, (10, 12), 2, 2, (1, 3), 0.7, 0.8, (1, 5), 100),
        ParameterGroup(3, 200, 4, (12, 14), 3, 2, (1, 4), 0.75, 0.85, (1, 6), 120),
    ],
    start_instance_id=201
)
这里会生成 2+3=5 个文件，实例编号从 201 开始（201~205）
'''