import random
import os
import json

def generate_data(num_surgeries, num_rooms, num_nurses, room_ratio=None):
    DAY_START = 8 * 60
    DAY_END = 18 * 60
    CLEAN_TIME = 10

    # 手术持续时间
    duration = [random.randint(30, 120) for _ in range(num_surgeries)]

    # 分配真实手术室（保证可行）
    real_room = [i % num_rooms for i in range(num_surgeries)]
    random.shuffle(real_room)

    room_schedule = [[] for _ in range(num_rooms)]
    start_time = [0] * num_surgeries
    end_time = [0] * num_surgeries

    for s in range(num_surgeries):
        r = real_room[s]
        if not room_schedule[r]:
            start = DAY_START
        else:
            last = room_schedule[r][-1]
            start = end_time[last] + CLEAN_TIME
        start_time[s] = start
        end_time[s] = start + duration[s]
        room_schedule[r].append(s)

    # 生成时间窗
    min_start = []
    max_end = []
    for s in range(num_surgeries):
        slack_before = random.randint(0, 60)
        slack_after = random.randint(0, 60)
        min_start.append(max(DAY_START, start_time[s] - slack_before))
        max_end.append(min(DAY_END, end_time[s] + slack_after))


    # 护士需求
    max_nurse_per_surgery = max(1, num_nurses // num_rooms)
    needed_nurses = [random.randint(1, max_nurse_per_surgery) for _ in range(num_surgeries)]

    # 护士班次
    shift_earliest_start = [DAY_START] * num_nurses
    shift_latest_end = [DAY_END] * num_nurses
    max_shift_duration = 8 * 60

    # 手术室占比控制
    if room_ratio is None:
        # 自动生成随机比例
        raw_ratios = [random.random() for _ in range(num_rooms)]
        total = sum(raw_ratios)
        room_ratio = {k+1: round(raw_ratios[k]/total, 2) for k in range(num_rooms)}
        # 调整最后一个保证总和为1
        keys = list(room_ratio.keys())
        room_ratio[keys[-1]] = 1 - sum(room_ratio[k] for k in keys[:-1])
    else:
        # 如果只设置了部分比例，剩余随机生成
        total_set = sum(room_ratio.values())
        unset_keys = [k for k in range(1, num_rooms+1) if k not in room_ratio]
        if unset_keys:
            raw_ratios = [random.random() for _ in unset_keys]
            total_raw = sum(raw_ratios)
            for i, k in enumerate(unset_keys):
                room_ratio[k] = round(raw_ratios[i] / total_raw * (1 - total_set), 2)
            # 调整最后一个保证总和为1
            keys = list(room_ratio.keys())
            room_ratio[keys[-1]] = 1 - sum(room_ratio[k] for k in keys[:-1])

    # 生成每个手术允许的手术室数量
    room_options = []
    for k, ratio in room_ratio.items():
        count = int(num_surgeries * ratio)
        room_options += [k] * count
    while len(room_options) < num_surgeries:
        room_options.append(random.choice(list(room_ratio.keys())))
    room_options = room_options[:num_surgeries]
    random.shuffle(room_options)

    # 手术室兼容矩阵
    incompatible_rooms = [[1] * num_rooms for _ in range(num_surgeries)]
    for s in range(num_surgeries):
        allowed_num = room_options[s]
        allowed_rooms = {real_room[s]}
        remaining = list(set(range(num_rooms)) - allowed_rooms)
        extra = min(allowed_num - 1, len(remaining))
        allowed_rooms.update(random.sample(remaining, extra))
        for r in allowed_rooms:
            incompatible_rooms[s][r] = 0

    # 计算实际生成的数据里每种手术室数量的占比
    room_count_distribution = {}
    for count in range(1, num_rooms + 1):
        c = sum(1 for n in room_options if n == count)
        room_count_distribution[count] = round(c / num_surgeries, 2)

    # 返回数据字典
    return {
        "num_surgeries": num_surgeries,
        "num_rooms": num_rooms,
        "num_nurses": num_nurses,
        "min_start": min_start,
        "max_end": max_end,
        "duration": duration,
        "needed_nurses": needed_nurses,
        "shift_earliest_start": shift_earliest_start,
        "shift_latest_end": shift_latest_end,
        "max_shift_duration": max_shift_duration,
        "incompatible_rooms": incompatible_rooms,
      #  "room_count_ratio": room_count_distribution,  # 实际生成的占比
        "room_ratio_config": room_ratio               # 实际使用的比例
    }

def save_to_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    NUM_SURGERIES = 20
    NUM_ROOMS = 10
    NUM_NURSES = 15
    NUM_INSTANCES = 100

    # 例：人为指定比例（只能用1个手术室的占20%，能用2个手术室的占30%），其余随机生成
    # 1: 0.2, 10: 0.3
    ratio = {NUM_ROOMS:1}
#0.5 1：0.1
#0.1 1: 0.3
    for i in range(1, NUM_INSTANCES + 1):
        data = generate_data(NUM_SURGERIES, NUM_ROOMS, NUM_NURSES, room_ratio=ratio)
        filename = f"data1/data_{i:03d}.json"
        save_to_json(data, filename)
        print(f"Generated: {filename}")