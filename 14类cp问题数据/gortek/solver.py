from __future__ import annotations

from abc import ABC, abstractmethod
from docplex.cp.solver.cpo_callback import CpoCallback
from fastapi import FastAPI, BackgroundTasks, HTTPException
from operator import methodcaller
from pydantic import BaseModel
from threading import Lock
from typing import Dict, List, Optional
import copy
import datetime
import docplex.cp.model as cp
import json
import logging
import logging.config
import math
import os
import re
import requests
import sys
import time
import uvicorn
import argparse # Added for command-line argument parsing


# Default logging configuration if logging_config.json is not found
DEFAULT_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True
        },
        'AS_main_server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
        'AS_task_record': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
        'sub_server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
        'is_optimal': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        }
    }
}


# === Variables from public/__init__.py ===
main_server_port = {
    'as': 8001,
    'ap': 8010
}
response_url = {
    'as': 'http://ocean.pmf.local/GtkPMF.MoldMom.Aps/api/solution/receive',
    'ap': 'http://ocean.pmf.local/GtkPMF.MoldMom.Aps/api/solution/receiveap'
}

# === Variables from AS/__init__.py ===
as_main_server_port = main_server_port['as']
datetime_fmt = '%Y-%m-%d %H:%M:%S'
as_response_url = 'http://10.10.28.166:7000/GtkPMF.MoldMom.Aps/api/solution/receive'
DEFAULT_CIRCULATION_TIME = 120
TIMEOUT_DEFAULT_LEFT_TIME = 1
DEFAULT_WORKERS = 2
DEFAULT_SOLVE_TIME_LIMIT = 1000
DEFAULT_REFINE_CONFLICT_TIME_LIMIT = 60


# ==========================================
# File: public/exceptions.py
# ==========================================
class SupportedException(Exception):
    pass


class ModelingException(SupportedException):
    pass


class ConfigurationException(SupportedException):
    """ 缺少相关配置导致的异常 """
    pass


class InvalidDataException(SupportedException):
    """ 由于输入数据不合理引发的异常 """
    pass


class NoObjectiveException(SupportedException):
    pass


class PlanningException(SupportedException):
    pass


class NotSupportException(SupportedException):
    pass


class AbortedException(SupportedException):
    pass


class ConflictException(SupportedException):
    pass


class NoSolutionException(SupportedException):
    pass


class FAException(SupportedException):
    pass


class UnknownException(Exception):
    pass


# ==========================================
# File: public/conflict.py
# ==========================================


class Conflict:
    def __init__(self,
                 constraint):
        self.constraint = constraint
        self.constraint_name = self.constraint.name

    def __str__(self):
        return self.constraint_name

    @classmethod
    def new(cls, constraint):
        if constraint.name.startswith('Parallel constraint'):
            return DeviceResourceConflict(constraint)
        else:
            return cls(constraint)


class DeviceResourceConflict(Conflict):
    def __init__(self, constraint):
        super().__init__(constraint)

        match = re.search(r"'(.*?)'", self.constraint_name)
        self.device_type = match.group(1)

    def __str__(self):
        return f"{self.device_type} 类设备可用资源无法满足当前任务量!"


# ==========================================
# File: public/request_type.py
# ==========================================


class PlanningRequest(BaseModel):
    """ base data class of planning request """
    token: str
    input_data: dict


# ==========================================
# File: public/device_loader.py
# ==========================================



class BaseDeviceLoader:
    def __init__(self,
                 base_time: datetime.datetime,
                 max_time: datetime.datetime,
                 data: dict,
                 *args,
                 **kwargs):
        self.base_time = base_time
        self.max_time = max_time

        self.devices = dict()  # 按工序区分设备
        self.devices_record = dict()  # 直接按id记录设备，避免因为多功能设备导致同一个设备id产生多个实例

        self._loading_devices(data)

    def _loading_devices(self, data: dict):
        raise NotImplemented

    def __getitem__(self, item):
        return self.devices[item]

    def get_device_by_id(self, device_id: str):
        return self.devices_record[device_id]

    @property
    def devices_cnt(self) -> int:
        return len(self.devices_record)


class BaseDevice:
    def __init__(self,
                 device_id: str,
                 stage_code: List[str],
                 base_time: datetime.datetime,
                 max_time: datetime.datetime,
                 daily_rest_time: List[List[str]],
                 rest_days: List[List[str]],
                 can_overlap: bool,
                 *args,
                 **kwargs):
        self.device_id = device_id
        self.stage_code = stage_code
        self.base_time = base_time
        self.max_time = max_time
        self.can_overlap = can_overlap

        self.intensity = cp.CpoStepFunction()
        self.intensity.set_value(0, self.real_to_relative_time(self.max_time), 100)

        if daily_rest_time:
            self.set_daily_rest_time(daily_rest_time)

        if rest_days:
            self.set_rest_days(rest_days)

    def set_daily_rest_time(self, daily_rest_time: List[List[str]]) -> None:
        # 根据每日休息时间，生成从基准时间到最大时间的每天休息时段
        date = self.base_time.date()
        while date <= self.max_time.date():
            for (start_time_str, end_time_str) in daily_rest_time:
                start_time = datetime.datetime.strptime(start_time_str, '%H:%M:%S').time()
                end_time = datetime.datetime.strptime(end_time_str, '%H:%M:%S').time()
                start_datetime = self.datetime_combine(date, start_time)
                if start_time < end_time:
                    end_datetime = self.datetime_combine(date, end_time)
                else:
                    end_datetime = self.datetime_combine(date + datetime.timedelta(days=1), end_time)
                self.set_rest_period(start_datetime, end_datetime)
            date += datetime.timedelta(days=1)

    def set_rest_days(self, rest_days: List[List[str]]) -> None:
        for (start_datetime_str, end_datetime_str) in rest_days:
            start_datetime = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')
            end_datetime = datetime.datetime.strptime(end_datetime_str, '%Y-%m-%d %H:%M:%S')
            self.set_rest_period(start_datetime, end_datetime)

    def set_rest_period(self, start_datetime: datetime.datetime, end_datetime: datetime.datetime) -> None:
        """ 根据生成的休息时段，将对应时段的设备效率设置为0 """
        if start_datetime > self.base_time or end_datetime < self.max_time:
            relative_start_time = self.real_to_relative_time(max(start_datetime, self.base_time))
            relative_end_time = self.real_to_relative_time(min(end_datetime, self.max_time))
            self.intensity.set_value(relative_start_time, relative_end_time, 0)

    def real_to_relative_time(self, real_time: datetime.datetime) -> int:
        datetime_delta = real_time - self.base_time
        return datetime_delta.days * 24 * 60 + datetime_delta.seconds // 60

    @staticmethod
    def datetime_combine(date_: datetime.date, time_: datetime.time) -> datetime.datetime:
        """ combine datetime.date with datetime.time to datetime.datetime ( while considering 24:00 to 00:00 +1 )"""
        # if time_ == datetime.time(0):
        #     return datetime.datetime(date_.year, date_.month, date_.day, 0) + datetime.timedelta(days=1)
        return datetime.datetime.combine(date_, time_)

    @property
    def working_intervals(self) -> List[List[int]]:
        """ 获得设备的开工时段 """
        working_intervals = []
        start = None
        for (p, v) in self.intensity.get_step_list():
            if start is not None and v == 0:
                working_intervals.append([start, p])
                start = None
            elif start is None and v == 100:
                start = p
        return working_intervals

    def get_daily_working_vars(self):
        overlap_vars = self.get_overlap_vars()
        if not overlap_vars:
            return None
        else:
            working_vars = copy.deepcopy(overlap_vars)
            for var in working_vars:
                var.set_optional()
            return working_vars

    def get_overlap_vars(self):
        if self.stage_code != ['OUTSOURCING']:
            daily_working_vars = []
            relative_max_time = self.real_to_relative_time(self.max_time)
            start = 0
            if self.base_time.time() < datetime.time(20):
                end = self.real_to_relative_time(
                    datetime.datetime.combine(self.base_time.date(),
                                              datetime.time(20))
                )
            else:
                end = self.real_to_relative_time(
                    datetime.datetime.combine(self.base_time.date() + datetime.timedelta(days=1),
                                              datetime.time(20))
                )
            while start < relative_max_time:
                if end >= relative_max_time:
                    end = relative_max_time
                    daily_working_vars.append(cp.interval_var(start=start, end=end))
                    break
                else:
                    daily_working_vars.append(cp.interval_var(start=start, end=end))
                    start, end = end, end + 60 * 24
            return daily_working_vars
        else:
            return None

    def __hash__(self):
        return hash(self.device_id)

    def __eq__(self, other):
        return self.device_id == other.device_id

    def __repr__(self):
        return self.device_id


# ==========================================
# File: public/model.py
# ==========================================




class BaseModelWrapper:
    def __init__(self, token: str, data: dict):
        self.token = token
        self.data = data

        self.model = None

        # log
        self.logger = logging.getLogger(token)

    def _main_solve(self) -> cp.CpoSolveResult:
        raise NotImplementedError

    def solve(self, *args, **kwargs) -> dict:
        sol = self._main_solve()

        if sol is None or (sol.solution is None and sol.fail_status == 'SearchStoppedByAbort'):
            self.logger.info('中断时无解!')
            return {}

        if sol.solve_status == 'Infeasible':
            # 模型infeasible, 尝试寻找冲突点
            self.logger.warning(f'[{self.token}] Conflict!')
            conflicts = self.model.refine_conflict()
            conflicts_info = ';'.join([str(mc) for mc in conflicts.member_constraints])
            self.logger.warning(f'No solution: 模型存在冲突！{conflicts_info}')
            raise ConflictException(conflicts_info)
        elif sol.solution is None and sol.fail_status == 'SearchStoppedByLimit':
            raise NoSolutionException('最大求解时间耗尽，无解！')
        elif sol.solution is not None:
            return self.model.solution_dict
        else:
            raise RuntimeError('未知的解的情形！')

    def abort_solving(self) -> bool:
        self.logger.info("手动中断求解")
        return self.model.abort_solving()

    @property
    def solver(self):
        return self.model.solver


# ==========================================
# File: public/sub_server.py
# ==========================================




class SubServer:
    """ 算法服务器端口, FastAPI的包装实现 """

    def __init__(self,
                 planning_type: str,
                 port: int,
                 main_port: int = None):
        self.planning_type = planning_type  # 可选: ['as', 'ap']

        self.port = port
        self.main_server_port = main_port or main_server_port[planning_type]  # 对应主服务器监听端口

        self.app = FastAPI()

        self.ongoing_model: Optional[BaseModelWrapper] = None
        self.ongoing_model_lock = Lock()

        # 'sub_server_{}.log' 相关配置
        with open('logging_config.json', 'r') as f:
            logging_config = json.load(f)
            logging.config.dictConfig(logging_config)
        self.task_logger = logging.getLogger(f'{planning_type}_task_record')
        self.logger = self.get_server_logger()

        # API
        @self.app.on_event('startup')
        def register():
            """ 启动时注册到主服务器 """
            try:
                resp = requests.get(f'http://localhost:{self.main_server_port}/register/{self.port}')
            except requests.exceptions.ConnectionError:
                self.logger.warning('Main server offline, registration failed.')
                sys.exit()
            if resp.status_code == 201:
                self.logger.info('Port registered.')
            else:
                self.logger.info('Port registration failed.')
                sys.exit()

        @self.app.on_event('shutdown')
        def shutdown():
            """ 服务器关闭时通知主服务器 """
            resp = requests.get(f'http://localhost:{self.main_server_port}/close/{self.port}')
            if resp.status_code == 201:
                self.logger.info('Port shut down.')
            else:
                self.logger.warning('Port shut down, but close on main server failed!')
                sys.exit()

        @self.app.post('/planning/', status_code=201)
        def planning(data: PlanningRequest, background_task: BackgroundTasks):
            """ 排产 """
            background_task.add_task(self.background_planning, data.token, data.input_data)  # 后台执行任务
            return {
                'status': 200,
                'token': data.token
            }

        @self.app.get('/stop/{token}')
        def stop(token: str):
            """ 手动停止正在进行中的排产 """
            with self.ongoing_model_lock:
                m: BaseModelWrapper = self.ongoing_model
                if m.token == token:
                    res = m.abort_solving()
                    if res:
                        self.logger.info(f'[{token}] Aborted!')
                        return
                    else:
                        error_info = 'Abortion failed!'
                else:
                    error_info = f'Attempting to abort task-{token}, but task-{m.token} is planning on this port.'

                self.logger.warning(error_info)
                raise HTTPException(status_code=500, detail=error_info)

        self.run()

    def get_server_logger(self):
        sub_server_logger = logging.getLogger(f'sub_server_{self.port}')
        file_handler = logging.FileHandler(f'logs/{self.planning_type}/sub_server_{self.port}.log')
        formatter = logging.Formatter("%(asctime)s - %(levelname)-8s : %(message)s")
        file_handler.setFormatter(formatter)
        sub_server_logger.addHandler(file_handler)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        sub_server_logger.addHandler(console_handler)
        sub_server_logger.setLevel(logging.INFO)
        return sub_server_logger

    def background_planning(self, token, data):
        """ 核心排产入口 """
        self.logger.info(f'[{token}] Planning request received.')

        # '{token}.log' 日志配置
        planning_logger = logging.getLogger(token)
        planning_logger.propagate = False
        planning_logger.setLevel(level=logging.DEBUG)

        if not planning_logger.hasHandlers():
            file_name = token[:12] + "-" + token[12:]
            file_path = f'logs/{self.planning_type}/solving_logs/{data["args"]["factory_code"]}/'
            if not os.path.exists(file_path):
                os.makedirs(file_path)
                print(f'Create path \'{file_path}\'.')
            log_file_handler = logging.FileHandler(f'{file_path}{file_name}.log')
            log_file_handler.setLevel(level=logging.DEBUG)
            planning_logger.addHandler(log_file_handler)

        if 'test_mode' in data['args'].keys() and data['args']['test_mode'] == 1:
            test_mode = True
        else:
            test_mode = False

        solution_dict = {
            'token': token,
            'state': None,
            'solutions': {}
        }

        try:
            self.planning(token, data, solution_dict)

        except SupportedException as e:
            # 已知的部分异常，返回异常信息
            if isinstance(e, ConflictException):
                solution_dict['state'] = '错误: ' + '模型存在冲突！' + e.args[0]
            else:
                solution_dict['state'] = '错误: ' + e.args[0]
            self.logger.warning(f'[{token}] {solution_dict["state"]}')
        except Exception as e:
            # 预期外的异常，记录具体异常堆栈
            solution_dict['state'] = '未知错误: ' + e.args[0]
            self.logger.exception(e)
        finally:
            with self.ongoing_model_lock:
                self.ongoing_model = None

            if solution_dict['state'] == 'OK':
                self.task_logger.info(f'[{token}] Model solved.')
            else:
                self.task_logger.info(f'[{token}] {solution_dict["state"]}')

            if not test_mode:
                try:
                    # 回传结果给一体化服务器
                    resp = requests.post(
                        url=response_url[self.planning_type],
                        data=json.dumps(solution_dict),
                        headers={
                            'Content-Type': 'application/json;charset=UTF-8'
                        }
                    )
                    self.logger.info(f'[{token}] Result successfully sent with status code <{resp.status_code}>.')
                except requests.exceptions.ConnectionError:
                    self.logger.warning(f'[{token}] Failed to send result due to server connection.')
                except Exception as e:
                    self.logger.warning(f'[{token}] Failed to send result: {str(e)}')
            else:
                self.logger.info(f'[{token}] Test mode finished.')

            requests.get(url=f'http://localhost:{self.main_server_port}/release/{self.port}')

    def planning(self, token, data, solution_dict):
        # 具体由AS/AP子类继承实现
        raise NotImplementedError

    def save_solution(self, token: str, factory_code: str, solution_dict: dict):
        file_name = token[:12] + "-" + token[12:]
        solution_path = f'solutions/{self.planning_type}/{factory_code}/'
        if not os.path.exists(solution_path):
            os.makedirs(solution_path)
            print(f'Create path \'{solution_path}\'.')
        solution_file_path = solution_path + f'solution_{file_name}.json'
        with open(solution_file_path, 'w') as solution_file:
            solution_file.write(json.dumps(solution_dict['solutions']))
            self.logger.info(f'[{token}] Solution saved to \'{solution_file_path}\' .')

    def run(self):
        uvicorn.run(self.app, host='localhost', port=self.port)


# ==========================================
# File: public/main_server.py
# ==========================================




class SubPortStatus:
    """ 用来记录所有的算法接口、可用状态、正在运行的任务token """

    def __init__(self, port: int):
        self.port = port
        self.is_valid = False
        self.ongoing_planning_token = None

    def register(self):
        self.is_valid = True

    def close(self):
        self.is_valid = False

    def allocate_task(self, token: str):
        self.is_valid = False
        self.ongoing_planning_token = token

    def release(self):
        self.is_valid = True
        self.ongoing_planning_token = None


class MainServer:
    """ 主服务器端口, FastAPI的包装实现 """

    def __init__(self,
                 planning_type: str,
                 port: int = None):
        self.planning_type = planning_type  # 可选: ['as', 'ap']

        self.app = FastAPI()

        self.port = port or main_server_port[planning_type]  # 主服务器监听端口

        self.port_status: Dict[int, SubPortStatus] = dict()  # 记录算法服务器端口状态
        self.port_status_lock = Lock()
        self.task_queue = []  # 记录无法被及时分配的任务

        # 'main_server.log' 相关配置
        log_path = f'logs/{planning_type}/'
        if not os.path.exists(log_path):
            os.makedirs(log_path)
            print(f'create path \'{log_path}\'.')
        with open('logging_config.json', 'r') as f:
            logging_config = json.load(f)
        logging.config.dictConfig(logging_config)
        self.logger = logging.getLogger(f'{planning_type}_main_server')

        # API
        @self.app.on_event('startup')
        def startup():
            """ 主服务器启动 """
            self.logger.info('Main server start up.')

        @self.app.on_event('shutdown')
        def shutdown():
            """ 主服务器关闭 """
            self.logger.info('Main server shut down.')
            if self.task_queue:
                # 记录暂存的任务token
                as_left_tasks = list(map(lambda x: str(x[0]), self.task_queue))
                self.logger.warning(f'Tasks left in queue: {", ".join(as_left_tasks)}')

        @self.app.get('/register/{port_number}', status_code=201)
        def register(port_number: int):
            """ 算法服务器注册到主服务器 """
            with self.port_status_lock:
                if port_number not in self.port_status.keys():
                    self.port_status[port_number] = SubPortStatus(port_number)
                self.port_status[port_number].register()
            self.logger.info(f'Port {port_number} registered.')
            return {'result': 'success'}

        @self.app.get('/close/{port_number}', status_code=201)
        def close(port_number: int):
            """ 算法服务器离线 """
            with self.port_status_lock:
                if port_number not in self.port_status.keys():
                    self.logger.warning('Attempting to close a non-existent port.')
                else:
                    self.port_status[port_number].close()
                    self.logger.info(f'Port {port_number} closed.')

            return {'result': 'success'}

        @self.app.post('/planning/', status_code=201)
        def planning(original_data: PlanningRequest):
            """ 排产请求 """
            token = original_data.token
            self.logger.info(f'[{token}] Received!')
            with self.port_status_lock:
                self.allocate_task(original_data)

            return {
                'status': 200,
                'token': token
            }

        @self.app.get('/release/{sub_port}')
        def release(sub_port: int):
            """ 算法服务器资源释放（完成/异常/其他原因） """
            with self.port_status_lock:
                self.port_status[sub_port].release()
                self.logger.info(f'Port {sub_port} released.')
                if self.task_queue:
                    # 端口释放后，检查任务队列中有无等待中的任务，并自动分配
                    token, original_data = self.task_queue.pop(0)
                    self.allocate_task(original_data)

        @self.app.get('/stop/{token}')
        def stop(token: str):
            """ 手动停止排产任务 """
            with self.port_status_lock:
                for sub_port in self.port_status.values():
                    # 查找在哪个算法服务器上进行排产
                    if sub_port.ongoing_planning_token == token:
                        resp = requests.get(f'http://localhost:{sub_port.port}/stop/{token}')
                        if resp.status_code == 200:
                            self.logger.info(f'[{token}] Task aborted on port {sub_port.port}.')
                            return "中断成功"
                        else:
                            error_info = f"[{token}] 中断失败."
                            break
                else:
                    for waiting_token, waiting_data in self.task_queue:
                        # 如果在算法服务器上未查询到，则查找任务队列
                        if waiting_token == token:
                            self.logger.info(f"[{token}] Received abort request, but task hasn't started yet. ")
                            return {"中断成功"}

                    else:
                        # 如果仍然没找到，则返回错误
                        error_info = f'[{token}] 中断失败: 未找到该token任务!'

                self.logger.warning(error_info)
                raise HTTPException(status_code=500, detail=error_info)

        @self.app.get('/trigger/')
        def trigger():
            """ 手动触发任务队列 """
            if self.task_queue:
                token, original_data = self.task_queue.pop(0)
                with self.port_status_lock:
                    self.allocate_task(original_data)

        self.run()

    def allocate_task(self, original_data: PlanningRequest):
        """ 查找可用算法服务器并分配排产任务 """
        token = original_data.token
        input_data = original_data.input_data
        file_name = token[:12] + "-" + token[12:]
        factory_code = input_data['args']['factory_code']

        if 'test_mode' in input_data['args'].keys() and input_data['args']['test_mode'] == 1:
            test_mode = True
        else:
            test_mode = False

        if not test_mode:
            # 0为测试模式，不保存数据
            file_path = f'inputs/{self.planning_type}/{factory_code}/'
            if not os.path.exists(file_path):
                os.makedirs(file_path)
                print(f'create path \'{file_path}\'.')

            input_file_path = file_path + f'{file_name}.json'
            with open(input_file_path, 'w') as input_file:
                input_file.write(json.dumps(input_data))
                self.logger.info(f'[{token}] Input data saved to \'{input_file_path}\' .')

        for port_number, port in self.port_status.items():
            # 查找有没有空闲的算法服务器可用
            if port.is_valid:
                response = requests.post(url=f'http://localhost:{port_number}/planning',
                                         data=json.dumps({'token': token,
                                                          'input_data': input_data}),
                                         headers={'Content-Type': 'application/json;charset=UTF-8'})
                if response.status_code == 201:
                    # 服务器成功接收
                    self.logger.info(f'[{token}] Successfully allocate to port {port_number}.')
                    port.allocate_task(token)
                    break

                else:
                    # 分配失败，检查下一个服务器
                    continue
        else:
            # 如果没有服务器可用，暂存入任务队列
            self.task_queue.append((token, original_data))
            self.logger.info(f'[{token}] No valid port. Saved to task queue.')

    def run(self):
        """ 运行主服务器 """
        uvicorn.run(self.app, host='0.0.0.0', port=self.port)


# ==========================================
# File: AS/callbacks.py
# ==========================================



class MonitorCallback(CpoCallback):
    """ 记录求解过程，同时按需筛选中间结果 """

    def __init__(self,
                 token: str,
                 obj_name_list: List[str],
                 select_result: bool = True,
                 early_stop: bool = False):
        self.obj_name_list = obj_name_list
        self.kpi_name_list: Optional[List[str]] = None
        self.select_result = select_result  # 是否在过程中筛选结果（不保存较差的中间结果）
        self.early_stop = early_stop  # 知否支持早停
        self.logger = logging.getLogger(token)

        self.previous_solution = None
        self.last_best_solution = None

        self.max_memory_usage = 0

    def invoke(self, solver, event, sres):
        if event == "StartSolve":
            stats = solver.get_model().get_statistics()
            self.kpi_name_list = solver.get_model().get_kpis().keys()

            if ('priority_process_delay_time' not in self.obj_name_list
                    and 'priority_process_delay_time' not in self.kpi_name_list):
                # 如果没有优先工艺，则无法对求解中的结果进行二次筛选
                self.select_result = False

            # 打印日志头
            self.logger.info(f"Variables: {stats.nb_interval_vars}   Constraints: {stats.nb_constraints}")
            self.logger.info("=======================================================")
            self.logger.info(''.center(3) +
                             'time'.center(10) +
                             '|'.join([self.convert_name(obj_name).center(20) for obj_name in self.obj_name_list]) +
                             '|'.join([self.convert_name(kpi_name).center(20) for kpi_name in self.kpi_name_list]))

        elif event == "Solution":
            bounds = sres.get_objective_bounds()
            if (not self.previous_solution
                    or bounds != self.previous_solution.get_objective_bounds()):
                # bounds更新
                logging_info = f'[new bounds]'.center(13)
                logging_info += '|'.join([f'{bound}'.center(20) for bound in bounds])
                self.logger.info(logging_info)

            obj_val = sres.get_objective_values()
            obj_gaps = sres.get_objective_gaps()
            kpis = sres.get_kpis()

            solver_info = sres.get_solver_infos()
            solve_time = solver_info.get_solve_time()
            self.max_memory_usage = max(self.max_memory_usage, solver_info.get_memory_usage())

            is_better_solution = self.is_new_solution_better(obj_val, kpis)
            if is_better_solution:
                # 更新结果
                self.last_best_solution = sres

            logging_info = ('*' if is_better_solution else '').center(3)
            logging_info += f'{solve_time:.3f}s'.rjust(10)
            logging_info += '|'.join([f'{obj_val[i]}({obj_gaps[i] * 100:.2f}%)'.center(20)
                                      for i in range(len(obj_val))])
            logging_info += '|'.join([str(kpi).center(20) for kpi in kpis.values()])
            self.logger.info(logging_info)

            if self.early_stop:
                # 早停功能
                real_gaps = [self.get_real_gap(obj_val[i], bounds[i])
                             for i in range(len(obj_val))]
                if (all(gap <= 0.005 for gap in real_gaps[:-1])
                        and (real_gaps[-1] <= 0.05)):
                    self.logger.info('Early stopped!')
                    solver.abort_search()

            self.previous_solution = sres

        elif event == 'EndSolve':
            self.logger.info(f'Max memory usage: {self.max_memory_usage / (1024 * 1024 * 1024):.2f} GB.')

    @staticmethod
    def convert_name(original_name: str) -> str:
        _map = {"critical_process_delay_time": "critDelayTime",
                "priority_business_delay_number": "prioDelayCnt",
                "priority_process_delay_time": "prioDelayTime",
                "all_business_delay_number": "allDelayCnt",
                "normal_process_delay_time": "norDelayTime",
                "advanced_time": "advancedTime"}
        return _map[original_name]

    @staticmethod
    def get_real_gap(obj, bound):
        """ 计算实际gap(该功能的作用是: 当前面的objective没有到最优时，cplex不会计算后续objectives的gaps，需要手动计算) """
        return abs(obj - bound) / max(0.0000000001, abs(obj))

    def get_obj_value(self, objectives, kpis, key):
        if key in self.obj_name_list:
            return objectives[self.obj_name_list.index(key)]
        elif key in self.kpi_name_list:
            return kpis[key]
        else:
            raise RuntimeError(f"No objective named \'{key}\'")

    def is_new_solution_better(self, new_obj_val, new_kpi) -> bool:
        if self.last_best_solution is None or not self.select_result:
            return True

        last_best_obj_val = self.last_best_solution.get_objective_values()
        last_best_kpis = self.last_best_solution.get_kpis()

        last_best_priority_delay_time = self.get_obj_value(last_best_obj_val, last_best_kpis,
                                                           "priority_process_delay_time")
        new_priority_delay_time = self.get_obj_value(new_obj_val,
                                                     new_kpi,
                                                     "priority_process_delay_time")

        try:
            if (last_best_priority_delay_time
                    and new_priority_delay_time >= (last_best_priority_delay_time * 0.95)):
                last_best_normal_delay_time = self.get_obj_value(last_best_obj_val,
                                                                 last_best_kpis,
                                                                 "normal_process_delay_time")
                new_normal_delay_time = self.get_obj_value(new_obj_val,
                                                           new_kpi,
                                                           "normal_process_delay_time")
                if (last_best_normal_delay_time
                        and new_normal_delay_time >= (last_best_normal_delay_time * 1.3)):
                    # 求解过程中，由于优先模具的总延期时间获得了微小提升，导致普通模具总延期时间出现大幅波动的结果，视为较差的解，直接放弃记录
                    return False

        except TypeError:
            # 目标或kpi的实际值超过一定大小时，CPLEX会返回str格式的"Infinity"(CPLEX真的脑子有坑)，从而导致<=号的运行错误
            pass
        except RuntimeError:
            # 有极其弱智的情况下没有normal process, 跳过这种情况吧
            pass

        return True


class StatisticCallback(CpoCallback):
    def __init__(self,
                 logger: logging.Logger,
                 other_info):
        self.logger = logger
        self.other_info = other_info

    def invoke(self, solver, event, sres):
        if event == "StartSolve":
            stats = solver.get_model().get_statistics()
            self.logger.info(f"{self.other_info}, "
                             f"{stats.nb_interval_vars}, "
                             f"{stats.nb_constraints}")
            solver.abort_search()


class OptimalRecordCallback(CpoCallback):
    def __init__(self,
                 mould_task_cnt: int,
                 objs_list: List[str]):
        self.task_cnt = mould_task_cnt
        self.objs_list = objs_list
        self.logger = logging.getLogger("is_optimal")

        self.last_solution = None

    def invoke(self, solver, event, sres):
        if event == 'Solution':
            self.last_solution = sres

        if event == 'EndSearch':
            mould_id = solver.get_model().get_name()
            additional_info = ''
            if isinstance(sres, cp.CpoSolveResult):
                if not sres.is_solution():
                    result_flag = 'No solution'
                elif not sres.is_solution_optimal():
                    result_flag = 'Not optimal'
                    gaps = self.last_solution.solution.objective_gaps
                    objs = self.last_solution.solution.objective_values
                    additional_info = ','.join([f'{self.objs_list[i]}:{objs[i]}({gaps[i]})'
                                                for i in range(len(self.objs_list))])
                elif sres.is_solution_optimal():
                    result_flag = 'Optimal'
                    objs = self.last_solution.solution.objective_values
                    additional_info = ','.join([f'{self.objs_list[i]}:{objs[i]}'
                                                for i in range(len(self.objs_list))])
                else:
                    result_flag = 'Unknown'
            elif isinstance(sres, cp.CpoRefineConflictResult):
                result_flag = 'Conflict'
            else:
                result_flag = 'Unknown'

            self.logger.info(
                f'[{result_flag}]'.ljust(15)
                + mould_id
                + f'({self.task_cnt} tasks)'.ljust(12)
                + additional_info
            )


# ==========================================
# File: AS/dataloader.py
# ==========================================




class DataLoader:
    """ 数据加载 """

    def __init__(self,
                 data: dict):
        self.data = data

        # 基础数据
        args = data['args']
        self.base_time = datetime.datetime.strptime(args['base_time'], datetime_fmt)  # 基准时间（相对时间为0）
        self.max_datetime = datetime.datetime.strptime(args['max_time'], datetime_fmt)  # 排产考虑的最大时间
        self.ele_percentage: float = args.get('ele_percentage',
                                              1)  # 最小电极比例（EDM开工并不需要全部电极加工完成，只需保证达到最小比例）
        self.min_time_for_splitting: Dict[str, int] = args['min_time_for_splitting']  # 自动分割机台的最小时间（按工艺类型区分）
        self.circulation_time: Dict[str, int] = args['default_circulation_time']  # 流转时间（按工艺类型区分）

        self.processes: Dict[str, Process] = dict()  # 直接存储Process

        # 按其他单位存储process
        self.moulds: Dict[str, Mould] = dict()
        self.businesses: Dict[str, Business] = dict()

        self.batches: Dict[str, Batch] = dict()
        self.resources: Dict[str, Resource] = dict()
        self.sequences: Dict[str, Sequence] = dict()

        self._loading_processes()

    def _loading_processes(self) -> None:
        """ 加载所有工艺数据 """
        self._pre_processing()

        for process_id, process_data in self.data['data'].items():
            process = Process(process_id, self, **process_data)
            self.processes[process_id] = process

            if process.mould_id not in self.moulds.keys():
                self.moulds[process.mould_id] = Mould(process.mould_id)
            self.moulds[process.mould_id].add_process(process)

            if process.business_id not in self.businesses.keys():
                self.businesses[process.business_id] = Business(process.business_id)
            self.businesses[process.business_id].add_process(process)

        # self.processes = dict(sorted(self.processes.items(), key=lambda x: x[0]))

        self._post_processing()

    def _pre_processing(self) -> None:
        for batch_id, batches in self.data['batches'].items():
            for process_id, stage_id in batches['tasks']:
                try:
                    stage = self.data['data'][process_id]['stages'][stage_id]
                    if len(stage['tasks']) == 1:
                        for task in stage['tasks'].values():
                            task['batch_id'] = batch_id
                except KeyError:
                    pass

    def _post_processing(self) -> None:
        """ 工艺数据全部加载完毕后，执行后处理相关逻辑 """
        # 主要是四方面逻辑：
        # 1. 自动将工时过长的工艺，按要求拆分机台加工
        # 2. 关联组立关系
        # 3. 按直接加工逻辑推理得到每个工序的最早开始加工时间，从而限定变量的可行域范围
        # 4. 初始化Batch和Resource相关数据
        for process_id, process in self.processes.items():
            process.calculate_estimated_times()  # 预先计算时间，防止递归溢出
            process.will_overdue = process.estimated_end_time > process.relative_t0_time
            for idx, (stage_id, stage) in enumerate(process.stages.items()):

                if stage.can_be_split:
                    stage.split()

                if stage.stage_code == 'FA':
                    # 关联组立关系
                    if stage.assemble_stages:
                        for item in stage.assemble_stages:
                            # 兼容性处理：如果生成的数据不符合[process_id, stage_id]格式，则跳过
                            if not isinstance(item, (list, tuple)) or len(item) != 2:
                                # print(f"Warning: Invalid assemble_stages item: {item} in {stage.full_name}")
                                continue

                            sub_process_id, sub_stage_id = item
                            try:
                                sub_stage = self.processes[sub_process_id][sub_stage_id]
                                stage.sub_stages.append(sub_stage)
                                sub_stage.main_stage = stage
                            except KeyError:
                                # raise ModelingException(f'{stage.full_name} FA工序匹配失败: 辅件{sub_process_id}不存在')
                                # 在生成数据场景下，可能会生成不存在的关联ID，暂时忽略以允许程序运行
                                pass

                    if stage.disassemble_stage:
                        main_process_id, main_stage_id = stage.disassemble_stage
                        try:
                            main_stage = self.processes[main_process_id][main_stage_id]
                            main_stage.sub_stages.append(stage)
                            stage.main_stage = main_stage
                        except KeyError:
                            raise ModelingException(f'{stage.full_name} FA工序匹配失败: 主件{main_process_id}不存在')

                if stage.resources_id:
                    for resource_id in stage.resources_id:
                        if resource_id not in self.resources.keys():
                            self.resources[resource_id] = Resource(resource_id)

        # 扫一遍以后，再额外检查FA是否有冲突已删除

        for batch_id, batch_info in self.data['batches'].items():
            batch = Batch(batch_id,
                          is_fixed_time=batch_info["fixed_time"],
                          estimated_time=batch_info["estimated_time"])
            for (process_id, stage_id) in batch_info['tasks']:
                try:
                    stage = self.processes[process_id][stage_id]
                    batch.add_stage(stage)
                except KeyError:
                    pass
            if batch.tasks:
                self.batches[batch_id] = batch

        for sequence_id, sequence_info in self.data['sequences'].items():
            sequence = Sequence(sequence_id, sequence_info['fixed_sequence'])
            for (process_id, stage_id) in sequence_info['stages']:
                try:
                    stage = self.processes[process_id][stage_id]
                    sequence.add_stage(stage)
                except KeyError:
                    pass
            if sequence.tasks:
                self.sequences[sequence_id] = sequence

        # 有较多情况会导致只有一个task的batch不在batches里出现，但是task中会存储batch_id，难以避免，单独做前处理清除
        for process in self.processes.values():
            for stage in process.stages.values():
                for task in stage.tasks.values():
                    if task.batch_id and task.batch_id not in self.batches:
                        task.batch_id = None

    def __getitem__(self, item):
        return self.processes.__getitem__(item)

    @property
    def priority_businesses(self) -> List["Business"]:
        return [b for b in self.businesses.values() if b.is_priority]

    @property
    def n_tasks(self) -> int:
        return sum(p.n_tasks for p in self.processes.values())

    def real_to_relative_time(self, real_time: datetime.datetime) -> int:
        if real_time is None:
            return 0
        else:
            datetime_delta = real_time - self.base_time
            return datetime_delta.days * 24 * 60 + datetime_delta.seconds // 60

    def relative_to_real_time(self, relative_time: int) -> datetime.datetime:
        return self.base_time + datetime.timedelta(minutes=relative_time)


class Mould:
    def __init__(self,
                 mould_id: str):
        self.mould_id = mould_id
        self.processes: Dict[str, Process] = dict()

    def add_process(self, process: "Process") -> None:
        self.processes[process.process_id] = process


class Business:
    def __init__(self,
                 business_id: str):
        self.business_id = business_id
        self.processes: Dict[str, Process] = dict()

    def add_process(self, process: "Process") -> None:
        self.processes[process.process_id] = process

    @property
    def is_delayed(self) -> cp.CpoExpr:
        return cp.min(1, cp.sum(p.is_delayed for p in self.processes.values()))

    @property
    def is_priority(self) -> bool:
        return any(p.is_priority for p in self.processes.values())


class Process:
    """ 工艺类，实际对应的是一个零件 """

    def __init__(self,
                 process_id: str,
                 data_loader: DataLoader,
                 **kwargs):
        self.process_id = process_id
        self.data_loader = data_loader
        self.mould_id: str = kwargs.get('mould_id', " ")
        self.business_id: str = kwargs.get('business_id', " ")
        self.part_code: str = kwargs.get("part_code", " ")  # 零件名称
        self.planning_type: int = kwargs.get('planning_type', 0)  # 加工类型，机台匹配用
        self.quantity: int = kwargs.get('quantity', 1)
        self.reply_t0_date = datetime.datetime.strptime(kwargs['reply_t0_date'], datetime_fmt)  # 工艺交期
        self.process_priority: int = kwargs.get('process_priority', 0)  # 优先级
        self.is_critical: bool = kwargs.get('is_critical', False)  # 是否紧急
        self.emergency_circulation_time: Optional[int] = kwargs.get('emergency_circulation_time',
                                                                    None)  # 紧急流转时间（覆盖默认流转时间，且不区分工艺类型）
        self.relative_locked_start_time: float = kwargs.get('relative_locked_start_time', -1.0)
        self.relative_locked_end_time: float = kwargs.get('relative_locked_end_time', -1.0)
        self.will_overdue: Optional[bool] = None

        self.stages: Dict[str, Stage] = dict()

        self._loading_stages(**kwargs)

    def _loading_stages(self, **kwargs) -> None:
        """ 加载全部工序 """
        previous_stage: Optional["Stage"] = None

        for stage_id, stage_data in kwargs['stages'].items():
            self.stages[stage_id] = Stage(stage_id, self, **stage_data, previous_stage=previous_stage)
            previous_stage = self.stages[stage_id]

    def calculate_estimated_times(self) -> None:
        """ 线性计算各工序的预估时间，避免递归深度过大 """
        # 按加载顺序（工序顺序）线性计算，利用缓存机制避免递归
        for stage in self.stages.values():
            _ = stage.estimated_latest_end_time

    @property
    def estimated_end_time(self) -> int:
        """ 估计整条工艺路线所需的最小时间（考虑流转时间，考虑休息时间），供判断是否将会延期使用 """
        return int(self.last_stage.estimated_latest_end_time * 1.25)

    def __getitem__(self, item):
        return self.stages.__getitem__(item)

    @property
    def first_stage(self) -> "Stage":
        return list(self.stages.values())[0]

    @property
    def last_stage(self) -> "Stage":
        return list(self.stages.values())[-1]

    @property
    def start_time(self) -> cp.CpoExpr:
        # 开始时间（第一个工序的开始时间）
        return self.first_stage.start_time

    @property
    def end_time(self) -> cp.CpoExpr:
        # 结束时间（最后一个工序的结束时间）
        return self.last_stage.end_time

    @property
    def relative_t0_time(self) -> int:
        # 相对交期
        return self.data_loader.real_to_relative_time(self.reply_t0_date)

    @property
    def time_gap(self) -> cp.CpoExpr:
        """ 结束时间与交期的差，正数代表延期，负数代表提前 """
        if self.relative_t0_time < 0:
            # 如果交期已过，则gap取相对于开始时间的gap（而不是相对于交期，否则可能会出现异常的值）
            return self.end_time
        else:
            process_time_gap = self.end_time - self.relative_t0_time
            return process_time_gap

    @property
    def delayed_time(self) -> cp.CpoExpr:
        return cp.max(0, self.time_gap)

    @property
    def advanced_time(self) -> cp.CpoExpr:
        return cp.min(0, self.time_gap)

    # @property
    # def will_overdue(self) -> bool:
    #     """ 是否已经延期或者将要延期 """
    #     return self.estimated_end_time > self.relative_t0_time

    @property
    def n_tasks(self) -> int:
        return sum(s.n_tasks for s in self.stages.values())

    @property
    def is_priority(self) -> bool:
        """ 判断是否优先（交期小于1天的工艺默认优先） """
        return (self.process_priority
                or self.is_critical
                or (self.relative_t0_time <= 1440))

    @property
    def is_delayed(self) -> cp.CpoExpr:
        return cp.greater(self.end_time, self.relative_t0_time)


class Stage:
    """ 工序类 """

    def __init__(self,
                 stage_id: str,
                 process: Process,
                 previous_stage: Optional["Stage"] = None,
                 **kwargs):
        self.stage_id = stage_id
        self.stage_code: str = kwargs['stage_code']
        self.stage_order: int = kwargs['stage_order']
        self.estimated_time: int = math.ceil(kwargs['estimated_time'])
        self.min_start_time = datetime.datetime.strptime(kwargs['min_start_time'],
                                                         datetime_fmt) if kwargs['min_start_time'] else None
        self.previous_process: Optional[str] = kwargs.get('previous_process', None)  # 可能的前置工艺（例如返修工艺）
        self.resources_id: Optional[List[str]] = kwargs.get('resources_id', None)  # 对于EW及某系工序，需要考虑供用资源的问题（例如板材）

        self.assemble_stages: Optional[List[List[str]]] = kwargs.get('assemble_stages', None)  # （作为主件时）组立的目标工序
        self.disassemble_stage: Optional[List[str]] = kwargs.get('disassemble_stage', None)  # （作为辅件时）解组立的目标工序
        self.main_stage: Optional[Stage] = None
        self.sub_stages: List[Stage] = []

        self.electrodes: Optional[Dict[str, int]] = None

        self.sequence_id: Optional[str] = None

        self.process = process
        self.previous_stage = previous_stage

        self.rest_electrodes: Optional[List[str]] = None

        if self.stage_code == 'EDM':
            self.electrodes = kwargs['electrodes']

        self.tasks: Dict[str, Task] = dict()
        self._cached_estimated_latest_end_time = None

        for task_id, task_dict in kwargs['tasks'].items():
            self.tasks[task_id] = Task(task_id, self, **task_dict)

    def __repr__(self):
        return self.stage_code

    def __getitem__(self, item):
        return self.tasks.__getitem__(item)

    def __getattr__(self, item):
        # print(f"正在查找属性: {item}")
        return getattr(self.process, item)

    def split(self):
        (original_task_id, original_task), = self.tasks.items()
        # 均分工时，拆成两个任务
        task_1_quantity = original_task.quantity // 2
        task_1_time = math.ceil((task_1_quantity / original_task.quantity) * original_task.estimated_time)
        new_task_1 = Task.manually_new(task_id=original_task_id + '-1',
                                       stage=self,
                                       quantity=task_1_quantity,
                                       estimated_time=task_1_time)

        new_task_2 = Task.manually_new(task_id=original_task_id + '-2',
                                       stage=self,
                                       quantity=original_task.quantity - task_1_quantity,
                                       estimated_time=original_task.estimated_time - task_1_time)

        self.tasks = {new_task_1.task_id: new_task_1,
                      new_task_2.task_id: new_task_2}

    def get_select_resource_constraint(self) -> Optional[cp.CpoExpr]:
        task = list(self.tasks.values())[0]  # 仅为第一个任务选择资源（业务要求）
        if not self.resources_id or task.locked_start_time:
            return None

        for resource_id in self.resources_id:
            resource = self.data_loader.resources[resource_id]
            task_resource_var = cp.interval_var(optional=True,
                                                name=f'{task.task_id}-{resource_id}')
            task.alternative_resources[resource_id] = task_resource_var
            resource.vars.append(task_resource_var)

        alternative_constraint = cp.alternative(task.var,
                                                task.alternative_resources.values())
        alternative_constraint.set_name(f'Task \'{task.task_id} select resource')
        return alternative_constraint

    @property
    def is_main(self):
        return self.main_stage is None

    @property
    def circulation_time(self) -> int:
        if self.process.emergency_circulation_time:
            return self.process.emergency_circulation_time
        else:
            try:
                return self.data_loader.circulation_time[self.stage_code]
            except KeyError:
                raise ConfigurationException(f'工序类型\"{self.stage_code}\"未设置流转时间!')

    @property
    def full_name(self) -> str:
        return f'{self.process.part_code}  ({self.stage_name})'

    @property
    def stage_name(self) -> str:
        return f'{self.stage_order}-{self.stage_code}'

    @property
    def need_planning(self) -> bool:
        return not (self.stage_code == 'FA' and self.is_main is False)

    @property
    def start_time(self) -> Optional[cp.CpoExpr]:
        try:
            return cp.min(task.start_time for task in self.tasks.values() if not task.is_locked)
        except ValueError:
            return None

    @property
    def end_time(self) -> Optional[cp.CpoExpr]:
        return cp.max(task.end_time for task in self.tasks.values())

    @property
    def start_time_of_last_task(self) -> Optional[cp.CpoExpr]:
        if len(self.tasks) < 2:
            return self.start_time
        else:
            return cp.max(task.start_time for task in self.tasks.values() if not task.is_locked)

    @property
    def var(self) -> cp.CpoIntervalVar:
        if len(self.tasks) == 1:
            return list(self.tasks.values())[0].var
        else:
            raise AttributeError('该工序任务数量大于1, 不能直接调用var!')

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    @property
    def estimated_latest_end_time(self) -> int:
        if self._cached_estimated_latest_end_time is not None:
            return self._cached_estimated_latest_end_time
        val = max(t.estimated_end_time for t in self.tasks.values())
        self._cached_estimated_latest_end_time = val
        return val

    @property
    def can_be_split(self) -> bool:
        # 自动拆分机台需要同时满足以下所有要求：
        # 1. 整条工艺将要或已经延期
        # 2. 工序预估工时大于要求的下限
        # 3. 工序仅有1个任务
        # 4. 任务未被锁定
        # 5. 工件数量大于1
        # process层面
        if not self.process.will_overdue:
            return False

        # Stage层面
        if (self.n_tasks != 1
                or self.stage_code not in self.data_loader.min_time_for_splitting.keys()):
            return False

        # Task层面
        task, = self.tasks.values()
        if (task.quantity < 2
                or task.is_locked
                or task.batch_id is not None
                or task.estimated_time < self.data_loader.min_time_for_splitting[self.stage_code]):
            return False

        return True

    @property
    def electrodes_ready_time(self) -> List[cp.CpoExpr]:
        if self.stage_code != 'EDM':
            raise ModelingException('非EDM工序不需要电极')

        n_electrodes = len(self.electrodes)
        electrodes_finish_time = []

        unfinished_electrodes = [electrode_id
                                 for electrode_id in self.electrodes.keys()
                                 if electrode_id in self.data_loader.processes.keys()]

        if n_electrodes >= 10:
            # 如果电极组数大于10，则无需全部电极完工，只需要满足最小电极完工比例即可开始放电
            # 最小比例约束的是电极组数，且有先后次序
            n_unnecessary_electrodes = n_electrodes - math.ceil(n_electrodes * self.data_loader.ele_percentage)
            necessary_electrodes = unfinished_electrodes[:-n_unnecessary_electrodes]
            self.rest_electrodes = unfinished_electrodes[-n_unnecessary_electrodes:]  # 可以在放电开始后才完工的电极
        else:
            necessary_electrodes = unfinished_electrodes

        for electrode_id in necessary_electrodes:
            electrode_process = self.data_loader[electrode_id]
            electrodes_finish_time.append(
                electrode_process.end_time + electrode_process.last_stage.circulation_time
            )

        return electrodes_finish_time

    @property
    def need_order_constraint(self) -> bool:
        """ 判断在建模时该工序是否需要添加加工次序约束 """
        # 有两种情况无需添加:
        # 1. 当前工序的start_time为空（所有任务都锁定/其他)
        # 2. 当前工序为辅件的解组立工序（跟随主件故无需添加约束）
        return (self.start_time is not None
                and not (self.is_main is False and
                         self.disassemble_stage is not None))

    def get_rest_electrodes_finish_time_constraint(self) -> Optional[cp.CpoExpr]:
        electrodes_finish_time = []
        for electrode_id in self.rest_electrodes:
            try:
                electrode_process = self.data_loader[electrode_id]
                electrodes_finish_time.append(
                    electrode_process.end_time + electrode_process.last_stage.circulation_time
                )
            except KeyError:
                continue

        if len(electrodes_finish_time) == 0:
            return None

        rest_electrodes_finish_time_constraint = cp.less_or_equal(
            cp.max(electrodes_finish_time),
            self.start_time + math.ceil(self.estimated_time * self.data_loader.ele_percentage)
        )
        rest_electrodes_finish_time_constraint.set_name(
            f'Stage \'{self.stage_id}\' rest electrodes finish time constraint'
        )
        return rest_electrodes_finish_time_constraint


class BaseUnit(ABC):
    """ 排产单元的基类，主要描述排产相关的属性 """

    def __init__(self,
                 stage_code: str = None,
                 planning_type: int = None,
                 estimated_time: float = 0,
                 quantity: int = None,
                 start_time: str = None,
                 end_time: str = None,
                 device_id: str = None,
                 **kwargs):
        # 基本属性
        self.stage_code = stage_code
        self.planning_type = planning_type
        self.estimated_time: int = math.ceil(estimated_time)
        self.quantity = quantity

        # 锁定属性
        self.locked_start_time: Optional[datetime.datetime] = datetime.datetime.strptime(
            start_time, datetime_fmt) if start_time else None
        self.locked_end_time: Optional[datetime.datetime] = datetime.datetime.strptime(
            end_time, datetime_fmt) if end_time else None
        self.locked_device_id: Optional[str] = device_id

        # 建模属性
        self.var = cp.interval_var(name=self.unit_id)
        self.alternative_devices: Dict[str, cp.CpoIntervalVar] = dict()

        self.chosen_device_id: Optional[str] = None

    @property
    @abstractmethod
    def unit_id(self) -> str:
        """ 独立ID """

    @property
    @abstractmethod
    def relative_locked_start_time(self) -> int:
        """ 锁定开始时间（相对时间，若锁定为空则返回0） """

    @property
    @abstractmethod
    def relative_locked_end_time(self) -> int:
        """ 锁定结束时间（相对时间，若锁定为空则返回0） """

    @property
    def estimated_earliest_start_time(self) -> int:
        return 0

    @property
    def estimated_end_time(self) -> int:
        return self.estimated_earliest_start_time + self.estimated_time

    def get_select_device_constraint(self) -> Optional[cp.CpoExpr]:
        """ 返回筛选设备的约束 """
        if len(self.alternative_devices) <= 1:
            return None

        alternative_constraint = cp.alternative(self.var, self.alternative_devices.values())
        alternative_constraint.set_name(f'Task \'{self.unit_id}\' select device')
        return alternative_constraint

    @property
    def start_time(self) -> Optional[cp.CpoExpr]:
        """ 返回开始时间 """
        return cp.start_of(self.var)

    @property
    def end_time(self) -> Optional[cp.CpoExpr]:
        """ 返回结束时间 """
        return cp.end_of(self.var)

    def get_alternative_result(self,
                               alternative_dict: Dict[str, cp.CpoIntervalVar],
                               solution: cp.CpoSolveResult) -> Optional[str]:
        if len(alternative_dict) == 1:
            return list(alternative_dict.keys())[0]

        for _id, interval in alternative_dict.items():
            itv = solution.get_var_solution(interval)
            if itv.is_present():
                return _id
        else:
            raise ModelingException(f'{self.unit_id}未找到资源!')

    def get_chosen_device_id(self, solution: cp.CpoSolveResult) -> Optional[str]:
        if self.chosen_device_id:
            return self.chosen_device_id

        try:
            return self.get_alternative_result(self.alternative_devices, solution)
        except ModelingException:
            raise ModelingException(f'{self.unit_id} 未找到加工设备')


class Task(BaseUnit):
    """ 任务类 """

    def __init__(self,
                 task_id: str,
                 stage: Stage,
                 batch_id: Optional[str] = None,
                 **kwargs):
        self.task_id = task_id
        self.stage = stage
        self.batch_id: Optional[str] = batch_id
        super().__init__(stage_code=stage.stage_code,
                         planning_type=stage.planning_type,
                         **kwargs)

        self.alternative_resources: Dict[str, cp.CpoIntervalVar] = dict()  # 可选的不同资源的变量

    def __getattr__(self, item):
        return getattr(self.stage, item)

    @property
    def estimated_earliest_start_time(self):
        previous_stage = self.previous_stage
        if self.locked_start_time:
            estimated_earliest_start_time = self.relative_locked_start_time

        elif not previous_stage:
            estimated_earliest_start_time = max(0,
                                                self.data_loader.real_to_relative_time(self.stage.min_start_time))

        else:
            previous_end_time = previous_stage.estimated_latest_end_time
            if (self.stage_code == 'FA'
                    and self.stage_code == 'FA'
                    and self.stage.stage_order == previous_stage.stage_order):
                circulation_time = 0
            elif self.stage.process.emergency_circulation_time:
                circulation_time = self.stage.process.emergency_circulation_time
            else:
                circulation_time = previous_stage.circulation_time

            estimated_earliest_start_time = max(previous_end_time + circulation_time,
                                                self.data_loader.real_to_relative_time(self.stage.min_start_time))

        return estimated_earliest_start_time

    @property
    def relative_locked_start_time(self) -> int:
        return self.data_loader.real_to_relative_time(self.locked_start_time)

    @property
    def relative_locked_end_time(self) -> int:
        return self.data_loader.real_to_relative_time(self.locked_end_time)

    @property
    def unit_id(self) -> str:
        return self.task_id

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_device_id or self.locked_end_time or self.locked_start_time)

    @classmethod
    def manually_new(cls, task_id: str, stage: Stage, quantity: int, estimated_time: float):
        """ 手动实例化Task对象，而不是通过解析数据dict获得（用于拆分任务） """
        return cls(task_id=task_id,
                   stage=stage,
                   quantity=quantity,
                   estimated_time=estimated_time)

    def get_chosen_resource_id(self, solution: cp.CpoSolveResult) -> Optional[str]:
        return self.get_alternative_result(self.alternative_resources, solution)

    def parse_solution(self, solution: cp.CpoSolveResult, device_allocate_result: Dict[str, Optional[str]]):
        itv = solution.get_var_solution(self.var)
        task_dict = {
            "process_id": self.stage.process.process_id,
            "stage_id": self.stage.stage_id,
            "start_time": str(self.data_loader.relative_to_real_time(itv.get_start())),
            "end_time": str(self.data_loader.relative_to_real_time(itv.get_end())),
            "device_id": None,
            "resource_id": None
        }

        if self.batch_id:
            task_dict.update({
                "device_id": device_allocate_result[self.batch_id]
            })
        elif self.stage.sequence_id:
            task_dict.update({
                "device_id": device_allocate_result[self.stage.sequence_id]
            })
        elif self.alternative_devices:
            task_dict.update({
                "device_id": device_allocate_result[self.task_id]
            })

        if self.alternative_resources:
            task_dict.update({
                "resource_id": self.get_chosen_resource_id(solution)
            })

        return task_dict


class BaseUnitCollection(BaseUnit, ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.tasks: List[Task] = []

    def add_stage(self, stage: Stage):
        for task in stage.tasks.values():
            self.add_task(task)

    def add_task(self, task: Task):
        self.tasks.append(task)

    @property
    def represented_task(self) -> Task:
        return self.tasks[0]


class SameStageTypeUnitCollection(BaseUnitCollection, ABC):
    def add_task(self, task: Task):
        super().add_task(task)
        self._check_attributes_consistency(attr='stage_code', attr_name='工艺类型', new_task=task)
        self._check_attributes_consistency(attr='planning_type', attr_name='工单类型', new_task=task)
        self._check_attributes_consistency(attr='locked_device_id', attr_name='锁定设备', new_task=task)

    def _check_attributes_consistency(self, attr: str, attr_name: str, new_task: Task, ignore_none: bool = True):
        old_attr_value = getattr(self, attr)
        new_attr_value = getattr(new_task, attr)
        if old_attr_value is None:
            setattr(self, attr, new_attr_value)


class Batch(SameStageTypeUnitCollection):
    def __init__(self,
                 batch_id: str,
                 is_fixed_time: bool,
                 **kwargs):
        self.batch_id = batch_id
        super().__init__(**kwargs)

        self.is_fixed_time = is_fixed_time

    def add_stage(self, stage: Stage):
        for task in stage.tasks.values():
            if task.batch_id == self.batch_id:
                self.add_task(task)

    def add_task(self, task: Task):
        super().add_task(task)

        task.batch_id = self.batch_id
        self._check_attributes_consistency(attr='locked_start_time', attr_name='锁定开始时间', new_task=task)
        self._check_attributes_consistency(attr='locked_end_time', attr_name='锁定结束时间', new_task=task)

        if not self.is_fixed_time:
            self.estimated_time += task.estimated_time

    def get_synchronize_constraint(self) -> cp.CpoExpr:
        # 同步Batch的变量和全部包含的任务变量
        batch_synchronize_constraint = cp.synchronize(self.var,
                                                      [t.var for t in self.tasks])
        batch_synchronize_constraint.set_name(f'Batch \'{self.batch_id}\' synchronize')
        return batch_synchronize_constraint

    @property
    def relative_locked_start_time(self) -> int:
        return self.represented_task.relative_locked_start_time

    @property
    def relative_locked_end_time(self) -> int:
        return self.represented_task.relative_locked_end_time

    @property
    def unit_id(self) -> str:
        return self.batch_id

    @property
    def estimated_earliest_start_time(self) -> int:
        return max(t.estimated_earliest_start_time for t in self.tasks)


class Sequence(SameStageTypeUnitCollection):
    def __init__(self,
                 sequence_id: str,
                 fixed_sequence: bool,
                 **kwargs):
        self.sequence_id = sequence_id
        self.fixed_sequence = fixed_sequence
        super().__init__(**kwargs)

    def add_stage(self, stage: Stage):
        stage.sequence_id = self.sequence_id
        for task in stage.tasks.values():
            self.add_task(task)

    def add_task(self, task: Task):
        super().add_task(task)
        self.estimated_time += task.estimated_time

    def get_span_constraint(self) -> cp.CpoExpr:
        sequence_span_constraint = cp.span(self.var,
                                           [t.var for t in self.tasks])
        sequence_span_constraint.set_name(f'Sequence \'{self.sequence_id}\' spans constraint')
        return sequence_span_constraint

    def get_tasks_no_overlap_constraint(self) -> cp.CpoExpr:
        task_included_no_overlap = cp.no_overlap([t.var for t in self.tasks])
        task_included_no_overlap.set_name(f'Tasks in sequence \'{self.sequence_id}\' no overlap')
        return task_included_no_overlap

    def get_device_synchronize_constraint(self) -> List[Optional[cp.CpoExpr]]:
        """ 任务选择的设备要与sequence选择的设备同步 """
        if len(self.alternative_devices) == 1:
            return [None]
        else:
            constraints = []
            for device_id, sequence_device_var in self.alternative_devices.items():
                for task in self.tasks:
                    same_device_constraint = cp.equal(cp.presence_of(sequence_device_var),
                                                      cp.presence_of(task.alternative_devices[device_id]))
                    same_device_constraint.set_name(f'{task.task_id}-{device_id} '
                                                    f'sequence device synchronize constraint')
                    constraints.append(same_device_constraint)
            return constraints

    def get_order_constraint(self) -> List[cp.CpoExpr]:
        constraints = []
        for i in range(1, len(self.tasks)):
            order_constraint = cp.end_before_start(self.tasks[i - 1].end_time,
                                                   self.tasks[i].start_time)
            order_constraint.set_name(f'Sequence order constraint between '
                                      f'{self.tasks[i].task_id} and {self.tasks[i - 1].task_id}')
            constraints.append(order_constraint)
        return constraints

    def get_constraints(self) -> List[cp.CpoExpr]:
        """ 返回sequence相关的全部约束：选择设备约束、span约束、内部任务no overlap约束、内部任务选择设备与sequence同步约束 """
        constraints = [self.get_select_device_constraint(),
                       self.get_span_constraint(),
                       self.get_tasks_no_overlap_constraint(),
                       *self.get_device_synchronize_constraint()]

        if self.fixed_sequence:
            constraints += self.get_order_constraint()

        return constraints

    @property
    def relative_locked_start_time(self) -> int:
        return 0

    @property
    def relative_locked_end_time(self) -> int:
        return 0

    @property
    def unit_id(self) -> str:
        return self.sequence_id


class Resource:
    """ 资源类 """

    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.vars = []


# ==========================================
# File: AS/device.py
# ==========================================


# from docplex.cp.model import *


class DeviceLoader(BaseDeviceLoader):
    def __init__(self,
                 data: dict):
        base_time = datetime.datetime.strptime(data['args']['base_time'],
                                               '%Y-%m-%d %H:%M:%S')
        max_time = datetime.datetime.strptime(data['args']['max_time'],
                                              '%Y-%m-%d %H:%M:%S')
        super().__init__(base_time=base_time,
                         max_time=max_time,
                         data=data)

    def _loading_devices(self, data: dict):
        for device_id, device_data in data['devices'].items():
            rest_days = []
            if (global_rest_time := data['args']['rest_time']) is None:
                global_rest_time = []
            if (device_rest_time := device_data['rest_time']) is None:
                device_rest_time = []
            for rest_day in global_rest_time + device_rest_time:
                if rest_day not in rest_days:
                    rest_days.append(rest_day)
            device = Device(device_id=device_id,
                            stage_code=device_data['stage_code'],
                            base_time=self.base_time,
                            max_time=self.max_time,
                            daily_rest_time=device_data['daily_rest_time'],
                            rest_days=rest_days,
                            can_overlap=device_data['can_overlap'],
                            planning_type=device_data['planning_type'])

            repr_stage_code = device.stage_code[0]
            if repr_stage_code not in self.devices:
                self.devices[repr_stage_code] = {}
            for device_group in self.devices[repr_stage_code].values():
                if device == device_group:
                    device_group.device_id_list.append(device_id)
                    break
            else:
                virtual_device_group = VirtualDeviceGroup(device)
                self.devices_record[virtual_device_group.device_id] = virtual_device_group
                for stage_code in virtual_device_group.stage_code:
                    if stage_code not in self.devices:
                        self.devices[stage_code] = dict()
                    self.devices[stage_code][virtual_device_group.device_id] = virtual_device_group

    def get_compatible_devices(self, unit: BaseUnit) -> List["Device"]:
        if unit.locked_device_id:
            return [self.get_device_by_id(unit.locked_device_id)]
        
        stage_devices = self.devices.get(unit.stage_code, {})
        compatible_devices = [device for device in stage_devices.values() if device.is_compatible_for_task(unit)]
        can_overlap_devices = [device for device in compatible_devices if device.can_overlap]
        
        if can_overlap_devices:
            # 对匹配的设备进行二次筛选
            # 主要对于可同时加工的工序，仅筛选出一台开机时间最早的设备即可
            best_device = min(can_overlap_devices, key=lambda x: x.earliest_valid_time)
            return [best_device]

        else:
            return compatible_devices




class Device(BaseDevice):
    def __init__(self,
                 device_id: str,
                 stage_code: List[str],
                 base_time: datetime.datetime,
                 max_time: datetime.datetime,
                 daily_rest_time: List[List[str]],
                 rest_days: List[List[str]],
                 can_overlap: bool,
                 planning_type: int):
        super().__init__(device_id=device_id,
                         stage_code=stage_code,
                         base_time=base_time,
                         max_time=max_time,
                         daily_rest_time=daily_rest_time,
                         rest_days=rest_days,
                         can_overlap=can_overlap)
        self.planning_type = planning_type
        self.recently_available: bool = True  # 设备近期是否可用

        # 设备可选加工任务列表
        self.vars: Dict[str, cp.CpoIntervalVar] = dict()

        if self.earliest_valid_time is None:
            # 如果最早可用时间已经超过了排产的最大时间，则将设备设置为近期不可用状态
            self.recently_available = False

    def __eq__(self, other):
        return (sorted(self.stage_code) == sorted(other.stage_code) and
                self.can_overlap == other.can_overlap and
                self.working_intervals == other.working_intervals and
                self.planning_type == other.planning_type)

    @property
    def earliest_valid_time(self) -> Optional[int]:
        """ 设备的最早可用时间 """
        step_list = self.intensity.get_step_list()
        for (p, v) in step_list:
            if v == 100:
                return p
        else:
            return None

    def is_valid_on_time(self, start_time: int) -> bool:
        """ 判断设备是否可用于某任务加工 """
        for (s, e) in self.working_intervals:
            if s <= start_time < e:
                return True
            if s > start_time:
                break
        return False

    @property
    def is_valid_at_start(self) -> bool:
        return self.is_valid_on_time(0)

    def is_valid_on_locked_start_time(self, unit: BaseUnit):
        if (unit.locked_start_time
                and not self.is_valid_on_time(unit.relative_locked_start_time)):
            return False
        else:
            return True

    def is_valid_on_planning_type(self, unit: BaseUnit) -> bool:
        if (self.planning_type == 0
                or self.planning_type == unit.planning_type):
            return True
        else:
            return False

    def is_compatible_for_task(self, unit: BaseUnit) -> bool:
        # 设备匹配有以下要求：
        # 1. 近期可用
        # 2. 加工类型相同（设备加工类型为0代表通用）
        # 3. 如果是锁定开始时间的任务，则设备需要在锁定的开始时间点可用
        return (self.recently_available
                and self.is_valid_on_planning_type(unit)
                and self.is_valid_on_locked_start_time(unit))


class VirtualDeviceGroup(Device):
    devices_cnt = dict()

    def __init__(self, repr_device: Device):
        copied_inst = copy.deepcopy(repr_device)
        self.__dict__.update(copied_inst.__dict__)

        device_type = '-'.join(sorted(self.stage_code))
        VirtualDeviceGroup.devices_cnt[device_type] = VirtualDeviceGroup.devices_cnt.get(device_type, 0) + 1
        self.device_id = f'{device_type}-{VirtualDeviceGroup.devices_cnt[device_type]}'

        self.device_id_list = [repr_device.device_id]

    @property
    def n_devices(self) -> int:
        return len(self.device_id_list)


class DeviceAllocator:
    def __init__(self, device_group: VirtualDeviceGroup):
        self._dict = {device_id: 0 for device_id in device_group.device_id_list}

    def set(self, key, value):
        self._dict[key] = value
        self._dict = dict(sorted(self._dict.items(), key=lambda x: x[1]))

    def allocate(self, start_time: int, end_time: int) -> Optional[str]:
        if start_time == end_time:
            return None

        for device_id, device_min_start_time in self._dict.items():
            if start_time >= device_min_start_time:
                self.set(device_id, end_time)
                return device_id
        else:
            raise RuntimeError("Allocate error!")


# ==========================================
# File: AS/objectives.py
# ==========================================



class Objectives:
    def __init__(self, dataloader: DataLoader):
        self.data_loader = dataloader

    def __getitem__(self, objective: str):
        return methodcaller(objective)(self)
        # return self.__getattribute__(objective)()

    def critical_process_delay_time(self):
        """ 目标函数：紧急工艺的总延期时间（分钟） """
        critical_processes = [p for p in self.data_loader.processes.values() if p.is_critical]
        if not critical_processes:
            return None
        else:
            return cp.sum(p.delayed_time for p in critical_processes)

    def priority_business_delay_number(self):
        """ 目标函数：优先订单的总延期数量（套数） """
        priority_businesses = self.data_loader.priority_businesses

        if not priority_businesses:
            return None
        else:
            return cp.sum(b.is_delayed for b in priority_businesses)

    def priority_process_delay_time(self):
        """ 目标函数：优先工艺的总延期时间（分钟） """
        priority_processes = [p for p in self.data_loader.processes.values() if p.is_priority]
        if not priority_processes:
            return None
        else:
            return cp.sum(p.delayed_time for p in priority_processes)

    def all_business_delay_number(self):
        """ 目标函数：所有订单的总延期数量（套数） """
        return cp.sum(b.is_delayed for b in self.data_loader.businesses.values())

    def normal_process_delay_time(self):
        """ 目标函数：普通工艺的总延期时间（分钟） """
        normal_processes = [p for p in self.data_loader.processes.values() if not p.is_priority]
        if not normal_processes:
            return None
        else:
            return cp.sum(p.delayed_time for p in normal_processes)

    def advanced_time(self):
        """ 目标函数：总的提前时间（分钟） """
        return cp.sum(p.advanced_time for p in self.data_loader.processes.values())


# ==========================================
# File: AS/model.py
# ==========================================




class Model:
    """ 基础模型 """

    def __init__(self,
                 token: str,
                 data: dict):
        self.token = token
        self.data = data
        # 排产目标
        self.objectives_list = ["critical_process_delay_time", "priority_process_delay_time",
                                "normal_process_delay_time", "advanced_time"]
        self.kpis_list = ["priority_business_delay_number", "all_business_delay_number"]

        # logger
        self.logger = logging.getLogger(token)

        # 排产基础信息
        args = data['args']
        self.factory_code: str = args['factory_code']
        self.circulation_time: Dict[str, int] = args['default_circulation_time']
        self.ele_percentage: float = args['ele_percentage']

        self.data_loader = DataLoader(data=data)
        self.device_loader = DeviceLoader(data=data)
        self.base_time = self.data_loader.base_time

        # 模型初始化
        self.model = cp.CpoModel()
        self.batches = self.data_loader.batches
        self.resources = self.data_loader.resources
        self.sequences = self.data_loader.sequences

        self.solver = None
        self.solution = None

        self.monitor_callback = None

    def _create_model(self) -> None:
        """ 建立模型：初始化变量，添加约束，添加目标和KPI """
        self._init_vars()
        self._add_order_constraints()
        self._add_device_no_overlap_constraints()
        self._add_resource_no_overlap_constraints()
        self._add_objectives()
        self._add_kpis()

    def _add_callbacks(self):
        self.monitor_callback = MonitorCallback(self.token,
                                                self.objectives_list,
                                                early_stop=True)
        self.solver.add_callback(self.monitor_callback)

    def _check_and_add_constraint(self, unchecked_constraint: Optional[cp.CpoExpr]):
        if unchecked_constraint is not None:
            self.model.add(unchecked_constraint)

    def _add_constraints(self, constraints: List[cp.CpoExpr] | Optional[cp.CpoExpr]):
        if not isinstance(constraints, list):
            constraints = [constraints]

        for constraint in constraints:
            self._check_and_add_constraint(constraint)

    def _pre_processing(self):
        """ [预留接口]建立模型前的前处理逻辑 """
        pass

    def _post_processing(self, *args, **kwargs):
        """ [预留接口]建立模型后的后处理逻辑 """
        pass

    def solve(self,
              time_limit: int = 30,
              workers: int = DEFAULT_WORKERS,
              tolerance: float = None,
              debug: bool = False,
              only_one_result: bool = False,
              *args,
              **kwargs) -> cp.CpoSolveResult:
        """ 求解模型 """
        modeling_start_time = time.time()
        self._pre_processing()
        self._create_model()
        self._post_processing(*args, **kwargs)
        #输出模型

        # 设置参数
        params = cp.CpoParameters()
        params.TimeLimit = time_limit  # 最大求解时间
        params.LogVerbosity = 'Terse'  # log的输出形式
        params.Workers = workers  # 搜索线程数量
        if tolerance:
            params.RelativeOptimalityTolerance = tolerance  # 容忍的误差

        self.solver = self.model.create_solver(params=params)
        self._add_callbacks()

        self.logger.info(f"Modeling used: {time.time() - modeling_start_time}s")

        if only_one_result:
            sol = self.solver.search_next()
        else:
            sol = self.solver.solve()

        if not sol and debug:
            # 在debug模式下，分析冲突点
            conflict = self.model.refine_conflict(ConflictRefinerTimeLimit=600)
            conflict.print_conflict()
            sys.exit()

        self.solution = self.monitor_callback.last_best_solution
        return self.solution

    def export_model(self, file_path: str):
            """ 仅执行建模逻辑，并导出模型为 .cpo 文件 """
            modeling_start_time = time.time()

            # 执行建模三部曲
            self._pre_processing()
            self._create_model()
            self._post_processing()

            # 调用 docplex.cp 的导出功能
            self.model.export_model(file_path)

            self.logger.info(f"Model exported to {file_path}. Modeling used: {time.time() - modeling_start_time}s")
            return file_path

    def refine_conflict(self, time_limit=600) -> cp.CpoRefineConflictResult:
        return self.model.refine_conflict(ConflictRefinerTimeLimit=time_limit)

    def _init_vars(self) -> None:
        """ 变量初始化 """
        for process_id, process in self.data_loader.processes.items():
            for stage_id, stage in process.stages.items():
                for task_idx, (task_id, task) in enumerate(stage.tasks.items()):
                    if task.batch_id or stage.sequence_id:
                        # 对于隶属于batch或sequence的任务，放到对应的排产单元中进行初始化
                        continue

                    if stage.need_planning:
                        self._init_variable(task)

                # 任务涉及到资源竞争
                select_resource_constraint = stage.get_select_resource_constraint()
                self._add_constraints(select_resource_constraint)

        for batch_id, batch in self.batches.items():
            # 初始化batch：计算总时长，生成变量
            self._init_variable(batch)
            self.model.add(batch.get_synchronize_constraint())

        for sequence_id, sequence in self.sequences.items():
            self._init_sequence(sequence)

    def _init_variable(self, unit: BaseUnit,
                       specified_devices: Optional[List[Device]] = None,
                       ignore_overlap: bool = False):
        """ 初始化具体的任务变量(任务或batch) """
        # 找到全部匹配的设备
        compatible_devices = specified_devices or self.device_loader.get_compatible_devices(unit)

        if len(compatible_devices) == 0:
            pass


        if len(compatible_devices) == 1:
            # 如果锁定了设备，或仅有一台匹配设备，则无需选择
            device, = compatible_devices

            if unit.locked_start_time:
                self.model.add(unit.start_time == unit.relative_locked_start_time)
            if unit.locked_end_time:
                self.model.add(unit.end_time == unit.relative_locked_end_time)
            if unit.locked_start_time is None or unit.locked_end_time is None:
                unit.var.set_size(unit.estimated_time)
                unit.var.set_intensity(device.intensity)

# TODO: 什么情况下会有 overlap 的情况，在 json 文件中如何体现？
            if not ignore_overlap:
                device.vars[unit.unit_id] = unit.var
            unit.alternative_devices[device.device_id] = unit.var

            if not unit.locked_start_time and not unit.locked_end_time:
                forbidden_start_constraint = cp.forbid_start(unit.var, device.intensity)
                forbidden_start_constraint.set_name(f'Task \'{unit.unit_id}\' forbid start at rest time')
                self.model.add(forbidden_start_constraint)

        elif len(compatible_devices) > 1:
            # 如果有多台匹配设备，则为每一台设备初始化一个可选变量，并从中选择一个实际加工
            for device in compatible_devices:
                task_device_var = cp.interval_var(optional=True,
                                                  name=f'{unit.unit_id}-{device.device_id}')
                if unit.locked_start_time:
                    task_device_var.set_start(unit.relative_locked_start_time)
                # else:
                #     task_device_var.set_start_min(max(unit.estimated_earliest_start_time,
                #                                       device.earliest_valid_time))
                if unit.locked_end_time:
                    task_device_var.set_end(unit.relative_locked_end_time)
                if unit.locked_start_time is None or unit.locked_end_time is None:
                    task_device_var.set_size(unit.estimated_time)
                    task_device_var.set_intensity(device.intensity)

                if not ignore_overlap:
                    device.vars[unit.unit_id] = task_device_var
                unit.alternative_devices[device.device_id] = task_device_var

                if not unit.locked_start_time and not unit.locked_end_time:
                    forbidden_start_constraint = cp.forbid_start(task_device_var, device.intensity)
                    forbidden_start_constraint.set_name(f'Task \'{unit.unit_id}\' forbid start at rest time')
                    self.model.add(forbidden_start_constraint)

            self.model.add(unit.get_select_device_constraint())

    def _init_sequence(self, sequence: Sequence):
        if sequence.locked_device_id:
            compatible_devices = [self.device_loader.get_device_by_id(sequence.locked_device_id)]
        else:
            # 找到所有任务可用设备的交集
            compatible_devices = self.device_loader.get_compatible_devices(sequence.tasks[0])
            for task in sequence.tasks[1:]:
                compatible_devices = [device for device in compatible_devices if
                                      device in self.device_loader.get_compatible_devices(task)]

        for task in sequence.tasks:
            self._init_variable(task, specified_devices=compatible_devices, ignore_overlap=True)

        # 初始化sequence
        if len(compatible_devices) == 1:
            device = compatible_devices[0]
            sequence.alternative_devices[device.device_id] = sequence.var
            device.vars[sequence.sequence_id] = sequence.var
        else:
            for device in compatible_devices:
                sequence_device_var = cp.interval_var(optional=True,
                                                      name=f'{sequence.sequence_id}-{device.device_id}')
                sequence.alternative_devices[device.device_id] = sequence_device_var
                device.vars[sequence.sequence_id] = sequence_device_var

        self._add_constraints(sequence.get_constraints())

    def _add_order_constraints(self) -> None:
        """
        添加工序间的加工顺序约束:
            1. 同一工艺路线中，后工序要在前工序后开始
            2. FA工序加工需要在所有组立件齐套后开始
            3. EDM工序加工需要在电极齐套（或满足最小比例）后开始
            4. 其他有前序工艺（返修等）的情况
        """
        for process_id, process in self.data_loader.processes.items():
# TODO：interval 是按照 task 定义的，在哪里跟 stage 绑定起来的？
            for idx, (stage_id, stage) in enumerate(process.stages.items()):
                previous_stage = stage.previous_stage
                stage_min_start_times = []  # 记录所有全部前置任务

                if (previous_stage
                        and stage.stage_order >= previous_stage.stage_order + 1):
                    # 前后工序的次序约束
                    # 当前的逻辑：如果前工序有多个任务，则后工序需要等待前工序的所有任务完成并齐套后才能开始加工
                    # 分机台同时分批流转的任务对应关系暂时不予考虑
                    stage_min_start_times.append(
                        previous_stage.end_time + previous_stage.circulation_time
                    )

# TODO: stage_order 的特殊逻辑
                elif (previous_stage
                      and stage.stage_code == 'FA'
                      and stage.stage_order == previous_stage.stage_order):
                    # 特殊逻辑：一步FA工序同时解组立后又组立，在数据中会拆成两个工序，但stage_order相同，这种情况下没有流转时间
                    stage_min_start_times.append(previous_stage.end_time)

                if stage.stage_code == 'FA':
                    # FA的齐套约束
                    self._add_fa_synchronize_constrains(stage)

# TODO: EDM 的特殊逻辑是什么，在 json 文件中是如何体现的？
                if stage.stage_code == 'EDM':
                    # EDM工序的电极齐套约束
                    if stage.electrodes and stage.start_time is not None:
                        stage_min_start_times += stage.electrodes_ready_time

                        if stage.rest_electrodes:
                            # 如果有可以在放电后完工的电极，也要约束这部分电极的完成时间
                            # 需要在电极预估工时*最小电极比例时间前完工，保证放电能够继续进行
                            rest_electrodes_finish_time_constraint = stage.get_rest_electrodes_finish_time_constraint()
                            if rest_electrodes_finish_time_constraint is not None:
                                self.model.add(rest_electrodes_finish_time_constraint)

                if stage.previous_process:
                    # 前置工艺约束（如修复工艺）
                    try:
                        previous_process = self.data_loader[stage.previous_process]
                        stage_min_start_times.append(
                            previous_process.end_time + previous_process.last_stage.circulation_time
                        )
                    except KeyError:
                        pass

                if stage.min_start_time:
                    # 工序指定了最早开始时间（如NC程式、外协回复）
                    stage_min_start_times.append(max(0,
                                                     self.real_to_relative_time(stage.min_start_time)))

                if stage_min_start_times and stage.need_order_constraint:
                    # 当前工序的最早开始时间，需要大于所有前序限制的最大值
                    stage_min_start_constraint = cp.greater_or_equal(stage.start_time,
                                                                     cp.max(stage_min_start_times))
                    stage_min_start_constraint.set_name(f'Stage \'{stage_id}\' start time')
                    self.model.add(stage_min_start_constraint)

    def _add_device_no_overlap_constraints(self) -> None:
        """ 为每个设备添加不能同时加工的约束 """
        for device_id, device in self.device_loader.devices_record.items():
            if not device.can_overlap and len(device.vars) > 1:
                max_parallel = cp.sum(cp.pulse(v, 1) for v in device.vars.values())
                parallel_constraint = cp.less_or_equal(max_parallel, device.n_devices)
                parallel_constraint.set_name(f'Parallel constraint \'{device_id}\'')
                self.model.add(parallel_constraint)

    def _add_resource_no_overlap_constraints(self) -> None:
        """ 为每个资源添加不能同时加工的约束 """
        for resource_id, resource in self.resources.items():
            if len(resource.vars) > 1:
                no_overlap_constraint = cp.no_overlap(resource.vars)
                no_overlap_constraint.set_name(f'Resource \'{resource_id}\' no overlap')
                self.model.add(no_overlap_constraint)

    def _add_fa_synchronize_constrains(self, stage: Stage) -> None:
        """ 添加FA主副工序同步约束 """
        if stage.is_main and stage.sub_stages:
            all_sub_stages = []
            sub_stages = stage.sub_stages
            while sub_stages:
                sub_stage = sub_stages.pop()
                all_sub_stages.append(sub_stage)
                if sub_stage.sub_stages:
                    sub_stages += sub_stage.sub_stages

            if all_sub_stages:
                sub_stage_vars = [sub_stage.var for sub_stage in all_sub_stages]
                fa_synchronize = cp.synchronize(stage.var, sub_stage_vars)
                fa_synchronize.set_name(f'FA \'{stage.stage_id}\' synchronize')
                self.model.add(fa_synchronize)

    def _add_objectives(self) -> None:
        """ 添加目标函数 """
        if self.model.objective is not None:
            if isinstance(self.model.objective, List):
                objs = self.model.objective
            else:
                objs = [self.model.objective]
            for obj in objs:
                self.model.remove(obj)

        objectives = Objectives(self.data_loader)
        objects_list = dict()
        for object_name in self.objectives_list:
            try:
                objective = objectives[object_name]
                if objective is not None:
                    objects_list[object_name] = objective
            except KeyError:
                self.logger.warning(f'No object name \'{object_name}\'')

        if len(objects_list) == 0:
            raise NoObjectiveException("没有有效的目标！")
        elif len(objects_list) == 1:
            self.model.add(cp.minimize(list(objects_list.values())[0]))
        else:
            self.model.add(cp.minimize_static_lex(list(objects_list.values())))

        self.objectives_list = list(objects_list.keys())

    def _add_kpis(self) -> None:
        """ 添加KPI """
        self.model.remove_all_kpis()

        objectives = Objectives(self.data_loader)
        for kpi_name in self.kpis_list:
            kpi = objectives[kpi_name]
            if kpi is not None:
                self.model.add_kpi(kpi, kpi_name)

    def allocate_specific_device(self, device_group: VirtualDeviceGroup) -> Dict[str, Optional[str]]:
        tasks_result = dict()
        units_to_allocate = []
        for unit_id, var in device_group.vars.items():
            itv = self.solution.get_var_solution(var)
            if not var.is_optional() or itv.is_present():
                units_to_allocate.append([unit_id, itv.get_start(), itv.get_end()])

        if device_group.n_devices == 1 or device_group.can_overlap:
            device_id = device_group.device_id_list[0]
            tasks_result = {unit[0]: device_id for unit in units_to_allocate}

        else:
            allocator = DeviceAllocator(device_group)
            for (unit_id, start_time, end_time) in sorted(units_to_allocate, key=lambda x: (x[1], x[2])):
                tasks_result[unit_id] = allocator.allocate(start_time, end_time)

        return tasks_result

    def allocate_device_id(self):
        tasks_result = dict()
        for device_group in self.device_loader.devices_record.values():
            tasks_result.update(self.allocate_specific_device(device_group))
        return tasks_result

    def _parse_result_to_dict(self) -> dict:
        result_dict = {}
        device_allocate_result = self.allocate_device_id()

        for process_id, process in self.data_loader.processes.items():
            for stage_id, stage in process.stages.items():
                for task_id, task in stage.tasks.items():
                    try:
                        result_dict[task_id] = task.parse_solution(self.solution, device_allocate_result)
                    except AttributeError:
                        self.logger.warning(f'任务{task_id}不在排程结果中!')

        return result_dict

    def real_to_relative_time(self, real_time: datetime.datetime) -> Optional[int]:
        if real_time is None:
            return None
        else:
            datetime_delta = real_time - self.base_time
            return datetime_delta.days * 24 * 60 + datetime_delta.seconds // 60

    def relative_to_real_time(self, relative_time: int) -> datetime.datetime:
        return self.base_time + datetime.timedelta(minutes=relative_time)

    @property
    def solution_dict(self) -> dict:
        if not self.solution:
            return {}

        return self._parse_result_to_dict()


class DirectModel(BaseModelWrapper):
    """ 基础求解模型的包装类 """

    def _main_solve(self) -> cp.CpoSolveResult:
        m = Model(self.token, self.data)
        self.model = m
        sol = m.solve(time_limit=self.data['args']['time_limit'], workers=8)
        return sol


class NewCascadeModel(Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manually_abort_flag = False
        self.is_finished = False

    def _pre_processing(self):
        self.objectives_list = ["priority_process_delay_time"]
        self.kpis_list = ["normal_process_delay_time", "advanced_time", "priority_business_delay_number",
                          "all_business_delay_number"]

    def _create_model(self) -> None:
        """ 建立模型：初始化变量，添加约束，添加目标和KPI """
        self._init_vars()
        self._add_order_constraints()
        self._add_device_no_overlap_constraints()
        self._add_resource_no_overlap_constraints()

    def unit_solve(self, objectives_list: List[str],
                   kpis_list: List[str],
                   time_limit: int = 30,
                   workers: int = 2,
                   tolerance: float = 0.0,
                   prev_obj_name: Optional[str] = None,
                   debug: bool = False):

        if self.manually_abort_flag:
            raise AbortedException('手动中断')

        self.objectives_list = objectives_list
        self.kpis_list = kpis_list

        try:
            self._add_objectives()
        except NoObjectiveException:
            return
        self._add_kpis()

        params = cp.CpoParameters()
        params.TimeLimit = time_limit
        params.LogVerbosity = 'Terse'
        params.Workers = workers
        params.RelativeOptimalityTolerance = tolerance

        self.solver = self.model.create_solver(params=params)
        self._add_callbacks()

        if self.solution is not None:
            prev_obj = Objectives(self.data_loader)[prev_obj_name]
            if prev_obj is not None:
                self.model.add(prev_obj <= self.solution.get_objective_value())
            self.model.set_starting_point(self.solution.get_solution())

        self.solution = self.solver.solve()
        if self.solution.solve_status == 'Infeasible':
            raise NoSolutionException()
        
        if self.solution.solve_status == 'Unknown' and self.solution.fail_status == 'SearchStoppedByLimit':
            raise NoSolutionException()
        
        # 重要更新，在级联求解的模式下，放弃了对结果的筛选功能。因为对每个目标单独求解的前提是上一个目标的结果已经最优。后面的目标等待后续继续优化

    def solve(self,
              time_limit: int = 30,
              workers: int = DEFAULT_WORKERS,
              tolerance: float = None,
              debug: bool = False,
              only_one_result: bool = False,
              *args,
              **kwargs) -> cp.CpoSolveResult:
        """ 求解模型 """
        self._create_model()
        try:
            # 1. 紧急订单
            self.logger.info("Solving critical processes: ")
            self.unit_solve(objectives_list=["critical_process_delay_time"],
                            kpis_list=["priority_process_delay_time", "normal_process_delay_time",
                                       "advanced_time",
                                       "priority_business_delay_number", "all_business_delay_number"],
                            time_limit=int(time_limit * 0.2),
                            tolerance=0.05,
                            workers=workers,
                            debug=debug)

            # 2. 优先订单
            self.logger.info("Solving priority processes: ")
            self.unit_solve(objectives_list=["priority_process_delay_time"],
                            kpis_list=["critical_process_delay_time", "normal_process_delay_time",
                                       "advanced_time",
                                       "priority_business_delay_number", "all_business_delay_number"],
                            time_limit=int(time_limit * 0.3),
                            tolerance=0.05,
                            prev_obj_name="critical_process_delay_time",
                            workers=workers,
                            debug=debug)

            # 3. 普通订单
            self.logger.info("Solving normal processes: ")
            self.unit_solve(objectives_list=["normal_process_delay_time"],
                            kpis_list=["critical_process_delay_time", "priority_process_delay_time",
                                       "advanced_time",
                                       "priority_business_delay_number", "all_business_delay_number"],
                            time_limit=int(time_limit * 0.4),
                            tolerance=0.1,
                            prev_obj_name="priority_process_delay_time",
                            workers=workers,
                            debug=debug)

            # 4. 提前时间
            self.logger.info("Solving advanced time: ")
            self.unit_solve(objectives_list=["advanced_time"],
                            kpis_list=["critical_process_delay_time", "priority_process_delay_time",
                                       "normal_process_delay_time", "priority_business_delay_number",
                                       "all_business_delay_number"],
                            time_limit=int(time_limit * 0.1),
                            tolerance=0.1,
                            prev_obj_name="normal_process_delay_time",
                            workers=workers,
                            debug=debug)
        except (AbortedException, NoSolutionException):
            pass

        self.is_finished = True  # 标记求解已经完成，用于检测是否abort成功
        return self.solution

    def abort_solving(self) -> bool:
        self.manually_abort_flag = True
        if self.solver is not None:
            self.solver.agent.abort_search()
        time.sleep(3)
        return self.is_finished


class CascadeModelWrapper(BaseModelWrapper):
    """ 基础求解模型的包装类 """

    def _main_solve(self) -> cp.CpoSolveResult:
        m = NewCascadeModel(self.token, self.data)
        self.model = m
        sol = m.solve(time_limit=self.data['args']['time_limit'])
        return sol

    def build_and_export(self, file_path: str):
        """ 实例化内部模型并执行导出 """
        # 注意：这里实例化的是 NewCascadeModel，因为它包含了你最新的业务逻辑
        m = NewCascadeModel(self.token, self.data)
        return m.export_model(file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the planning algorithm with a given input JSON file.")
    parser.add_argument("input_file", type=str, help="Path to the input JSON file.")
    args = parser.parse_args()

    # Configure logging
    try:
        with open('logging_config.json', 'r') as f:
            logging_config = json.load(f)
        logging.config.dictConfig(logging_config)
    except FileNotFoundError:
        logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
        logging.warning("logging_config.json not found. Using default logging configuration.")
    except Exception as e:
        logging.error(f"Error loading logging_config.json: {e}. Using default logging configuration.")
        logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

    main_logger = logging.getLogger("MainRunner")

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Extract token from input_data, or generate a default one
        token = input_data.get('token', f"manual_run_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        main_logger.info(f"Starting planning for token: {token} with input file: {args.input_file}")

        # Instantiate the model wrapper
        model_wrapper = CascadeModelWrapper(token, input_data)

        # Solve the model
        solution = model_wrapper.solve()

        if solution:
            main_logger.info(f"Planning completed successfully for token: {token}")
            # You can add logic here to save the solution to a file if needed
            output_filename = f"solution_{token}.json"
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                json.dump(solution, outfile, indent=4)
            main_logger.info(f"Solution saved to {output_filename}")
        else:
            main_logger.warning(f"No solution found for token: {token}")

    except FileNotFoundError:
        main_logger.error(f"Input file not found: {args.input_file}")
    except json.JSONDecodeError:
        main_logger.error(f"Invalid JSON format in input file: {args.input_file}")
    except Exception as e:
        main_logger.exception(f"An error occurred during planning for token: {token}")

# ==========================================
# File: AS/algorithm_server.py
# ==========================================

AS_MODEL = CascadeModelWrapper


class AlgorithmServer(SubServer):
    def planning(self, token, data, solution_dict):
        factory_code = data['args']['factory_code']

        # 暂时都改用一步求解
        m = AS_MODEL(token, data)
        self.ongoing_model = m

        sol = m.solve()
        self.logger.info(f'[{token}] Model solved.')
        solution_dict.update({
            'state': 'OK',
            'solutions': sol
        })

        self.save_solution(token, factory_code, solution_dict)
