# pylint: skip-file
"""设备服务端处理器."""
import csv
import datetime
import json
import logging
import os
import pathlib
import threading
import time
from logging.handlers import TimedRotatingFileHandler
from typing import Union, Optional

from inovance_tag.tag_communication import TagCommunication
from mitsubishi_plc.mitsubishi_plc import MitsubishiPlc
from modbus_api.modbus_api import ModbusApi
from secsgem.common import DeviceType
from secsgem.gem import CollectionEvent, GemEquipmentHandler, StatusVariable, RemoteCommand, Alarm, DataValue, \
    EquipmentConstant
from secsgem.secs.variables import U4, Array, String
from secsgem.hsms import HsmsSettings, HsmsConnectMode
from siemens_plc.s7_plc import S7PLC
from siemens_plc.exception import PLCWriteError as S7PLCWriteError, PLCReadError as S7PLCReadError

from passive_equipment.enum_sece_data_type import EnumSecsDataType
from passive_equipment.handler_config import HandlerConfig


class HandlerPassive(GemEquipmentHandler):
    """Passive equipment handler class."""

    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, encoding="UTF-8", format=self.LOG_FORMAT)

        self.config_instance = HandlerConfig(self.get_config_path())
        self.config = self.config_instance.config_data
        self.lower_computer_instance = self._get_lower_computer_instance()
        self._file_handler = None  # 保存日志的处理器

        hsms_settings = HsmsSettings(
            address=self.config_instance.get_config_value("secs_ip", "127.0.0.1", parent_name="secs_conf"),
            port=self.config_instance.get_config_value("secs_port", 5000, parent_name="secs_conf"),
            connect_mode=getattr(HsmsConnectMode, "PASSIVE"),
            device_type=DeviceType.EQUIPMENT
        )
        super().__init__(settings=hsms_settings, **kwargs)

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

        self._enable_equipment()
        self._monitor_lower_computer_thread()

    def _monitor_lower_computer_thread(self):
        """监控下位机的线程."""
        if self.lower_computer_instance.communication_open():
            self.logger.info("连接 %s 下位机成功, ip: %s", self.lower_computer_type, self.lower_computer_instance.ip)
        else:
            self.logger.info("连接 %s 下位机失败, ip: %s", self.lower_computer_type, self.lower_computer_instance.ip)

        getattr(self, f"mes_heart_thread_{self.lower_computer_type}")
        getattr(self, f"control_state_thread_{self.lower_computer_type}")
        getattr(self, f"machine_state_thread_{self.lower_computer_type}")
        getattr(self, f"signal_thread_{self.lower_computer_type}")

    @property
    def lower_computer_type(self) -> str:
        """获取下位机类型."""
        return self.config_instance.get_config_value("type", parent_name="lower_computer")

    @property
    def file_handler(self) -> TimedRotatingFileHandler:
        """设置保存日志的处理器, 每个一天自动生成一个日志文件.

        Returns:
            TimedRotatingFileHandler: 返回 TimedRotatingFileHandler 日志处理器.
        """
        if self._file_handler is None:
            log_file_name = f"{os.getcwd()}/log/{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
            self._file_handler = TimedRotatingFileHandler(
                log_file_name, when="D", interval=1, backupCount=10, encoding="UTF-8"
            )
            self._file_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
        return self._file_handler

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
        self.logger.addHandler(self.file_handler)
        self.protocol.communication_logger.addHandler(self.file_handler)  # secs 通讯日志

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

    def _get_lower_computer_instance(self):
        """获取下位机实例."""
        lower_computer_flag = self.config["lower_computer"]["type"]
        instance_params = self.config["lower_computer"]["lower_computer_flag"]
        instance_map = {
            "snap7": S7PLC, "tag": TagCommunication,
            "mitsubishi": MitsubishiPlc, "modbus": ModbusApi
        }
        instance = instance_map[lower_computer_flag](**instance_params)
        instance.communication_open()
        return instance

    def _get_sv_id_with_name(self, sv_name: str) -> Optional[int]:
        """根据变量名获取变量id.

        Args:
            sv_name: 变量名称.

        Returns:
            Optional[int]: 返回变量id, 没有此变量返回None.
        """
        if sv_info := self.config_instance.get_config_value(sv_name, "status_variable"):
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
        self.status_variables.get(self._get_sv_id_with_name(sv_name)).value = sv_value

    def set_dv_value_with_name(self, dv_name: str, dv_value: Union[str, int, float, list]):
        """设置指定 dv 变量的值.

        Args:
            dv_name (str): dv 变量名称.
            dv_value (Union[str, int, float, list]): 要设定的值.
        """
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
        config_file_path = os.path.join(os.getcwd(), f"{self.__module__}.json")
        self.logger.info("配置文件路径: %s")
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
                        try:
                            value = Array(U4, sv_instance.value)
                        except Exception:
                            value = Array(String, sv_instance.value)
                    else:
                        value = sv_instance.value_type(sv_instance.value)
                    variables.append(value)
                reports.append({"RPTID": U4(report_id), "V": variables})

            self.send_and_waitfor_response(
                self.stream_function(6, 11)({"DATAID": 1, "CEID": event.ceid, "RPT": reports})
            )

        threading.Thread(target=_ce_sender, daemon=True).start()

    def mes_heart_thread_snap7(self):
        """Snap7 plc mes 心跳的线程."""

        def _mes_heart():
            """Mes 心跳."""
            address = self.config_instance.get_signal_address("mes_heart")
            data_type = self.config_instance.get_signal_data_type("mes_heart")
            gap = self.config_instance.get_signal_param_value("mes_heart", "gap")
            db_num = self.get_ec_value_with_name("db_num")
            while True:
                try:
                    self.lower_computer_instance.execute_write(data_type, db_num, address, True)
                    time.sleep(gap)
                    self.lower_computer_instance.execute_write("bool", db_num, address, False)
                    time.sleep(gap)
                except S7PLCWriteError as e:
                    self.logger.warning("写入心跳失败, 错误信息: %s", str(e))
                    if self.lower_computer_instance.communication_open():
                        self.logger.info("Plc重新连接成功.")
                    else:
                        self.wait_time(30)
                        self.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

        threading.Thread(target=_mes_heart, daemon=True, name="mes_heart_thread").start()

    def control_state_thread_snap7(self):
        """Snap7 plc 监控控制状态变化的线程."""

        def _control_state():
            """监控控制状态变化."""
            address = self.config_instance.get_signal_address("control_state")
            data_type = self.config_instance.get_signal_data_type("control_state")
            db_num = self.get_ec_value_with_name("db_num")
            size = self.config_instance.get_signal_param_value("control_state", "size")
            bit_index = self.config_instance.get_signal_param_value("control_state", "bit_index")
            while True:
                try:
                    current_control_state = self.lower_computer_instance.execute_read(
                        data_type, db_num, address, size, bit_index, save_log=False
                    )
                    if data_type == "bool":
                        current_control_state = 2 if current_control_state else 1
                    if current_control_state != self.get_sv_value_with_name("current_control_state"):
                        self.set_sv_value_with_name("current_control_state", current_control_state)
                        self.send_s6f11("control_state_change")
                except S7PLCReadError as e:
                    self.set_sv_value_with_name("current_control_state", 0)
                    self.send_s6f11("control_state_change")
                    self.logger.warning("读取plc控制状态失败, 错误信息: %s", str(e))
                    if self.lower_computer_instance.communication_open():
                        self.logger.info("Plc重新连接成功.")
                    else:
                        self.wait_time(30)
                        self.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

        threading.Thread(target=_control_state, daemon=True, name="control_state_thread").start()

    def machine_state_thread_snap7(self):
        """Snap7 plc 运行状态变化的线程."""

        def _machine_state():
            """监控运行状态变化."""
            address = self.config_instance.get_signal_address("machine_state")
            data_type = self.config_instance.get_signal_data_type("machine_state")
            db_num = self.get_ec_value_with_name("db_num")
            size = self.config_instance.get_signal_param_value("machine_state", "size")
            bit_index = self.config_instance.get_signal_param_value("machine_state", "bit_index")
            while True:
                try:
                    machine_state = self.lower_computer_instance.execute_read(
                        data_type, db_num, address, size, bit_index, save_log=False
                    )
                    if machine_state != self.get_sv_value_with_name("current_machine_state"):
                        alarm_state = self.get_ec_value_with_name("alarm_state")
                        if machine_state == alarm_state:
                            self.set_clear_alarm(2)
                        elif self.get_sv_value_with_name("current_machine_state") == alarm_state:
                            self.set_clear_alarm(0)
                        self.set_sv_value_with_name("current_machine_state", machine_state)
                        self.send_s6f11("machine_state_change")
                except S7PLCReadError as e:
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
            alarm_code (int): 报警code, 2: 报警, 9: 清除报警.
        """
        if alarm_code == 2:
            address = self.config_instance.get_signal_address("alarm_id")
            data_type = self.config_instance.get_signal_data_type("alarm_id")
            db_num = self.get_ec_value_with_name("db_num")
            size = self.config_instance.get_signal_param_value("alarm_id", "size")
            bit_index = self.config_instance.get_signal_param_value("alarm_id", "bit_index")
            alarm_id = self.lower_computer_instance.execute_read(
                        data_type, db_num, address, size, bit_index, save_log=False
                    )
            self.logger.info("出现报警, 报警id: %s")
            try:
                self.alarm_id = U4(alarm_id)
                if alarm_text :=self.alarms.get(str(alarm_id)):
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

    def signal_thread_snap7(self):
        """Snap7 plc 信号监控的线程."""
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
        while True:
            value = self.config_instance.get_signal_param_value(signal_name, "value")
            current_value = self.lower_computer_instance.execute_read(
                **self._get_signal_address_info(signal_name), save_log=False
            )
            if current_value == value:
                self.get_signal_to_sequence(signal_name)

    def get_signal_to_sequence(self, signal_name: str):
        """监控到信号执行 call_backs.

        Args:
            signal_name: 信号名称.
        """
        _ = "=" * 40
        self.logger.info("%s 监控到 %s 信号 %s", _, signal_name, _)

        self.execute_call_backs(self.config_instance.get_signal_param_value(signal_name, "call_backs"))

        self.logger.info("%s %s 结束 %s", _, signal_name, _)

    def execute_call_backs(self, call_backs: list):
        """根据操作列表执行具体的操作.

        Args:
            call_backs: 要执行动作的信息列表, 按照列表顺序执行.
        """
        for i, call_back in enumerate(call_backs, 1):
            description = call_back.get("description")
            self.logger.info("%s 第 %s 步: %s %s", "-" * 30, i, description, "-" * 30)
            operation_func = getattr(self, call_back.get(f"operation_func_{self.lower_computer_type}"))
            operation_func(call_back=call_back)
            self.logger.info("%s %s 结束 %s", "-" * 30, description, "-" * 30)

    def read_update_sv_snap7(self, call_back: dict):
        """读取 Snap7 plc 数据更新 sv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        sv_name = call_back.get("sv_name")
        plc_value = self.lower_computer_instance.execute_read(**self._get_read_info_snap7(call_back))
        self.set_sv_value_with_name(sv_name, plc_value)

    def read_update_dv_snap7(self, call_back: dict):
        """读取 Snap7 plc 数据更新 dv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        dv_name = call_back.get("dv_name")
        plc_value = self.lower_computer_instance.execute_read(**self._get_read_info_snap7(call_back))
        self.set_dv_value_with_name(dv_name, plc_value)

    def write_sv_value_to_snap7(self, call_back: dict):
        """向 snap7 plc 地址写入 sv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        sv_value = self.get_sv_value_with_name(call_back.get("sv_name"))

        # 如果有前提条件, 要先判断前提条件再写入
        if call_back.get("premise_address"):
            premise_value = call_back.get("premise_address")
            wait_time = call_back.get("wait_time")
            while self.lower_computer_instance.execute_read(**self._get_premise_info_snap7(call_back)) != premise_value:
                self.logger.info("前提条件值 != %s", call_back.get("premise_value"))
                self.wait_time(1)
                wait_time -= 1
                if wait_time == 0:
                    break
        self.lower_computer_instance.execute_write(**self._get_write_info_snap7(call_back), data=sv_value)

        while self.lower_computer_instance.execute_read(**self._get_read_info_snap7(call_back)) != sv_value:
            self.logger.warning(f"向 %s 写入 %s 失败", json.dumps(self._get_read_info_snap7(call_back)), sv_value)
            self.lower_computer_instance.execute_write(**self._get_write_info_snap7(call_back), data=sv_value)

    def write_dv_value_to_snap7(self, call_back: dict):
        """向 snap7 plc 地址写入 dv 值.

        Args:
            call_back: 要执行的 call_back 信息.
        """
        dv_value = self.get_dv_value_with_name(call_back.get("dv_name"))

        # 如果有前提条件, 要先判断前提条件再写入
        if call_back.get("premise_address"):
            premise_value = call_back.get("premise_address")
            wait_time = call_back.get("wait_time")
            while self.lower_computer_instance.execute_read(**self._get_premise_info_snap7(call_back)) != premise_value:
                self.logger.info("前提条件值 != %s", call_back.get("premise_value"))
                self.wait_time(1)
                wait_time -= 1
                if wait_time == 0:
                    break
        self.lower_computer_instance.execute_write(**self._get_write_info_snap7(call_back), data=dv_value)

        while self.lower_computer_instance.execute_read(**self._get_read_info_snap7(call_back)) != dv_value:
            self.logger.warning(f"向 %s 写入 %s 失败", json.dumps(self._get_read_info_snap7(call_back)), dv_value)
            self.lower_computer_instance.execute_write(**self._get_write_info_snap7(call_back), data=dv_value)

    @staticmethod
    def _get_read_info_snap7(call_back: dict) -> dict:
        """获取要读取的 snap7 plc 地址信息.

        Args:
            call_back: 包含要读取的 snap7 plc 地址信息的字典.

        Returns:
            dict: 要读取的 snap7 plc 地址信息.
        """
        return {
            "start": call_back.get("address"),
            "data_type": call_back.get("data_type"),
            "db_num": call_back.get("db_num"),
            "size": call_back.get("size"),
            "bool_index": call_back.get("bit_index")
        }

    @staticmethod
    def _get_write_info_snap7(call_back: dict) -> dict:
        """获取要写入的 snap7 plc 地址信息.

        Args:
            call_back: 包含要写入的 snap7 plc 地址信息的字典.

        Returns:
            dict: 要写入的 snap7 plc 地址信息.
        """
        return {
            "start": call_back.get("address"),
            "data_type": call_back.get("data_type"),
            "db_num": call_back.get("db_num"),
            "bool_index": call_back.get("bit_index")
        }

    @staticmethod
    def _get_premise_info_snap7(call_back: dict) -> dict:
        """当读取或写入有前提条件时获取要写入的 snap7 plc 地址信息.

        Args:
            call_back: 包含要前提条件的 snap7 plc 地址信息的字典.

        Returns:
            dict: 前提条件的 snap7 plc 地址信息.
        """
        return {
            "premise_start": call_back.get("premise_start"),
            "premise_data_type": call_back.get("premise_data_type"),
            "premise_db_num": call_back.get("premise_db_num"),
            "premise_bool_index": call_back.get("premise_bool_index")
        }

    def _get_signal_address_info(self, signal_name: str) -> dict:
        """根据信号名称获取信号的地址信息.

        Args:
            signal_name: 信号名称.

        Returns:
            dict: 返回信号地址信息.
        """
        return {
            "address": self.config_instance.get_signal_address(signal_name),
            "data_type": self.config_instance.get_signal_data_type(signal_name),
            "db_num": self.get_ec_value_with_name("db_num"),
            "size": self.config_instance.get_signal_param_value(signal_name, "size"),
            "bit_index": self.config_instance.get_signal_param_value(signal_name, "bit_index")
        }

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
