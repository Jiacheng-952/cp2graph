import random
import os
import json

def generate_two_week_nurse_data(num_workers, senior_ratio, trainee_ratio):
    """
    生成两周排班数据（14天），周末班次需求高于周中
    每位护士都有明确职位: Senior / Regular / Trainee
    保证每天需求 <= 当天可用护士总人数
    保证每班至少有一名高级护士可上班
    """
    workers = [f"Nurse{i+1}" for i in range(num_workers)]

    # 分配高级护士
    num_senior = max(1, int(num_workers * senior_ratio))
    senior_nurses = random.sample(workers, num_senior)

    # 分配实习护士 (Trainee)
    remaining_workers = [w for w in workers if w not in senior_nurses]
    num_trainee = max(0, int(num_workers * trainee_ratio))
    trainee_nurses = random.sample(remaining_workers, min(num_trainee, len(remaining_workers)))

    # 剩下的都是普通护士
    regular_nurses = [w for w in workers if w not in senior_nurses and w not in trainee_nurses]

    # 职位字典
    positions = {w: "Senior" for w in senior_nurses}
    positions.update({w: "Trainee" for w in trainee_nurses})
    positions.update({w: "Regular" for w in regular_nurses})

    # 班次名称
    day_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    shifts = [f"{d}{i+1 + week*7}" for week in range(2) for i,d in enumerate(day_names)]

    # 可用班次 Availability
    availability = {}
    for w in workers:
        lower = max(7, num_workers // 2)
        lower = min(lower, len(shifts))
        num_shifts_available = random.randint(lower, len(shifts))
        availability[w] = sorted(random.sample(shifts, num_shifts_available))
        
    # 班次需求：确保 <= 当天可用护士总数，并保证至少有一名高级护士
    shift_requirements = {}
    for s in shifts:
        available_today = [w for w in workers if s in availability[w]]
        available_senior = [w for w in senior_nurses if s in availability[w]]

        if len(available_senior) == 0 and len(available_today) > 0:
            chosen = random.choice(available_today)
            senior_nurses.append(chosen)
            positions[chosen] = "Senior"
            available_senior = [chosen]

        total_avail = len(available_today)
        if total_avail == 0:
            req = 0
        else:
            day = s[:3]
            if day in ["Sat","Sun"]:
                min_req = min(3, total_avail)
                max_req = total_avail
            else:
                min_req = min(2, total_avail)
                max_req = total_avail
            req = random.randint(min_req, max_req)
        shift_requirements[s] = req

    # 工资：职位越高越高
    pay = {}
    for w in workers:
        if positions[w] == "Senior":
            pay[w] = random.randint(14, 16)
        elif positions[w] == "Regular":
            pay[w] = random.randint(10, 13)
        else:
            pay[w] = random.randint(8, 10)

    return {
        "Shifts": shifts,
        "shiftRequirements": shift_requirements,
        "Workers": workers,
        "SeniorNurses": senior_nurses,
        "Availability": availability,
        "pay": pay,
        "Positions": positions
    }

# 创建输出文件夹
output_dir = "data_large"
os.makedirs(output_dir, exist_ok=True)

# 生成 500 个 JSON 文件
for idx in range(1, 501):
    data = generate_two_week_nurse_data(num_workers=10, senior_ratio=0.1, trainee_ratio=0.2)#可以调节高级护士所占比例
    # data_small中的数据高级护士占比0.5，即senior_ratio=0.5
    # data_medium中的数据高级护士占比0.3，即senior_ratio=0.3
    # data_large中的数据高级护士占比0.1，即senior_ratio=0.1
    file_path = os.path.join(output_dir, f"data_{idx}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

print("500 个随机两周护士排班 JSON 文件已生成在文件夹 data中")