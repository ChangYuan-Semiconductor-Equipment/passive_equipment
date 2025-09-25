# pylint: skip-file
"""设备服务端处理器."""
import asyncio
import json
import logging
import threading
import time
import socket
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Union, Optional, Callable

from inovance_tag.tag_communication import TagCommunication
from mitsubishi_plc.mitsubishi_plc import MitsubishiPlc
from modbus_api.modbus_api import ModbusApi
from secsgem.gem import GemEquipmentHandler
from secsgem.secs.data_items import ACKC10
from secsgem.secs.data_items.tiack import TIACK
from secsgem.secs.functions import SecsS02F18
from secsgem.secs.variables import U4
from siemens_plc.s7_plc import S7PLC
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment.thread_methods import ThreadMethods

from passive_equipment import secs_config, factory, common_func, models_class, plc_address_operation


class HandlerPassive(GemEquipmentHandler):
    """Passive equipment handler class."""

    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    logging.basicConfig(level=logging.INFO, encoding="UTF-8", format=LOG_FORMAT)

    def __init__(self, equipment_name: str, plc: Union[TagCommunication, S7PLC, MitsubishiPlc, ModbusApi], open_flag: bool = False):
        """HandlerPassive 构造函数.

        Args:
            equipment_name: 设备名称.
            plc: plc 实例对象.
            open_flag: 是否打开监控 plc 的线程.
        """
        super().__init__(settings=factory.get_hsms_setting())

        self.logger = logging.getLogger(__name__)  # handler_passive 日志器
        self.mysql_secs = factory.get_mysql_secs()
        self.socket_server = factory.get_socket_server()
        self.plc = plc
        self.plc_type = equipment_name.split("_")[-1]

        self._file_handler = None  # 保存日志的处理器
        self._open_flag = open_flag  # 是否打开监控 plc 的线程
        self._initial_status_variable()
        self._initial_data_value()
        self._initial_event()
        self._initial_equipment_constant()
        self._initial_remote_command()
        self._initial_alarm()
        self._initial_log_config()

        self.thread_methods = ThreadMethods(self)

        self.enable_mes()  # 启动设备端服务器
        self._monitor_socket_thread()
        self._monitor_control_thread()

    def _monitor_socket_thread(self):
        """监控 socket 的线程."""
        self.__start_monitor_socket_thread(self.socket_server, self.operate_func_socket)

    def _monitor_control_thread(self):
        """监控 plc 的线程."""
        if self._open_flag:
            self.logger.info("打开监控 plc 的线程.")
            if self.plc.communication_open():
                self.logger.info("首次连接 plc 成功, ip: %s", self.plc.ip)
            else:
                self.logger.info("首次连接 %s plc 失败, ip: %s", self.plc.ip)
            self.__start_monitor_plc_thread()
        else:
            self.logger.info("不打开监控 plc 的线程.")

    def __start_monitor_socket_thread(self, control_instance: CygSocketServerAsyncio, func: Callable):
        """启动 socket 服务.

        Args:
            control_instance: CygSocketServerAsyncio 实例.
            func: 执行操作的函数.
        """
        control_instance.operations_return_data = func
        threading.Thread(target=self.thread_methods.run_socket_server, args=(control_instance,), daemon=True).start()

    def __start_monitor_plc_thread(self):
        """启动监控 plc 的线程."""
        threading.Thread(target=self.thread_methods.mes_heart, daemon=True).start()
        threading.Thread(target=self.thread_methods.control_state, daemon=True).start()
        threading.Thread(target=self.thread_methods.machine_state, daemon=True).start()
        threading.Thread(target=self.thread_methods.current_recipe_id, daemon=True).start()
        for signal_address_info in plc_address_operation.get_signal_address_list():
            if signal_address_info.get("state", False):  # 实时监控的信号才会创建线程
                threading.Thread(
                    target=self.thread_methods.monitor_plc_address, daemon=True,
                    args=(signal_address_info, ),
                ).start()

    @property
    def file_handler(self) -> TimedRotatingFileHandler:
        """设置保存日志的处理器, 每隔 24h 自动生成一个日志文件.

        Returns:
            TimedRotatingFileHandler: 返回 TimedRotatingFileHandler 日志处理器.
        """
        if self._file_handler is None:
            self._file_handler = factory.get_time_rotating_handler()
            self._file_handler.namer = common_func.custom_log_name
            self._file_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
        return self._file_handler

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

    def _initial_log_config(self) -> None:
        """日志配置."""
        common_func.create_log_dir()
        self.protocol.communication_logger.addHandler(self.file_handler)  # secs 日志保存到统一文件
        self.logger.addHandler(self.file_handler)  # handler_passive 日志保存到统一文件
        self.socket_server.logger.addHandler(self.file_handler)
        self.plc.logger.addHandler(self.file_handler)

    def _initial_status_variable(self):
        """加载定义好的 sv."""
        status_variables = secs_config.get_sv_list()
        for status_variable in status_variables:
            self.status_variables.update(status_variable)

    def _initial_data_value(self):
        """加载定义好的 data value."""
        data_values = secs_config.get_dv_list()
        for data_value in data_values:
            self.data_values.update(data_value)

    def _initial_equipment_constant(self):
        """加载定义好的常量."""
        equipment_consts = secs_config.get_ec_list()
        for equipment_const in equipment_consts:
            self.equipment_constants.update(equipment_const)

    def _initial_event(self):
        """加载定义好的事件."""
        events = secs_config.get_event_list()
        for event in events:
            self.collection_events.update(event)

    def _initial_remote_command(self):
        """加载定义好的远程命令."""
        remote_commands = secs_config.get_remote_command_list()
        for remote_command in remote_commands:
            self.remote_commands.update(remote_command)

    def _initial_alarm(self):
        """加载定义好的报警."""
        alarms = secs_config.get_alarm_list()
        for alarm in alarms:
            self.alarms.update(alarm)

    def enable_mes(self):
        """启动 EAP 连接的 MES服务."""
        self.enable()  # 设备和host通讯
        self.logger.info("Passive 服务已启动, 地址: %s %s!", self.settings.address, self.settings.port)

    def read_update_sv_or_dv(self, callback: dict):
        """读取 plc 数据更新 sv 值.

        Args:
            callback: 要执行的 callback 信息.
        """
        sv_or_dv_id = int(callback.get("associate_sv_or_dv"))
        count_num = callback.get("count_num", 1)
        address_info = plc_address_operation.get_address_info(self.plc_type, callback)
        if count_num == 1:
            plc_value = self.plc.execute_read(**address_info)
        else:
            read_multiple_value_func = getattr(self, f"read_multiple_value_{self.plc_type}")
            plc_value = read_multiple_value_func(callback)
        self.set_sv_or_dv_value_with_id(sv_or_dv_id, plc_value)

    def write_clean_signal_value(self, address_info: dict, value: int):
        """向 plc 地址写入清除信号值.

        Args:
            address_info: 要写入的地址信息.
            value: 要写入的值.
        """
        address_info_write = plc_address_operation.get_address_info(self.plc_type, address_info)
        self.plc.execute_write(**address_info_write, value=value)

    def write_sv_or_dv_value(self, callback: dict):
        """向 plc 地址写入 sv 或 dv 值.

        Args:
            callback: 要执行的 callback 信息.
        """
        sv_or_dv_id = int(callback.get("associate_sv_or_dv"))
        count_num = callback.get("count_num", 1)
        value = self.get_sv_or_dv_value_with_id(sv_or_dv_id)
        address_info = plc_address_operation.get_address_info(self.plc_type, callback)
        if count_num == 1:
            self.plc.execute_write(**address_info, value=value)
        else:
            write_multiple_value_func = getattr(self, f"write_multiple_value_{self.plc_type}")
            write_multiple_value_func(callback, value)

        if isinstance(self.plc, S7PLC) and address_info.get("data_type") == "bool":
            self.confirm_write_success(address_info, value)  # 确保写入成功

    def get_sv_or_dv_value_with_id(self, sv_or_dv_id: int) -> Union[int, bool, float, str, list]:
        """根据 sv id 或 dv id 获取 sv 或 dv 值.

        Returns:
            Union[int, bool, float, str, list]: 返回 sv 或 dv 值.
        """
        if sv_or_dv_id in self.status_variables:
            return self.get_sv_value_with_id(sv_or_dv_id)
        return self.get_dv_value_with_id(sv_or_dv_id)

    def set_sv_or_dv_value_with_id(self, sv_or_dv_id: int, value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 sv 或 dv 变量的值.

        Args:
            sv_or_dv_id : 变量名称.
            value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if sv_or_dv_id in self.status_variables:
            self.set_sv_value_with_id(sv_or_dv_id, value, is_save)
        if sv_or_dv_id in self.data_values:
            self.set_dv_value_with_id(sv_or_dv_id, value, is_save)

    def set_sv_value_with_name(self, sv_name: str, sv_value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 sv 变量的值.

        Args:
            sv_name : 变量名称.
            sv_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if sv_instance := self.status_variables.get(self.get_sv_id_with_name(sv_name)):
            sv_instance.value = sv_value
            self.logger.info("设置 sv 值, %s = %s", sv_instance.name, sv_value)
        if is_save:
            filter_data = {"sv_name": sv_name}
            update_data = {"value": sv_value}
            self.mysql_secs.update_data(models_class.SvList, update_data, filter_data)

    def set_dv_value_with_name(self, dv_name: str, dv_value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 dv 变量的值.

        Args:
            dv_name : 变量名称.
            dv_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if dv_instance := self.data_values.get(self.get_dv_id_with_name(dv_name)):
            dv_instance.value = dv_value
            self.logger.info("设置 dv 值, %s = %s", dv_instance.name, dv_value)
        if is_save:
            filter_data = {"dv_name": dv_name}
            update_data = {"value": dv_value}
            self.mysql_secs.update_data(models_class.DvList, update_data, filter_data)

    def set_ec_value_with_name(self, ec_name: str, ec_value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 ec 变量的值.

        Args:
            ec_name : 变量名称.
            ec_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if ec_instance := self.data_values.get(self.get_ec_id_with_name(ec_name)):
            ec_instance.value = ec_value
            self.logger.info("设置 ec 值, %s = %s", ec_instance.name, ec_value)
        if is_save:
            filter_data = {"ec_name": ec_name}
            update_data = {"value": ec_value}
            self.mysql_secs.update_data(models_class.DvList, update_data, filter_data)

    def set_sv_value_with_id(self, sv_id: int, sv_value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 sv 变量的值.

        Args:
            sv_id : 变量名称.
            sv_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if sv_instance := self.status_variables.get(sv_id):
            sv_instance.value = sv_value
            self.logger.info("设置 sv 值, %s = %s", sv_instance.name, sv_value)
        if is_save:
            filter_data = {"sv_id": sv_id}
            update_data = {"value": sv_value}
            self.mysql_secs.update_data(models_class.SvList, update_data, filter_data)

    def set_dv_value_with_id(self, dv_id: int, dv_value: Union[str, int, float, list], is_save: bool = True):
        """设置指定 dv 变量的值.

        Args:
            dv_id: dv 变量 id.
            dv_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if dv_instance := self.data_values.get(dv_id):
            dv_instance.value = dv_value
            self.logger.info("设置 dv 值, %s = %s", dv_instance.name, dv_value)
        if is_save:
            filter_data = {"dv_id": dv_id}
            update_data = {"value": dv_value}
            self.mysql_secs.update_data(models_class.DvList, update_data, filter_data)

    def get_sv_value_with_id(self, sv_id: int, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据变量 sv 名获取变量 sv 值.

        Args:
            sv_id: 变量 id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应变量的值.
        """
        if sv_instance := self.status_variables.get(sv_id):
            sv_value = sv_instance.value
            if save_log:
                self.logger.info("当前 sv %s = %s", sv_instance.name, sv_value)
            return sv_instance.value
        return None

    def get_dv_value_with_id(self, dv_id: int, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据变量 dv id 取变量 dv 值..

        Args:
            dv_id: dv id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应 dv 变量的值.
        """
        if dv_instance := self.data_values.get(dv_id):
            dv_value = dv_instance.value
            if save_log:
                self.logger.info("当前 dv %s = %s", dv_instance.name, dv_value)
            return dv_value
        return None

    def get_sv_value_with_name(self, sv_name: str, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据变量 sv name 取变量 sv 值..

        Args:
            sv_name: sv id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应 sv 变量的值.
        """
        if sv_instance := self.status_variables.get(self.get_sv_id_with_name(sv_name)):
            sv_value = sv_instance.value
            if save_log:
                self.logger.info("当前 sv %s = %s", sv_instance.name, sv_value)
            return sv_value
        return None

    def get_dv_value_with_name(self, dv_name: str, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据变量 dv name 取变量 dv 值..

        Args:
            dv_name: dv id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应 dv 变量的值.
        """
        if dv_instance := self.data_values.get(self.get_dv_id_with_name(dv_name)):
            dv_value = dv_instance.value
            if save_log:
                self.logger.info("当前 dv %s = %s", dv_instance.name, dv_value)
            return dv_value
        return None

    def get_ec_value_with_name(self, ec_name: str, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据变量 ec name 取变量 ec 值..

        Args:
            ec_name: dv id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应 ec 变量的值.
        """
        if ec_instance := self.equipment_constants.get(self.get_ec_id_with_name(ec_name)):
            ec_value = ec_instance.value
            if save_log:
                self.logger.info("当前 ec %s = %s", ec_instance.name, ec_value)
            return ec_value
        return None

    def get_dv_id_with_name(self, dv_name: str) -> Optional[int]:
        """根据 dv name 获取 dv id.

        Args:
            dv_name: dv 名称.

        Returns:
            Optional[int]: dv id 或者 None.
        """
        for dv_id, dv_instance in self.data_values.items():
            if dv_instance.name == dv_name:
                return dv_id
        return None

    def get_sv_id_with_name(self, sv_name: str) -> Optional[int]:
        """根据 sv name 获取 sv id.

        Args:
            sv_name: sv 名称.

        Returns:
            Optional[int]: sv id 或者 None.
        """
        for sv_id, sv_instance in self.status_variables.items():
            if sv_instance.name == sv_name:
                return sv_id
        return None

    def get_ec_id_with_name(self, ec_name: str) -> Optional[int]:
        """根据 ec name 获取 ec id.

        Args:
            ec_name: ec 名称.

        Returns:
            Optional[int]: ec id 或者 None.
        """
        for ec_id, ec_instance in self.equipment_constants.items():
            if ec_instance.name == ec_name:
                return ec_id
        return None

    def get_ec_value_with_id(self, ec_id: int, save_log: bool = True) -> Optional[Union[int, str, bool, list, float]]:
        """根据常量名获取常量值.

        Args:
            ec_id: 常量 id.
            save_log: 是否保存日志, 默认保存.

        Returns:
            Optional[Union[int, str, bool, list, float]]: 返回对应常量的值.
        """
        if ec_instance := self.equipment_constants.get(ec_id):
            ec_value = ec_instance.value
            if save_log:
                self.logger.info("当前 ec %s = %s", ec_instance.name, ec_value)
            return ec_value
        return None

    def get_sv_name_with_id(self, sv_id: int) -> Optional[str]:
        """根据 sv id 获取 sv name.

        Args:
            sv_id: sv id.

        Returns:
            str: sv name.
        """
        if sv := self.status_variables.get(sv_id):
            return sv.name
        return None

    def get_dv_name_with_id(self, dv_id: int) -> Optional[str]:
        """根据 dv id 获取 dv name.

        Args:
            dv_id: dv id.

        Returns:
            str: dv name.
        """
        if dv := self.data_values.get(dv_id):
            return dv.name
        return None

    def get_ec_name_with_id(self, ec_id: int) -> Optional[str]:
        """根据 ec id 获取 ec name.

        Args:
            ec_id: ec id.

        Returns:
            str: ec name.
        """
        if ec := self.equipment_constants.get(ec_id):
            return ec.name
        return None

    def set_ec_value_with_id(self, ec_id: int, ec_value: Union[str, int, float, list], is_save: bool = False):
        """设置指定 ec 变量的值.

        Args:
            ec_id: dv 变量 id.
            ec_value: 要设定的值.
            is_save: 是否更新数据库, 默认不更新.
        """
        if ec_instance := self.equipment_constants.get(ec_id):
            ec_instance.value = ec_value
            self.logger.info("设置 ec 值, %s = %s", ec_instance.name, ec_value)
        if is_save:
            filter_data = {"ec_id": ec_id}
            update_data = {"value": ec_value}
            self.mysql_secs.update_data(models_class.EcList, update_data, filter_data)

    def send_s6f11(self, event_id: int):
        """给EAP发送S6F11事件.

        Args:
            event_id: 事件 id.
        """
        threading.Thread(target=self.thread_methods.collection_event_sender, args=(event_id,), daemon=True).start()

    def set_clear_alarm(self, alarm_code: int):
        """通过S5F1发送报警和解除报警.

        Args:
            alarm_code: 报警 code, 128: 报警, 0: 清除报警.
        """
        address_info = plc_address_operation.get_alarm_address_info(self.plc_type)
        alarm_id = self.plc.execute_read(**address_info, save_log=False)
        self.logger.info("出现报警, 报警id: %s", alarm_id)
        self.send_and_save_alarm(alarm_code, alarm_id)

    def set_clear_alarm_socket(self, alarm_code: int, alarm_id: int, alarm_text: str):
        """通过S5F1发送报警和解除报警.

        Args:
            alarm_code: 报警 code, 128: 报警, 0: 清除报警.
            alarm_id: 报警 id.
            alarm_text: 报警内容.
        """
        self.send_and_save_alarm(alarm_code, alarm_id, alarm_text)

    def send_and_save_alarm(self, alarm_code: int, alarm_id: Union[int, str], alarm_text: str = None):
        """发送并保存报警信息.

        Args:
            alarm_code: alarm_code.
            alarm_id: 报警 id.
            alarm_text: 报警内容, 默认是None.
        """
        try:
            alarm_id = int(alarm_id)
            alarm_id_send = U4(alarm_id)
        except ValueError:
            alarm_id_send = U4(0)
            self.logger.warning("报警 id 非法, 报警id: %s", alarm_id)
        if alarm_instance := self.alarms.get(alarm_id):
            alarm_text_send = alarm_instance.text
            # noinspection PyUnresolvedReferences
            alarm_text_save = alarm_instance.text_zh
        else:
            alarm_text_send = "Alarm is not defined."
            alarm_text_save = "报警未定义"

        threading.Thread(
            target=self.thread_methods.alarm_sender, args=(alarm_code, alarm_id_send, alarm_text_send,), daemon=True
        ).start()

        if alarm_code == int(self.get_ec_value_with_id(701)):
            alarm_info = {"alarm_id": alarm_id, "alarm_text": alarm_text if alarm_text else alarm_text_save}
            self.mysql_secs.add_data(models_class.AlarmRecordList, [alarm_info])

    def get_signal_to_execute_callbacks(self, callbacks: list):
        """监控到信号执行 call_backs.

        Args:
            callbacks: 要执行的流程信息列表.
        """
        for i, callback in enumerate(callbacks, 1):
            description = callback.get("description")
            self.logger.info("%s 第 %s 步: %s %s", "-" * 30, i, description, "-" * 30)

            operation_type = callback.get("operation_type")
            if operation_type == "read":
                self.read_update_sv_or_dv(callback)

            if operation_type == "write":
                self.write_sv_or_dv_value(callback)

            if func_name := callback.get(f"func_name"):
                getattr(self, func_name)(callback)

            self._is_send_event(callback.get("event_id"))
            self.logger.info("%s %s 结束 %s", "-" * 30, description, "-" * 30)

    def read_multiple_value_snap7(
            self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], callback: dict
    ) -> list:
        """读取 Snap7 plc 多个数据.

        Args:
            plc: plc 实例对象.
            callback: callback 信息.

        """
        value_list = []
        count_num = callback["count_num"]
        gap = callback.get("gap", 1)
        start_address = int(callback.get("address"))
        for i in range(count_num):
            real_address = start_address + i * gap
            address_info = {
                "address": real_address,
                "data_type": callback.get("data_type"),
                "db_num": self.get_ec_value_with_name("db_num"),
                "size": callback.get("size", 1),
                "bit_index": callback.get("bit_index", 0)
            }
            plc_value = plc.execute_read(**address_info)
            value_list.append(plc_value)
            self.logger.info("读取 %s 的值是: %s", real_address, plc_value)
        return value_list

    def read_multiple_value_tag(
            self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], callback: dict
    ) -> list:
        """读取标签通讯 plc 多个数据值.

        Args:
            plc: plc 实例对象.
            callback: callback 信息.
        """
        value_list = []
        for i in range(1, callback["count_num"] + 1):
            real_address = callback["address"].replace("$", str(i))
            address_info = {"address": real_address,"data_type": callback["data_type"]}
            plc_value = plc.execute_read(**address_info)
            value_list.append(plc_value)
            self.logger.info("读取 %s 的值是: %s", real_address, plc_value)
        return value_list

    def read_multiple_value_modbus(
            self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], callback: dict
    ) -> list:
        """读取 modbus 通讯 plc 多个数据值.

        Args:
            plc: plc 实例对象.
            callback: callback 信息.
        """
        value_list = []
        count_num = callback["count_num"]
        start_address = callback.get("address")
        size = callback.get("size")
        for i in range(count_num):
            real_address = start_address + i * size
            address_info = {
                "address": real_address,
                "data_type": callback.get("data_type"),
                "size": size
            }
            plc_value = plc.execute_read(**address_info)
            value_list.append(plc_value)
            self.logger.info("读取 %s 的值是: ", real_address, plc_value)
        return value_list

    def write_multiple_value_snap7(self, callback: dict, value_list: list):
        """向 snap7 plc 地址写入多个值.

        Args:
            callback: callback 信息.
            value_list: 写入的值列表.
        """
        gap = callback.get("gap", 1)
        for i, value in enumerate(value_list):
            address_info = {
                "address": int(callback.get("address")) + gap * i,
                "data_type": callback.get("data_type"),
                "db_num": self.get_ec_value_with_name("db_num"),
                "size": callback.get("size", 2),
                "bit_index": callback.get("bit_index", 0)
            }
            self.plc.execute_write(**address_info, value=value)

    def write_multiple_value_tag(self, callback: dict, value_list: list):
        """向汇川 plc 标签通讯地址写入多个值.

        Args:
            callback: callback 信息.
            value_list: 写入的值列表.
        """
        for i, value in enumerate(value_list, 1):
            address_info = {
                "address": callback.get("address").replace("$", str(i)),
                "data_type": callback.get("data_type"),
            }
            self.plc.execute_write(**address_info, value=value)

    def write_multiple_value_modbus(self, callback: dict, value_list: list):
        """向 modbus 通讯地址写入多个值.

        Args:
            callback: callback 信息.
            value_list: 写入的值列表.
        """
        start_address = callback.get("address")
        size = callback.get("size")
        for i, value in enumerate(value_list, 0):
            address_info = {
                "address": int(start_address) + i * size,
                "data_type": callback.get("data_type"),
            }
            self.plc.execute_write(**address_info, value=value)

    def confirm_write_success(self, address_info: dict, value: Union[int, float, bool, str]):
        """向 plc 写入数据, 并且一定会写成功.

        在通过 S7 协议向西门子plc写入 bool 数据的时候, 会出现写不成功的情况, 所以再向西门子plc写入 bool 时调用此函数.
        为了确保数据写入成功, 向任何plc写入数据都可调用此函数, 但是交互的时候每次会多读一次 plc.

        Args:
            address_info: 写入数据的地址位信息.
            value: 要写入的数据.
        """
        while (plc_value := self.plc.execute_read(**address_info)) != value:
            self.logger.warning(f"当前地址 %s 的值是 %s != %s, %s", address_info.get("address"), plc_value,
                                value, address_info.get("description"))
            self.plc.execute_write(**address_info, value=value)

    def wait_time(self, callback: dict):
        """等待时间.

        Args:
            callback: callback 信息.
        """
        count_time = 0
        wait_time = self.get_dv_name_with_id(callback["associate_dv"])
        while True:
            time.sleep(1)
            count_time += 1
            self.logger.info("等待 %s 秒", count_time)
            wait_time -= 1
            if wait_time == 0:
                break

    def wait_2_second(self, call_back: dict):
        """等待 2 s.

        Args:
            call_back: call_back 信息.
        """
        self.logger.info("call back 信息是: %s", call_back)
        time.sleep(2)

    def send_data_to_socket_client(self, socket_instance: CygSocketServerAsyncio, client_ip: str, data: str) -> bool:
        """发送数据给 socket 下位机.

        Args:
            socket_instance: CygSocketServerAsyncio 实例.
            client_ip: 接收数据的设备ip地址.
            data: 要发送的数据.

        Return:
            bool: 是否发送成功.
        """
        status = True
        client_connection = socket_instance.clients.get(client_ip)
        if client_connection:
            byte_data = str(data).encode("UTF-8")
            asyncio.run(socket_instance.socket_send(client_connection, byte_data))
        else:
            self.logger.warning("发送失败: %s 未连接", client_ip)
            status = False
        return status

    async def operate_func_socket(self, byte_data) -> str:
        """操作并返回数据."""
        str_data = byte_data.decode("UTF-8")  # 解析接收的下位机数据
        receive_dict = json.loads(str_data)
        for receive_key, receive_info in receive_dict.items():
            self.logger.info("收到的下位机关键字是: %s", receive_key)
            self.logger.info("收到的下位机关键字对应的数据是: %s", receive_info)
            reply_data = await getattr(self, receive_key)(receive_info)
            if not reply_data:
                reply_data = "OK"
            self.logger.info("返回的数据是: %s", reply_data)
            return str(reply_data)
        return "OK"

    async def send_event(self, event_id: int):
        """发送事件.

        Args:
            event_id: 事件 id.
        """
        self.send_s6f11(event_id)

    def wait_eap_reply(self, callback: dict):
        """等待 eap 反馈.

        Args:
            callback: 要执行的 callback 信息.
        """
        wait_time = 0
        dv_id = int(callback.get("associate_dv"))
        is_wait = callback.get("is_wait")
        wait_eap_reply_time = self.get_ec_value_with_name("wait_time_eap_reply")
        dv_filter = {"dv_name": f"{self.get_dv_name_with_id(dv_id)}_reply"}
        dv_info_reply_flag = secs_config.get_dv_info(dv_filter)
        dv_id_reply_flag = dv_info_reply_flag["dv_id"]
        while not self.get_dv_value_with_id(dv_id_reply_flag):
            if is_wait:
                self.logger.info("需要等待 eap 回复, 等待超时时间是: %s", wait_eap_reply_time)
                if wait_time >= wait_eap_reply_time:
                    self.set_dv_value_with_id(dv_id, 2)
                    break
            else:
                self.logger.info("不需要等待 eap 回复, 默认可做")
                self.set_dv_value_with_id(dv_id, 1)
                self.set_dv_value_with_id(dv_id_reply_flag, True)
                break

            time.sleep(0.5)
            wait_time += 0.5
            self.logger.info("eap 未反馈 %s, 已等待 %s 秒", callback["description"], wait_time)

        self.set_dv_value_with_id(dv_id_reply_flag, False)

    def _is_send_event(self, event_id: Optional[int]):
        """判断是否要发送事件.

        Arg:
            event_id: 要发送的事件 id, 默认 None.
        """
        if event_id:
            self.send_s6f11(event_id)

    def _on_s07f19(self, *args):
        """查看设备的所有配方."""
        self.logger.info("收到的参数是: %s", args)
        return self.stream_function(7, 20)(secs_config.get_recipe_list())

    def _on_s02f17(self, *args) -> SecsS02F18:
        """获取设备时间.

        Returns:
            SecsS02F18: SecsS02F18 实例.
        """
        self.logger.info("收到的参数是: %s", args)
        current_time_str = datetime.now().strftime("%Y%m%d%H%M%S%C")
        return self.stream_function(2, 18)(current_time_str)

    def _on_s02f31(self, *args):
        """设置设备时间."""
        function = self.settings.streams_functions.decode(args[1])
        parser_result = function.get()
        date_time_str = parser_result
        if len(date_time_str) not in (14, 16):
            self.logger.info("时间格式错误: %s 不是14或16个数字", date_time_str)
            return self.stream_function(2, 32)(TIACK.TIME_SET_FAIL)
        current_time_str = datetime.now().strftime("%Y%m%d%H%M%S%C")
        self.logger.info("当前时间: %s", current_time_str)
        self.logger.info("设置时间: %s", date_time_str)
        status = common_func.set_date_time(date_time_str)
        current_time_str = datetime.now().strftime("%Y%m%d%H%M%S%C")
        if status:
            self.logger.info(f"设置成功, 当前时间: %s", current_time_str)
            ti_ack = TIACK.ACK
        else:
            self.logger.info("设置失败, 当前时间: %s", current_time_str)
            ti_ack = TIACK.TIME_SET_FAIL
        return self.stream_function(2, 32)(ti_ack)

    def _on_s10f03(self, *args):
        """Eap 下发弹框信息."""
        function = self.settings.streams_functions.decode(args[1])
        display_data = function.get()
        terminal_id = display_data.get("TID", 0)
        terminal_text = display_data.get("TEXT", "")
        self.logger.info("接收到的弹框信息是, terminal_id: %s, terminal_text: %s", terminal_id, terminal_text)
        return self.stream_function(10, 4)(ACKC10.ACCEPTED)

    def _on_rcmd_pp_select(self, recipe_name: str):
        """工厂切换配方.

        Args:
            recipe_name: 要切换的配方名称.
        """
        pp_select_recipe_name = recipe_name
        self.set_sv_value_with_name("pp_select_recipe_name", pp_select_recipe_name)
        pp_select_recipe_id = secs_config.get_recipe_id_with_name(recipe_name)
        self.set_sv_value_with_name("pp_select_recipe_id", pp_select_recipe_id)

        address_info = plc_address_operation.get_signal_address_info(self.plc_type, "pp_select")
        callbacks = plc_address_operation.get_signal_callbacks(address_info["address"])

        self.get_signal_to_execute_callbacks(callbacks,)

        current_recipe_id = self.get_sv_value_with_name("recipe_id")
        current_recipe_name = secs_config.get_recipe_name_with_id(current_recipe_id)
        self.set_sv_value_with_name("recipe_name", current_recipe_name)
        if current_recipe_id == pp_select_recipe_id:
            pp_select_state = 1
        else:
            pp_select_state = 2
        self.set_sv_value_with_name("pp_select_state", pp_select_state)
        self.send_s6f11(2000)

    def _on_rcmd_new_lot(self, lot_name: str, lot_quantity: int):
        """工厂开工单.

        Args:
            lot_name: 工单名称.
            lot_name: 工单数量.
        """
        lot_quantity = int(lot_quantity)
        self.set_sv_value_with_name("lot_name", lot_name)
        self.set_sv_value_with_name("lot_quantity", lot_quantity)
        address_info = plc_address_operation.get_signal_address_info(self.plc_type, "new_lot")
        callbacks = plc_address_operation.get_signal_callbacks(address_info["address"])
        self.get_signal_to_execute_callbacks(callbacks)

    def new_lot_pre_check(self):
        """开工单前检查上个工单是否做完."""
        address_info = plc_address_operation.get_do_quantity_address_info(self.plc_type)
        do_quantity = self.plc.execute_read(**address_info, save_log=True)
        self.set_sv_value_with_name("do_quantity", do_quantity)
        lot_quantity = self.get_sv_value_with_name("lot_quantity")
        if do_quantity < lot_quantity and do_quantity != 0:
            return False
        return True

    async def new_lot(self, lot_info: dict):
        """本地开工单.

        Args:
            lot_info: 工单信息.
        """
        state = self.new_lot_pre_check()
        if not state:
            lot_name = self.get_sv_value_with_name("lot_name")
            lot_quantity = self.get_sv_value_with_name("lot_quantity")
            do_quantity = self.get_sv_value_with_name("do_quantity")
            return f"当前工单 {lot_name} 未生产结束, 不允许开新工单, 应生产: {lot_quantity}, 已生产: {do_quantity}"
        self._on_rcmd_new_lot(lot_info["lot_name"], lot_info["lot_quantity"])
        return f"开工单 {self.get_sv_value_with_name('lot_name')} 成功"
