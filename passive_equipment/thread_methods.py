# pylint: skip-file
"""线程方法类."""
import asyncio
import time
from typing import Any

from secsgem.secs.variables import Array, U4
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment import plc_address_operation, secs_config


class ThreadMethods:
    """ThreadMethods class."""
    def __init__(self, handler_passive):
        """ThreadFunc 构造函数.

        Args:
            handler_passive: HandlerPassive 实例.
        """
        self.handler_passive = handler_passive

    def mes_heart(self):
        """Mes 心跳."""
        address_info = plc_address_operation.get_mes_herat(self.handler_passive.plc_type)
        if "snap7" in self.handler_passive.plc_type:
            address_info.update({"db_num": self.handler_passive.get_ec_value_with_name("db_num")})
        mes_heart_gap = self.handler_passive.get_ec_value_with_name("mes_heart_gap")
        while True:
            try:
                self.handler_passive.plc.execute_write(**address_info, value=True, save_log=False)
                time.sleep(mes_heart_gap)
                self.handler_passive.plc.execute_write(**address_info, value=False, save_log=False)
                time.sleep(mes_heart_gap)
            except Exception as e:
                self.handler_passive.set_sv_value_with_name("control_state", 0)
                self.handler_passive.send_s6f11(1001)
                self.handler_passive.logger.warning("写入心跳失败, 错误信息: %s", str(e))
                if self.handler_passive.plc.communication_open():
                    self.handler_passive.logger.info("Plc重新连接成功.")
                else:
                    self.handler_passive.logger.warning("Plc重新连接失败, 等待 2 秒后尝试重新连接.")

    def control_state(self):
        """监控控制状态变化."""
        address_info = plc_address_operation.get_control_state(self.handler_passive.plc_type)
        while True:
            try:
                current_control_state = self.handler_passive.plc.execute_read(**address_info, save_log=False)
                current_control_state = 1 if current_control_state else 2
                if current_control_state != self.handler_passive.get_sv_value_with_name("control_state", save_log=False):
                    self.handler_passive.set_sv_value_with_name("control_state", current_control_state, True)
                    self.handler_passive.send_s6f11(1001)
            except Exception as e:
                self.handler_passive.logger.warning("control_state 线程出现异常: %s.", str(e))
            time.sleep(2)

    def machine_state(self):
        """监控运行状态变化."""
        address_info = plc_address_operation.get_machine_state(self.handler_passive.plc_type)
        occur_alarm_code = self.handler_passive.get_ec_value_with_name("occur_alarm_code")
        clear_alarm_code = self.handler_passive.get_ec_value_with_name("clean_alarm_code")
        alarm_state = self.handler_passive.get_ec_value_with_name("alarm_state")
        while True:
            try:
                machine_state = self.handler_passive.plc.execute_read(**address_info, save_log=False)
                if machine_state != self.handler_passive.get_sv_value_with_name("machine_state", save_log=False):
                    if machine_state == alarm_state:
                        self.handler_passive.set_clear_alarm(occur_alarm_code)
                    elif self.handler_passive.get_sv_value_with_name("machine_state") == alarm_state:
                        self.handler_passive.set_clear_alarm(clear_alarm_code)
                    self.handler_passive.set_sv_value_with_name("machine_state", machine_state, True)
                    self.handler_passive.send_s6f11(1002)
            except Exception as e:
                self.handler_passive.logger.warning("machine_state 线程出现异常: %s.", str(e))
            time.sleep(2)

    def current_recipe_id(self):
        """监控设备的当前配方 id."""
        address_info = plc_address_operation.get_recipe_address_info(self.handler_passive.plc_type)
        while True:
            try:
                current_recipe_id = self.handler_passive.plc.execute_read(**address_info, save_log=False)
                if current_recipe_id != self.handler_passive.get_sv_value_with_name("recipe_id", save_log=False):
                    current_recipe_name = secs_config.get_recipe_name_with_id(current_recipe_id)
                    self.handler_passive.set_sv_value_with_name("recipe_id", current_recipe_id, True)
                    self.handler_passive.set_sv_value_with_name("recipe_name", current_recipe_name, True)
            except Exception as e:
                self.handler_passive.logger.warning("recipe_id 线程出现异常: %s.", str(e))
            time.sleep(10)

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

    def monitor_plc_address(self, address_info: dict[str, Any]):
        """监控 plc 信号.

        Args:
            address_info: 地址.
        """
        address_info_read = plc_address_operation.get_signal_address_info(self.handler_passive.plc_type, address_info["address"])
        callbacks = plc_address_operation.get_signal_callbacks(address_info["address"])
        signal_value = address_info["signal_value"]
        clean_signal_value = address_info["clean_signal_value"]
        description = address_info["description"]
        _ = "=" * 40
        while True:
            current_value = self.handler_passive.plc.execute_read(**address_info_read, save_log=False)
            if current_value == signal_value:
                self.handler_passive.logger.info("%s 监控到 %s 信号 %s", _, description, _)
                self.handler_passive.get_signal_to_execute_callbacks(callbacks)
                final_step_num = len(callbacks) + 1
                self.handler_passive.logger.info("%s 第 %s 步: 清除%s %s", "-" * 30, final_step_num, description, "-" * 30)
                self.handler_passive.write_clean_signal_value(address_info, clean_signal_value)
                self.handler_passive.logger.info("%s 清除%s 结束 %s", "-" * 30, description, "-" * 30)
                self.handler_passive.logger.info("%s 执行 %s 结束 %s", _, description, _)
            time.sleep(1)

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
                    value = Array(sv_or_dv_instance.base_value_type, sv_or_dv_instance.value)
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
