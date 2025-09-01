# pylint: skip-file
"""线程方法类."""
import asyncio
import time
from typing import Union, Any

from inovance_tag.tag_communication import TagCommunication
from mitsubishi_plc.mitsubishi_plc import MitsubishiPlc
from modbus_api.modbus_api import ModbusApi
from secsgem.secs.variables import Array, U4
from siemens_plc.s7_plc import S7PLC

from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment import plc_address_operation
from passive_equipment.enum_sece_data_type import EnumSecsDataType


class ThreadMethods:
    """ThreadMethods class."""
    def __init__(self, handler_passive):
        """ThreadFunc 构造函数.

        Args:
            handler_passive: HandlerPassive实例.
        """
        self.handler_passive = handler_passive

    def mes_heart(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name: str):
        """Mes 心跳."""
        address_info = plc_address_operation.get_mes_herat(equipment_name)
        mes_heart_gap = self.handler_passive.get_ec_value_with_id(703)
        while True:
            try:
                plc.execute_write(**address_info, value=True, save_log=False)
                time.sleep(mes_heart_gap)
                plc.execute_write(**address_info, value=False, save_log=False)
                time.sleep(mes_heart_gap)
            except Exception as e:
                self.handler_passive.set_sv_value_with_id(501, 0)
                self.handler_passive.send_s6f11(1001)
                self.handler_passive.logger.warning("写入心跳失败, 错误信息: %s", str(e))
                if plc.communication_open():
                    self.handler_passive.logger.info("Plc重新连接成功.")
                else:
                    self.handler_passive.wait_time(1)
                    self.handler_passive.logger.warning("Plc重新连接失败, 等待1秒后尝试重新连接.")

    def control_state(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name):
        """监控控制状态变化."""
        address_info = plc_address_operation.get_control_state(equipment_name)
        while True:
            try:
                current_control_state = plc.execute_read(**address_info, save_log=False)
                current_control_state = 1 if current_control_state else 2
                if current_control_state != self.handler_passive.get_sv_value_with_id(501, save_log=False):
                    self.handler_passive.set_sv_value_with_id(501, current_control_state, True)
                    self.handler_passive.send_s6f11(1001)
                self.handler_passive.wait_time(1)
            except Exception as e:
                self.handler_passive.logger.warning("control_state 线程出现异常: %s.", str(e))
                self.handler_passive.wait_time(1)

    def machine_state(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name):
        """监控运行状态变化."""
        address_info = plc_address_operation.get_machine_state(equipment_name)
        occur_alarm_code = self.handler_passive.get_ec_value_with_id(701)
        clear_alarm_code = self.handler_passive.get_ec_value_with_id(702)
        alarm_state = self.handler_passive.get_ec_value_with_id(704)
        while True:
            try:
                machine_state = plc.execute_read(**address_info, save_log=False)
                if machine_state != self.handler_passive.get_sv_value_with_id(502, save_log=False):
                    if machine_state == alarm_state:
                        self.handler_passive.set_clear_alarm(occur_alarm_code, plc, equipment_name)
                    elif self.handler_passive.get_sv_value_with_id(502) == alarm_state:
                        self.handler_passive.set_clear_alarm(clear_alarm_code, plc, equipment_name)
                    self.handler_passive.set_sv_value_with_id(502, machine_state, True)
                    self.handler_passive.send_s6f11(1002)
                self.handler_passive.wait_time(1)
            except Exception as e:
                self.handler_passive.logger.warning("machine_state 线程出现异常: %s.", str(e))
                self.handler_passive.wait_time(1)

    def alarm_sender(self, alarm_code: int, alarm_id: U4, alarm_text: str):
        """发送报警和解除报警.

        Args:
            alarm_code: 报警代码.
            alarm_id: 报警 id.
            alarm_text: 报警内容.
        """
        self.handler_passive.send_and_waitfor_response(
            self.handler_passive.stream_function(5, 1)({"ALCD": alarm_code, "ALID": alarm_id, "ALTX": alarm_text})
        )

    def monitor_plc_address(
            self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi],
            equipment_name: str, address_info: dict[str, Any]
    ):
        """监控 plc 信号.

        Args:
            plc: plc 实例.
            equipment_name: 设备名称.
            address_info: 地址.
        """
        address_info = plc_address_operation.get_signal_address_info(equipment_name, address_info["address"])
        callbacks = plc_address_operation.get_signal_callbacks(equipment_name, address_info["address"])
        value = address_info["value"]
        description = address_info["description"]
        _ = "=" * 40
        while True:
            current_value = plc.execute_read(**address_info, save_log=False)
            if current_value == value:
                self.handler_passive.logger.info("%s 监控到 %s 设备的 %s 信号 %s", _, equipment_name, description, _)
                self.handler_passive.get_signal_to_execute_callbacks(callbacks, equipment_name)
                self.handler_passive.logger.info("%s 执行 %s 结束 %s", _, description, _)
            time.sleep(0.1)

    def collection_event_sender(self, event_id: int):
        """设备发送事件给 Host.

        Args:
            event_id: 事件 id.
        """
        reports = []
        event = self.handler_passive.collection_events.get(event_id)
        link_reports = event.link_reports
        for report_id, sv_or_dv_ids in link_reports.items():
            variables = []
            for sv_or_dv_id in sv_or_dv_ids:
                if sv_or_dv_id in self.handler_passive.status_variables:
                    sv_or_dv_instance = self.handler_passive.status_variables.get(sv_or_dv_id)
                else:
                    sv_or_dv_instance = self.handler_passive.data_values.get(sv_or_dv_id)
                if issubclass(sv_or_dv_instance.value_type, Array):
                    enum_secs_data_type = getattr(EnumSecsDataType, sv_or_dv_instance.base_value_type)
                    value = Array(enum_secs_data_type.value, sv_or_dv_instance.value)
                else:
                    value = sv_or_dv_instance.value_type(sv_or_dv_instance.value)
                variables.append(value)
            reports.append({"RPTID": U4(report_id), "V": variables})

        self.handler_passive.send_and_waitfor_response(
            self.handler_passive.stream_function(6, 11)({"DATAID": 1, "CEID": event.ceid, "RPT": reports})
        )

    @staticmethod
    def run_socket_server(server_instance: CygSocketServerAsyncio):
        """运行 socket 服务端.

        Args:
            server_instance: CygSocketServerAsyncio 实例对象.
        """
        asyncio.run(server_instance.run_socket_server())