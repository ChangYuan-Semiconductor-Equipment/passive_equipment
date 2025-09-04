# pylint: skip-file
"""生成实例的方法集合."""
import os
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

from mysql_api.mysql_database import MySQLDatabase
from secsgem.common import DeviceType
from secsgem.hsms import HsmsSettings, HsmsConnectMode
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment import models_class


def get_mysql_secs() -> MySQLDatabase:
    """获取 secs 数据库实例对象.

    Returns:
        MySQLDatabase: 返回 secs 数据库实例对象.
    """
    return MySQLDatabase("root", "liuwei.520")


def get_socket_server():
    """获取 socket 服务端示例"""
    return CygSocketServerAsyncio("127.0.0.1", 1830)


def get_hsms_setting() -> HsmsSettings:
    """获取 HsmsSettings 实例对象.

    Returns:
        HsmsSettings: 返回 HsmsSettings 实例对象.
    """
    mysql = get_mysql_secs()
    secs_ip = mysql.query_data(models_class.EcList, {"ec_name": "secs_ip"})[0].get("value", "127.0.0.1")
    secs_port = mysql.query_data(models_class.EcList, {"ec_name": "secs_port"})[0].get("value", 5000)
    hsms_settings = HsmsSettings(
        address=secs_ip, port=int(secs_port),
        connect_mode=getattr(HsmsConnectMode, "PASSIVE"),
        device_type=DeviceType.EQUIPMENT
    )

    return hsms_settings


def get_time_rotating_handler() -> RotatingFileHandler:
    """获取自动生成日志的日志器实例.

    Returns:
        RotatingFileHandler: 返回自动生成日志的日志器实例.
    """
    return TimedRotatingFileHandler(
        f"{os.getcwd()}/log/all.log",
        when="D", interval=1, backupCount=10, encoding="UTF-8"
    )
