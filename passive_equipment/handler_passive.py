# pylint: skip-file
"""设备服务端处理器."""
import asyncio
import csv
import json
import logging
import os
import pathlib
import threading
import time
import socket
from logging.handlers import TimedRotatingFileHandler
from typing import Union, Optional, Callable

from inovance_tag.tag_communication import TagCommunication
from mitsubishi_plc.mitsubishi_plc import MitsubishiPlc
from modbus_api.modbus_api import ModbusApi
from mysql_api.mysql_database import MySQLDatabase
from secsgem.common import DeviceType
from secsgem.gem import CollectionEvent, GemEquipmentHandler, StatusVariable, RemoteCommand, Alarm, DataValue, \
    EquipmentConstant
from secsgem.secs.variables import U4, Array, String
from secsgem.hsms import HsmsSettings, HsmsConnectMode
from siemens_plc.s7_plc import S7PLC
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment.enum_sece_data_type import EnumSecsDataType
from passive_equipment.handler_config import HandlerConfig


class HandlerPassive(GemEquipmentHandler):
    """Passive equipment handler class."""

    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

    def __init__(self, open_flag: bool = False, **kwargs):
        logging.basicConfig(level=logging.INFO, encoding="UTF-8", format=self.LOG_FORMAT)

        self.kwargs = kwargs

        self._open_flag = open_flag  # 是否打开监控下位机的线程
        self._file_handler = None  # 保存日志的处理器
        self._mysql = None  # 数据库实例对象

        self.logger = logging.getLogger(__name__)  # handler_passive 日志器

        self.config_instance = HandlerConfig(self.get_config_path())  # 配置文件实例对象
        self.config = self.config_instance.config_data

        self.lower_computer_instance = self._get_lower_computer_instance()  # 下位机实例

        hsms_settings = HsmsSettings(
            address=self.config_instance.get_config_value("secs_ip", "127.0.0.1", parent_name="secs_conf"),
            port=self.config_instance.get_config_value("secs_port", 5000, parent_name="secs_conf"),
            connect_mode=getattr(HsmsConnectMode, "PASSIVE"),
            device_type=DeviceType.EQUIPMENT
        )  # high speed message server 配置

        super().__init__(settings=hsms_settings)
        self.model_name = self.config_instance.get_config_value("model_name", parent_name="secs_conf")
        self.software_version = self.config_instance.get_config_value("software_version", parent_name="secs_conf")
        self.recipes = self.config_instance.get_config_value("recipes", {})  # 获取所有上传过的配方信息
        self.alarm_id = U4(0)  # 保存报警id
        self.alarm_text = ""  # 保存报警内容

        self._initial_log_config()
        self._initial_evnet()
        self._initial_status_variable()
        self._initial_data_value()
        self._initial_equipment_constant()
        self._initial_remote_command()
        self._initial_alarm()

        self._enable_equipment()  # 启动设备端服务器
        self._monitor_lower_computer_thread()

    def _monitor_lower_computer_thread(self):
        """监控下位机的线程."""
        if self._open_flag:
            self.logger.info("打开监控下位机的线程.")
            if isinstance(self.lower_computer_instance, CygSocketServerAsyncio):
                self.logger.info("下位机是 Socket")
                self.start_monitor_labview_thread(self.operate_func_socket)
            else:
                if self.lower_computer_instance.communication_open():
                    self.logger.info("连接 %s 下位机成功, ip: %s", self.lower_computer_type,
                                     self.lower_computer_instance.ip)
                else:
                    self.logger.info("连接 %s 下位机失败, ip: %s", self.lower_computer_type,
                                     self.lower_computer_instance.ip)

                self.mes_heart_thread()
                self.control_state_thread()
                self.machine_state_thread()
                self.signal_thread()
        else:
            self.logger.info("不打开监控下位机的线程.")

    def start_monitor_labview_thread(self, func: Callable):
        """启动供下位机连接的socket服务.

        Args:
            func: 执行操作的函数.
        """
        self.lower_computer_instance.operations_return_data = func

        def run_socket_server():
            asyncio.run(self.lower_computer_instance.run_socket_server())

        thread = threading.Thread(target=run_socket_server, daemon=True)  # 主程序结束这个线程也结束
        thread.start()

    @property
    def mysql(self) -> MySQLDatabase:
        """数据库实例对象.

        Returns:
            MySQLDatabase: 返回操作 Mysql 数据的实例对象.
        """
        if self._mysql:
            return self._mysql
        if self.config["lower_computer"].get("local_database", False):
            self._mysql = MySQLDatabase(
                self.get_ec_value_with_name("mysql_user_name"),
                self.get_ec_value_with_name("mysql_password"),
                host=self.get_ec_value_with_name("mysql_host")
            )
            self._mysql.logger.addHandler(self.file_handler)
        return self._mysql

    @mysql.setter
    def mysql(self, value: MySQLDatabase):
        """设置数据库实例对象.

        Args:
            value: 数据库 MySQLDatabase实例.
        """
        if not isinstance(value, MySQLDatabase) and value is not None:
            raise ValueError("mysql 必须是一个 MySQLDatabase 实例或 None")
        self._mysql = value

    @property
    def lower_computer_type(self) -> str:
        """获取下位机类型."""
        return self.config_instance.get_config_value("type", parent_name="lower_computer")

    @property
    def file_handler(self) -> TimedRotatingFileHandler:
        """设置保存日志的处理器, 每隔一天自动生成一个日志文件.

        Returns:
            TimedRotatingFileHandler: 返回 TimedRotatingFileHandler 日志处理器.
        """
        if self._file_handler is None:
            logging.basicConfig(level=logging.INFO, encoding="UTF-8", format=self.LOG_FORMAT)
            self._file_handler = TimedRotatingFileHandler(
                f"{os.getcwd()}/log/equipment_sequence.log",
                when="D", interval=1, backupCount=10, encoding="UTF-8"
            )
            self._file_handler.namer = self._custom_log_namer
            self._file_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
        return self._file_handler

    @staticmethod
    def _custom_log_namer(log_path: str):
        """自定义新生成的日志名称.

        Args:
            log_path: 原始的日志文件路径.

        Returns:
            str: 新生成的自定义日志文件路径.
        """
        _, suffix, date_str = log_path.split(".")
        new_log_path = f"{os.getcwd()}/log/equipment_sequence_{date_str}.{suffix}"
        return new_log_path

    @staticmethod
    def _create_log_dir():
        """判断log目录是否存在, 不存在就创建."""
        log_dir = pathlib.Path(f"{os.getcwd()}/log")
        if not log_dir.exists():
            os.mkdir(log_dir)

    @staticmethod
    def _get_alarm_path() -> Optional[str]:
        """获取报警表格的路径.

        Returns:
            Optional[str]: 返回报警表格路径, 不存在返回None.
        """
        alarm_path = os.path.join(os.getcwd(), "alarm.csv")
        if os.path.exists(alarm_path):
            return alarm_path
        return None

    def _initial_log_config(self) -> None:
        """日志配置."""
        self._create_log_dir()
        self.protocol.communication_logger.addHandler(self.file_handler)  # secs 日志保存本地
        self.logger.addHandler(self.file_handler)  # handler_passive 日志保存本地
        self.lower_computer_instance.logger.addHandler(self.file_handler)  # 下位机日志保存本地

    def _initial_evnet(self):
        """加载定义好的事件."""
        collection_events = self.config.get("collection_events", {})
        for event_name, event_info in collection_events.items():
            self.collection_events.update({
                event_name: CollectionEvent(name=event_name, data_values=[], **event_info)
            })

    def _initial_status_variable(self):
        """加载定义好的变量."""
        status_variables = self.config.get("status_variable", {})
        for sv_name, sv_info in status_variables.items():
            sv_id = sv_info.get("svid")
            value_type_str = sv_info.get("value_type")
            value_type = getattr(EnumSecsDataType, value_type_str).value
            sv_info["value_type"] = value_type
            self.status_variables.update({sv_id: StatusVariable(name=sv_name, **sv_info)})
            sv_info["value_type"] = value_type_str

    def _initial_data_value(self):
        """加载定义好的 data value."""
        data_values = self.config.get("data_values", {})
        for data_name, data_info in data_values.items():
            data_id = data_info.get("dvid")
            value_type_str = data_info.get("value_type")
            value_type = getattr(EnumSecsDataType, value_type_str).value
            data_info["value_type"] = value_type
            self.data_values.update({data_id: DataValue(name=data_name, **data_info)})
            data_info["value_type"] = value_type_str

    def _initial_equipment_constant(self):
        """加载定义好的常量."""
        equipment_constants = self.config.get("equipment_constant", {})
        for ec_name, ec_info in equipment_constants.items():
            ec_id = ec_info.get("ecid")
            value_type_str = ec_info.get("value_type")
            value_type = getattr(EnumSecsDataType, value_type_str).value
            ec_info["value_type"] = value_type
            ec_info.update({"min_value": 0, "max_value": 0})
            self.equipment_constants.update({ec_id: EquipmentConstant(name=ec_name, **ec_info)})
            ec_info["value_type"] = value_type_str

    def _initial_remote_command(self):
        """加载定义好的远程命令."""
        remote_commands = self.config.get("remote_commands", {})
        for rc_name, rc_info in remote_commands.items():
            ce_id = rc_info.get("ce_id")
            self.remote_commands.update({rc_name: RemoteCommand(name=rc_name, ce_finished=ce_id, **rc_info)})

    def _initial_alarm(self):
        """加载定义好的报警."""
        if alarm_path := self._get_alarm_path():
            with pathlib.Path(alarm_path).open("r+") as file:  # pylint: disable=W1514
                csv_reader = csv.reader(file)
                next(csv_reader)
                for row in csv_reader:
                    alarm_id, alarm_name, alarm_text, alarm_code, ce_on, ce_off, *_ = row
                    self.alarms.update({
                        alarm_id: Alarm(alarm_id, alarm_name, alarm_text, int(alarm_code), ce_on, ce_off)
                    })

    def _enable_equipment(self):
        """启动监控EAP连接的服务."""
        self.enable()  # 设备和host通讯
        self.logger.info("Passive 服务已启动, 地址: %s %s!", self.settings.address, self.settings.port)

    def _get_lower_computer_instance(self) -> Union[
        S7PLC, TagCommunication, MitsubishiPlc, ModbusApi, CygSocketServerAsyncio]:
        """获取下位机实例."""
        instance_params = self.config["lower_computer"][self.lower_computer_type]
        instance_map = {
            "snap7": S7PLC, "tag": TagCommunication,
            "mitsubishi": MitsubishiPlc, "modbus": ModbusApi,
            "socket": CygSocketServerAsyncio
        }
        instance = instance_map[self.lower_computer_type](**instance_params)
        return instance

    def _get_sv_id_with_name(self, sv_name: str) -> Optional[int]:
        """根据变量名获取变量id.

        Args:
            sv_name: 变量名称.

        Returns:
            Optional[int]: 返回变量id, 没有此变量返回None.
        """
        if sv_info := self.config_instance.get_config_value(sv_name, parent_name="status_variable"):
            return sv_info["svid"]
        return None

    def _get_dv_id_with_name(self, dv_name: str) -> Optional[int]:
        """根据data名获取data id.

        Args:
            dv_name: 变量名称.

        Returns:
            Optional[int]: 返回data id, 没有此data返回None.
        """
        if sv_info := self.config_instance.get_config_value("data_values").get(dv_name):
            return sv_info["dvid"]
        return None

    def _get_ec_id_with_name(self, ec_name: str) -> Optional[int]:
        """根据常量名获取常量 id.

        Args:
            ec_name: 常量名称.

        Returns:
            Optional[int]: 返回常量 id, 没有此常量返回None.
        """
        if ec_info := self.config_instance.get_config_value("equipment_constant").get(ec_name):
            return ec_info["ecid"]
        return None

    def set_sv_value_with_name(self, sv_name: str, sv_value: Union[str, int, float, list]):
        """设置指定 sv 变量的值.

        Args:
            sv_name (str): 变量名称.
            sv_value (Union[str, int, float, list]): 要设定的值.
        """
        self.logger.info("设置 sv 值, %s = %s", sv_name, sv_value)
        self.status_variables.get(self._get_sv_id_with_name(sv_name)).value = sv_value

    def set_dv_value_with_name(self, dv_name: str, dv_value: Union[str, int, float, list]):
        """设置指定 dv 变量的值.

        Args:
            dv_name (str): dv 变量名称.
            dv_value (Union[str, int, float, list]): 要设定的值.
        """
        self.logger.info("设置 dv 值, %s = %s", dv_name, dv_value)
        self.data_values.get(self._get_dv_id_with_name(dv_name)).value = dv_value

    def set_ec_value_with_name(self, ec_name: str, ec_value: Union[str, int, float]):
        """设置指定 ec 变量的值.

        Args:
            ec_name (str): ec 变量名称.
            ec_value (Union[str, int, float]): 要设定的 ec 的值.
        """
        self.equipment_constants.get(self._get_ec_id_with_name(ec_name)).value = ec_value

    def get_sv_value_with_name(self, sv_name: str) -> Union[int, str, bool, list, float]:
        """根据变量 sv 名获取变量 sv 值.

        Args:
            sv_name: 变量名称.

        Returns:
            Union[int, str, bool, list, float]: 返回对应变量的值.
        """
        if sv_instance := self.status_variables.get(self._get_sv_id_with_name(sv_name)):
            return sv_instance.value
        return None

    def get_dv_value_with_name(self, dv_name: str) -> Union[int, str, bool, list, float]:
        """根据变量 dv 名获取变量 dv 值..

        Args:
            dv_name: dv 名称.

        Returns:
            Union[int, str, bool, list, float]: 返回对应 dv 变量的值.
        """
        if dv_instance := self.data_values.get(self._get_dv_id_with_name(dv_name)):
            return dv_instance.value
        return None

    def get_ec_value_with_name(self, ec_name: str) -> Union[int, str, bool, list, float]:
        """根据常量名获取常量值.

        Args:
            ec_name: 常量名称.

        Returns:
            Union[int, str, bool, list, float]: 返回对应常量的值.
        """
        if ec_instance := self.equipment_constants.get(self._get_ec_id_with_name(ec_name)):
            return ec_instance.value
        return None

    def get_config_path(self) -> str:
        """获取配置文件绝对路径."""
        relative_path = "/".join(self.__module__.split("."))
        config_file_path = os.path.join(os.getcwd(), f"{relative_path}.json")
        self.logger.info("配置文件路径: %s", config_file_path)
        return config_file_path

    def send_s6f11(self, event_name):
        """给EAP发送S6F11事件.

        Args:
            event_name (str): 事件名称.
        """

        def _ce_sender():
            reports = []
            event = self.collection_events.get(event_name)
            # noinspection PyUnresolvedReferences
            link_reports = event.link_reports
            for report_id, sv_ids in link_reports.items():
                variables = []
                for sv_id in sv_ids:
                    if sv_id in self.status_variables:
                        sv_instance: StatusVariable = self.status_variables.get(sv_id)
                    else:
                        sv_instance: DataValue = self.data_values.get(sv_id)
                    if issubclass(sv_instance.value_type, Array):
                        if sv_instance.base_value_type == "ASCII":
                            value = Array(String, sv_instance.value)
                        else:
                            value = Array(U4, sv_instance.value)
                    else:
                        value = sv_instance.value_type(sv_instance.value)
                    variables.append(value)
                reports.append({"RPTID": U4(report_id), "V": variables})

            self.send_and_waitfor_response(
                self.stream_function(6, 11)({"DATAID": 1, "CEID": event.ceid, "RPT": reports})
            )

        threading.Thread(target=_ce_sender, daemon=True).start()

    def mes_heart_thread(self):
        """plc mes 心跳的线程."""

        def _mes_heart():
            """Mes 心跳."""
            address_info = self.config_instance.get_signal_address_info("mes_heart", self.lower_computer_type)
            while True:
                try:
                    self.lower_computer_instance.execute_write(**address_info, data=True)
                    time.sleep(self.get_ec_value_with_name("mes_heart_gap"))
                    self.lower_computer_instance.execute_write(**address_info, data=False)
                    time.sleep(self.get_ec_value_with_name("mes_heart_gap"))
                except Exception as e:
                    self.logger.warning("写入心跳失败, 错误信息: %s", str(e))
                    if self.lower_computer_instance.communication_open():
                        self.logger.info("Plc重新连接成功.")
                    else:
                        self.wait_time(30)
                        self.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

        threading.Thread(target=_mes_heart, daemon=True, name="mes_heart_thread").start()

    def control_state_thread(self):
        """plc 监控控制状态变化的线程."""

        def _control_state():
            """监控控制状态变化."""
            address_info = self.config_instance.get_signal_address_info("control_state", self.lower_computer_type)
            while True:
                try:
                    current_control_state = self.lower_computer_instance.execute_read(**address_info, save_log=False)
                    if address_info["data_type"] == "bool":
                        current_control_state = 2 if current_control_state else 1
                    if current_control_state != self.get_sv_value_with_name("current_control_state"):
                        self.set_sv_value_with_name("current_control_state", current_control_state)
                        self.send_s6f11("control_state_change")
                except Exception as e:
                    self.set_sv_value_with_name("current_control_state", 0)
                    self.send_s6f11("control_state_change")
                    self.logger.warning("读取plc控制状态失败, 错误信息: %s", str(e))
                    if self.lower_computer_instance.communication_open():
                        self.logger.info("Plc重新连接成功.")
                    else:
                        self.wait_time(30)
                        self.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

        threading.Thread(target=_control_state, daemon=True, name="control_state_thread").start()

    def machine_state_thread(self):
        """Snap7 plc 运行状态变化的线程."""

        def _machine_state():
            """监控运行状态变化."""
            address_info = self.config_instance.get_signal_address_info("machine_state", self.lower_computer_type)
            while True:
                try:
                    machine_state = self.lower_computer_instance.execute_read(**address_info, save_log=False)
                    if machine_state != self.get_sv_value_with_name("current_machine_state"):
                        alarm_state = self.get_ec_value_with_name("alarm_state")
                        if machine_state == alarm_state:
                            self.set_clear_alarm(self.get_ec_value_with_name("occur_alarm_code"))
                        elif self.get_sv_value_with_name("current_machine_state") == alarm_state:
                            self.set_clear_alarm(self.get_ec_value_with_name("clear_alarm_code"))
                        self.set_sv_value_with_name("current_machine_state", machine_state)
                        self.send_s6f11("machine_state_change")
                except Exception as e:
                    self.set_sv_value_with_name("current_control_state", 0)
                    self.send_s6f11("control_state_change")
                    self.logger.warning("读取plc运行状态失败, 错误信息: %s", str(e))
                    if self.lower_computer_instance.communication_open():
                        self.logger.info("Plc重新连接成功.")
                    else:
                        self.wait_time(30)
                        self.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

        threading.Thread(target=_machine_state, daemon=True, name="machine_state_thread").start()

    def set_clear_alarm(self, alarm_code: int):
        """通过S5F1发送报警和解除报警.

        Args:
            alarm_code: 报警 code, 2: 报警, 9: 清除报警.
        """
        address_info = self.config_instance.get_signal_address_info("alarm_id", self.lower_computer_type)
        if alarm_code == self.get_ec_value_with_name("occur_alarm_code"):
            alarm_id = self.lower_computer_instance.execute_read(**address_info, save_log=False)
            self.logger.info("出现报警, 报警id: %s")
            try:
                self.alarm_id = U4(alarm_id)
                if alarm_text := self.alarms.get(str(alarm_id)):
                    self.alarm_text = alarm_text
                else:
                    self.alarm_text = "Alarm is not defined."
            except ValueError:
                self.logger.warning("报警id非法, 报警id: %s")
                self.alarm_id = U4(0)
                self.alarm_text = "Alarm is not defined."

        def _alarm_sender(_alarm_code):
            """发送报警和解除报警."""
            self.send_and_waitfor_response(
                self.stream_function(5, 1)({
                    "ALCD": _alarm_code, "ALID": self.alarm_id, "ALTX": self.alarm_text
                })
            )

        threading.Thread(target=_alarm_sender, args=(alarm_code,), daemon=True).start()

    def signal_thread(self):
        """监控 plc 信号的线程."""
        signal_dict = self.config_instance.get_config_value("signal_address", {})
        for signal_name, signal_info in signal_dict.items():
            if signal_info.get("loop", False):  # 实时监控的信号才会创建线程
                threading.Thread(
                    target=self.monitor_plc_address, daemon=True, args=(signal_name,), name=signal_name
                ).start()

    def monitor_plc_address(self, signal_name: str):
        """实时监控信号.

        Args:
            signal_name: 信号名称.
        """
        value = self.config_instance.get_monitor_signal_value(signal_name)
        address_info = self.config_instance.get_signal_address_info(signal_name, self.lower_computer_type)
        while True:
            current_value = self.lower_computer_instance.execute_read(**address_info, save_log=False)
            if current_value == value:
                self.get_signal_to_sequence(signal_name)
            time.sleep(1)

    def get_signal_to_sequence(self, signal_name: str):
        """监控到信号执行 call_backs.

        Args:
            signal_name: 信号名称.
        """
        _ = "=" * 40
        self.logger.info("%s 监控到 %s 信号 %s", _, signal_name, _)
        self.execute_call_backs(self.config_instance.get_call_backs(signal_name))
        self.logger.info("%s %s 结束 %s", _, signal_name, _)

    def execute_call_backs(self, call_backs: list):
        """根据操作列表执行具体的操作.

        Args:
            call_backs: 要执行动作的信息列表, 按照列表顺序执行.
        """
        for i, call_back in enumerate(call_backs, 1):
            description = call_back.get("description")
            self.logger.info("%s 第 %s 步: %s %s", "-" * 30, i, description, "-" * 30)
            operation_func = getattr(self, call_back.get(f"operation_func"))
            operation_func(call_back=call_back)
            self._is_send_event(call_back.get("event_name"))
            self.logger.info("%s %s 结束 %s", "-" * 30, description, "-" * 30)

    def _is_send_event(self, event_name: str = None):
        """判断是否要发送事件.

        Arg:
            event_name: 要发送的事件名称, 默认 None.
        """
        if event_name:
            self.send_s6f11(event_name)

    def update_dv_specify_value(self, call_back: dict):
        """更新 dv 指定值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        value = call_back.get("value")
        dv_name = call_back.get("dv_name")
        self.set_dv_value_with_name(dv_name, value)
        self.logger.info("当前 %s 值: %s", dv_name, value)

    def update_sv_specify_value(self, call_back: dict):
        """更新 sv 指定值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        value = call_back.get("value")
        sv_name = call_back.get("sv_name")
        self.set_sv_value_with_name(sv_name, value)
        self.logger.info("当前 %s 值: %s", sv_name, value)

    def read_update_sv(self, call_back: dict):
        """读取 plc 数据更新 sv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        sv_name = call_back.get("sv_name")
        address_info = self.config_instance.get_call_back_address_info(call_back, self.lower_computer_type)
        plc_value = self.lower_computer_instance.execute_read(**address_info)
        self.set_sv_value_with_name(sv_name, plc_value)
        self.logger.info("当前 %s 值: %s", sv_name, plc_value)

    def read_update_dv(self, call_back: dict):
        """读取 plc 数据更新 dv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        dv_name = call_back.get("dv_name")
        address_info = self.config_instance.get_call_back_address_info(call_back, self.lower_computer_type)
        plc_value = self.lower_computer_instance.execute_read(**address_info)
        self.set_dv_value_with_name(dv_name, plc_value)
        self.logger.info("当前 %s 值: %s", dv_name, plc_value)

    def read_multiple_update_dv_snap7(self, call_back: dict):
        """读取 Snap7 plc 多个数据更新 dv 值.
        Args:
            call_back: 要执行的 call_back 信息.
        """
        value_list = []
        count_num = call_back["count_num"]
        gap = call_back.get("gap", 1)
        start_address = call_back.get("address")
        for i in range(count_num):
            address_info = {
                "address": start_address + i * gap,
                "data_type": call_back.get("data_type"),
                "db_num": self.get_ec_value_with_name("db_num"),
                "size": call_back.get("size", 1),
                "bit_index": call_back.get("bit_index", 0)
            }
            plc_value = self.lower_computer_instance.execute_read(**address_info)
            value_list.append(plc_value)
        self.set_dv_value_with_name(call_back.get("dv_name"), value_list)
        self.logger.info("当前 dv %s 值 %s", call_back.get("dv_name"), value_list)

    def write_sv_value(self, call_back: dict):
        """向 plc 地址写入 sv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        sv_value = self.get_sv_value_with_name(call_back.get("sv_name"))
        self._write_value(call_back, sv_value)

    def write_dv_value(self, call_back: dict):
        """向 plc 地址写入 dv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        dv_value = self.get_dv_value_with_name(call_back.get("dv_name"))
        self._write_value(call_back, dv_value)

    def write_multiple_dv_value_snap7(self, call_back: dict):
        """向 snap7 plc 地址写入 dv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        value_list = self.get_dv_value_with_name(call_back.get("dv_name"))
        gap = call_back.get("gap", 1)
        for i, value in enumerate(value_list):
            _call_back = {
                "address": call_back.get("address") + gap * i,
                "data_type": call_back.get("data_type"),
                "db_num": self.get_ec_value_with_name("db_num"),
                "size": call_back.get("size", 2),
                "bit_index": call_back.get("bit_index", 0)
            }
            self._write_value(_call_back, value)

    def write_specify_value(self, call_back: dict):
        """向 plc 地址写入指定值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        value = call_back.get("value")
        self._write_value(call_back, value)

    def _write_value(self, call_back: dict, value: Union[int, float, bool]):
        """向 snap7 plc 地址写入指定值.

        Args:
            call_back: 要执行的 call_back 信息.
            value: 要写入的值.
        """
        # 如果有前提条件, 要先判断前提条件再写入
        if call_back.get("premise_address"):
            premise_value = call_back.get("premise_value")
            wait_time = call_back.get("wait_time", 600000)
            address_info = self.config_instance.get_call_back_address_info(call_back, self.lower_computer_type)
            while self.lower_computer_instance.execute_read(**address_info) != premise_value:
                self.logger.info("%s 前提条件值 != %s", call_back.get("description"), call_back.get("premise_value"))
                self.wait_time(1)
                wait_time -= 1
                if wait_time == 0:
                    break

        address_info = self.config_instance.get_call_back_address_info(call_back, self.lower_computer_type)
        self.lower_computer_instance.execute_write(**address_info, data=value)

        while self.lower_computer_instance.execute_read(**address_info) != value:
            self.logger.warning(f"向 %s 写入 %s 失败", json.dumps(address_info), value)
            self.lower_computer_instance.execute_write(**address_info, data=value)

    def wait_time(self, wait_time: int):
        """等待时间.

        Args:
            wait_time: 等待时间.
        """
        while True:
            time.sleep(1)
            self.logger.info("等待 %s 秒", 1)
            wait_time -= 1
            if wait_time == 0:
                break

    def send_data_to_socket_client(self, client_ip: str, data: str) -> bool:
        """发送数据给下位机.

        Args:
            client_ip: 接收数据的设备ip地址.
            data: 要发送的数据

        Return:
            bool: 是否发送成功.
        """
        status = True
        client_connection = self.lower_computer_instance.clients.get(client_ip)
        if client_connection:
            byte_data = str(data).encode("UTF-8")
            asyncio.run(self.lower_computer_instance.socket_send(client_connection, byte_data))
        else:
            self.logger.warning("发送失败: %s 未连接", client_ip)
            status = False
        return status

    @staticmethod
    def send_data_to_socket_server(ip: str, port: int, data: str):
        """向服务端发送数据.

        Args:
            ip: Socket 服务端 ip.
            port: Socket 服务端 port.
            data: 要发送的数据.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        sock.sendall(data.encode("UTF-8"))

    def operate_func_socket(self, byte_data) -> str:
        """操作并返回数据."""
        str_data = byte_data.decode("UTF-8")  # 解析接收的下位机数据
        receive_dict = json.loads(str_data)
        for receive_key, receive_info in receive_dict.items():
            self.logger.info("收到的下位机关键字是: %s", receive_key)
            self.logger.info("收到的下位机关键字对应的数据是: %s", receive_info)
            getattr(self, receive_key)(receive_info)
        return "OK"

    def wait_eap_reply(self, call_back: dict):
        """等待 eap 反馈.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        wait_time = 0
        dv_name = call_back["param"]
        while self.get_dv_value_with_name(dv_name) is False:
            time.sleep(1)
            wait_time += 1
            self.logger.info("eap 未反馈 %s 请求, 已等待 %s 秒", dv_name, wait_time)

        self.set_dv_value_with_name(dv_name, False)

    def _on_rcmd_pp_select(self, recipe_name: str):
        """eap 切换配方.

        Args:
            recipe_name: 要切换的配方名称.
        """
        pp_select_recipe_id = self.config_instance.get_recipe_id_with_name(recipe_name)
        self.set_sv_value_with_name("pp_select_recipe_name", recipe_name)
        self.set_sv_value_with_name("pp_select_recipe_id", pp_select_recipe_id)

        # 执行切换配方操作
        if self._open_flag:
            self.execute_call_backs(self.config["signal_address"]["pp_select"]["call_back"])

        current_recipe_id = self.get_sv_value_with_name("current_recipe_id")
        current_recipe_name = self.config_instance.get_recipe_name_with_id(current_recipe_id)

        # 保存当前配方到本地
        self.set_sv_value_with_name("current_recipe_name", current_recipe_name)
        self.config_instance.update_config_sv_value("current_recipe_id", current_recipe_id)
        self.config_instance.update_config_sv_value("current_recipe_name", current_recipe_name)

    def _on_rcmd_new_lot(self, lot_name: str, lot_quality: int):
        """eap 开工单.

        Args:
            lot_name: 工单名称.
            lot_quality: 工单数量.
        """
        self.set_sv_value_with_name("current_lot_name", lot_name)
        self.set_sv_value_with_name("lot_quality", lot_quality)
        self.set_sv_value_with_name("current_lot_state", 1)
        if self._open_flag:
            self.execute_call_backs(self.config["signal_address"]["new_lot"]["call_backs"])

    def _on_s07f19(self, handler, packet):
        """查看设备的所有配方."""
        del handler
        return self.stream_function(7, 20)(self.config_instance.get_all_recipe_names())
