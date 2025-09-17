# pylint: skip-file
"""通用的操作函数."""
import json
import os
import pathlib
import subprocess
from datetime import datetime
from typing import Union


def parse_value(value: str, value_type: str) -> Union[int, float, str, bool, list]:
    """解析数值.

    Args:
        value: 解析的数据
        value_type: 数据类型.

    Returns:
        Union[int, float, str, bool, list]: 解析后的数据.
    """
    int_type_flag = "U1,U4,I4"
    float_type_flag = "F4"
    bool_type_flag = "BOOL"
    list_type_flag = "ARRAY"
    binary_type_flag = "BINARY"

    if value_type in int_type_flag:
        return int(value) if value else 0
    elif value_type in float_type_flag:
        return float(value) if value else 0.0
    elif value_type in bool_type_flag:
        if value in ["false", "False", "FALSE", 0, "0", "", None]:
            return False
        return True
    elif value_type in list_type_flag:
        if isinstance(value, str):
            return json.loads(value) if value else []
        return value
    elif value_type in binary_type_flag:
        return int(value) if value else 0
    else:
        return value


def set_date_time(modify_time_str) -> bool:
    """设置windows系统日期和时间.

    Args:
        modify_time_str (str): 要修改的时间字符串.

    Returns:
        bool: 修改成功或者失败.
    """
    date_time = datetime.strptime(modify_time_str, "%Y%m%d%H%M%S%f")
    date_command = f"date {date_time.year}-{date_time.month}-{date_time.day}"
    result_date = subprocess.run(date_command, shell=True, check=False)
    time_command = f"time {date_time.hour}:{date_time.minute}:{date_time.second}"
    result_time = subprocess.run(time_command, shell=True, check=False)
    if result_date.returncode == 0 and result_time.returncode == 0:
        return True
    return False


def custom_log_name(log_path: str) -> str:
    """自定义新生成的日志名称.

    Args:
        log_path: 原始的日志文件路径.

    Returns:
        str: 新生成的自定义日志文件路径.
    """
    _, suffix, date_str, *__ = log_path.split(".")
    new_log_path = f"{os.getcwd()}/log/all_{date_str}.{suffix}"
    return new_log_path


def create_log_dir():
    """判断log目录是否存在, 不存在就创建."""
    log_dir = pathlib.Path(f"{os.getcwd()}/log")
    if not log_dir.exists():
        os.mkdir(log_dir)
