# pylint: skip-file
"""线程方法类."""
import asyncio
import time
from typing import Union

from inovance_tag.tag_communication import TagCommunication
from mitsubishi_plc.mitsubishi_plc import MitsubishiPlc
from modbus_api.modbus_api import ModbusApi
from secsgem.secs.variables import Array, String, U4
from siemens_plc.s7_plc import S7PLC

from secsgem.hsms.connection_state_machine import ConnectionState
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment.database_model.models_class import EquipmentState


class ThreadMethods:
    """ThreadMethods class."""
    def __init__(self, handler_passive):
        """ThreadFunc 构造函数.

        Args:
            handler_passive: HandlerPassive实例.
        """
        self.handler_passive = handler_passive

    def _get_signal_address_info(self, signal_name: str, equipment_name: str) -> dict[str, Union[str, int, list]]:
        """获取信号信息.

        Args:
            signal_name: 信号名称.
            equipment_name: plc 类型.

        Returns:
            dict[str, Union[str, int, list]]: 信号信息字典.
        """
        address_info = self.handler_passive.config_instance.get_signal_address_info(
            signal_name, equipment_name
        )
        return address_info

    def eap_connect_state(self):
        """监控 eap 连接状态的方法."""
        pre_eap_state = ConnectionState.CONNECTED_SELECTED
        while True:
            if (current_eap_state := self.handler_passive.protocol.connection_state.current) != pre_eap_state:
                pre_eap_state = current_eap_state
                if current_eap_state == ConnectionState.CONNECTED_SELECTED:
                    eap_connect_state = 1
                    message = "已连接"
                else:
                    eap_connect_state = 0
                    message = "未连接"

                self.handler_passive.mysql.update_data(EquipmentState, {
                    "eap_connect_state": eap_connect_state, "eap_connect_state_message": message
                })

    def mes_heart(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name: str):
        """Mes 心跳."""
        address_info = self._get_signal_address_info("mes_heart", equipment_name)
        mes_heart_gap = self.handler_passive.get_ec_value_with_name("mes_heart_gap")
        while True:
            try:
                plc.execute_write(**address_info, value=True, save_log=False)
                time.sleep(mes_heart_gap)
                plc.execute_write(**address_info, value=False, save_log=False)
                time.sleep(mes_heart_gap)
            except Exception as e:
                self.handler_passive.set_sv_value_with_name("current_control_state", 0)
                self.handler_passive.send_s6f11("control_state_change")
                self.handler_passive.logger.warning("写入心跳失败, 错误信息: %s", str(e))
                if plc.communication_open():
                    self.handler_passive.logger.info("Plc重新连接成功.")
                else:
                    self.handler_passive.wait_time(30)
                    self.handler_passive.logger.warning("Plc重新连接失败, 等待30秒后尝试重新连接.")

    def control_state(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name):
        """监控控制状态变化."""
        address_info = self._get_signal_address_info("control_state", equipment_name)
        while True:
            try:
                current_control_state = plc.execute_read(**address_info, save_log=False)
                current_control_state = 1 if current_control_state else 2
                if current_control_state != self.handler_passive.get_sv_value_with_name(f"current_control_state_{equipment_name}", save_log=False):
                    self.handler_passive.set_sv_value_with_name(f"current_control_state_{equipment_name}", current_control_state)
                    self.handler_passive.send_s6f11(f"control_state_change_{equipment_name}")
            except Exception as e:
                self.handler_passive.logger.warning("control_state 线程出现异常: %s.", str(e))

    def machine_state(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi], equipment_name):
        """监控运行状态变化."""
        address_info = self._get_signal_address_info("machine_state", equipment_name)
        occur_alarm_code = self.handler_passive.get_ec_value_with_name("occur_alarm_code")
        clear_alarm_code = self.handler_passive.get_ec_value_with_name("clear_alarm_code")
        alarm_state = self.handler_passive.get_ec_value_with_name("alarm_state")
        while True:
            try:
                machine_state = plc.execute_read(**address_info, save_log=False)
                if machine_state != self.handler_passive.get_sv_value_with_name(f"current_machine_state_{equipment_name}", save_log=False):
                    if machine_state == alarm_state:
                        self.handler_passive.set_clear_alarm(occur_alarm_code, plc, equipment_name)
                    elif self.handler_passive.get_sv_value_with_name(f"current_machine_state_{equipment_name}", save_log=False) == alarm_state:
                        self.handler_passive.set_clear_alarm(clear_alarm_code, plc, equipment_name)
                    self.handler_passive.set_sv_value_with_name(f"current_machine_state_{equipment_name}", machine_state)
                    self.handler_passive.send_s6f11(f"machine_state_change_{equipment_name}")
            except Exception as e:
                self.handler_passive.logger.warning("machine_state 线程出现异常: %s.", str(e))

    def alarm_sender(self, alarm_code: int):
        """发送报警和解除报警.

        Args:
            alarm_code: 报警代码.
        """
        self.handler_passive.send_and_waitfor_response(
            self.handler_passive.stream_function(5, 1)({
                "ALCD": alarm_code, "ALID": self.handler_passive.alarm_id, "ALTX": self.handler_passive.alarm_text
            })
        )

    def monitor_plc_address(self, plc: Union[S7PLC, TagCommunication, MitsubishiPlc, ModbusApi],
                            signal_name: str, equipment_name: str):
        """监控 plc 信号.

        Args:
            plc: plc 实例.
            signal_name: 要监控的信号名称.
            equipment_name: 设备名称.
        """
        address_info = self._get_signal_address_info(signal_name, equipment_name)
        value = self.handler_passive.config_instance.get_monitor_signal_value(signal_name, equipment_name)
        while True:
            current_value = plc.execute_read(**address_info, save_log=False)
            if current_value == value:
                self.handler_passive.get_signal_to_sequence(signal_name, equipment_name)
            time.sleep(1)

    def collection_event_sender(self, event_name: str):
        """设备发送事件给 Host.

        Args:
            event_name: 事件名称.
        """
        reports = []
        event = self.handler_passive.collection_events.get(event_name)
        link_reports = event.link_reports
        for report_id, sv_ids in link_reports.items():
            variables = []
            for sv_id in sv_ids:
                if sv_id in self.handler_passive.status_variables:
                    sv_instance = self.handler_passive.status_variables.get(sv_id)
                else:
                    sv_instance = self.handler_passive.data_values.get(sv_id)
                if issubclass(sv_instance.value_type, Array):
                    if sv_instance.base_value_type == "ASCII":
                        value = Array(String, sv_instance.value)
                    else:
                        value = Array(U4, sv_instance.value)
                else:
                    value = sv_instance.value_type(sv_instance.value)
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