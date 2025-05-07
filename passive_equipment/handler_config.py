# pylint: skip-file
"""配置文件处理器."""
import json
import pathlib
from collections.abc import Callable
from typing import Union, Optional


class HandlerConfig:
    def __init__(self, config_path:str):
        self.config_path = config_path
        self.config_data = self.get_config_data()

    def get_config_data(self) -> dict:
        """获取配置文件内容.

        Returns:
            dict: 配置文件数据.
        """
        with pathlib.Path(self.config_path).open(mode="r", encoding="utf-8") as f:
            conf_dict = json.load(f)
        return conf_dict

    def update_config_sv_value(self, sv_name: str, sv_value: Union[int, str, float, bool]):
        """更新配置文件里的 sv 变量值.

        Args:
            sv_name: sv 名称.
            sv_value: sv 值.
        """
        with pathlib.Path(self.config_path).open(mode="w+", encoding="utf-8") as f:
            self.config_data["status_variable"][sv_name]["value"] = sv_value
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def update_config_dv_value(self, dv_name: str, dv_value: Union[int, str, float, bool]):
        """更新配置文件里的 dv 变量值.

        Args:
            dv_name: dv 名称.
            dv_value: dv 值.
        """
        with pathlib.Path(self.config_path).open(mode="w+", encoding="utf-8") as f:
            self.config_data["data_values"][dv_name]["value"] = dv_value
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def update_config_recipe_id_name(self, recipe_id: Union[int, str], recipe_name: str):
        """更新配置文件里的配方名称.

        Args:
            recipe_id: 配方id.
            recipe_name: 配方名称.
        """
        for recipe_id_name, recipe_info, in self.config_data.items():
            if str(recipe_id) == recipe_id_name.split("_", 1)[0]:
                self.config_data.get("recipes").pop(recipe_id_name)
                break

        with pathlib.Path(self.config_path).open(mode="w+", encoding="utf-8") as f:
            self.config_data["recipes"][f"{recipe_id}_{recipe_name}"] = {}
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def get_config_value(self, key, default=None, parent_name=None) -> Union[str, int, dict, list, None]:
        """根据key获取配置文件里的值.

        Args:
            key(str): 获取值对应的key.
            default: 找不到值时的默认值.
            parent_name: 父级名称.

        Returns:
            Union[str, int, dict, list]: 从配置文件中获取的值.
        """
        if parent_name:
            return self.config_data.get(parent_name).get(key, default)
        return self.config_data.get(key, default)

    def get_monitor_signal_value(self, signal_name: str) -> Union[int, str, bool]:
        """获取要监控 plc 地址的值.

        Args:
            signal_name: 配置文件里给 plc 信号定义的名称.

        Returns:
            Union[int, str, bool]: 返回要监控 plc 地址的值.
        """
        return self.config_data["signal_address"][signal_name]["value"]

    def get_call_backs(self, signal_name: str) -> list:
        """获取 plc 信号的地址.

        Args:
            signal_name: 配置文件里给 plc 信号定义的名称.

        Returns:
            list: call_back 列表.
        """
        return self.config_data["signal_address"][signal_name]["call_backs"]

    def get_signal_address_info(self, signal_name: str, lower_computer_type: str) -> dict:
        """获取信号的地址信息.

        Args:
            signal_name: 信号名称.
            lower_computer_type: 下位机类型.

        Returns:
            dict: 信号的地址信息.
        """
        address_info = self.config_data["signal_address"][signal_name]
        if lower_computer_type == "snap7":
            address_info_expect =  self._get_address_info_snap7(address_info)
        elif lower_computer_type == "tag":
            address_info_expect = self._get_address_info_tag(address_info)
        elif lower_computer_type == "mitsubishi":
            address_info_expect = self._get_address_info_mitsubishi(address_info)
        else:
            address_info_expect = {}
        return address_info_expect

    def get_call_back_address_info(self, call_back: dict, lower_computer_type: str) -> dict:
        """获取具体一个 call_back 的地址信息.

        Args:
            call_back: call_back 信息.
            lower_computer_type: 下位机类型.

        Returns:
            dict: 信号的地址信息.
        """
        call_back_str = json.dumps(call_back)
        if lower_computer_type == "snap7":
            if "premise" in call_back_str:
                return self._get_premise_address_info_snap7(call_back)
            return self._get_address_info_snap7(call_back)
        elif lower_computer_type == "tag":
            if "premise" in call_back_str:
                return self._get_premise_address_info_tag(call_back)
            return self._get_address_info_tag(call_back)
        elif lower_computer_type == "modbus":
            return self._get_address_info_modbus(call_back)
        elif lower_computer_type == "mitsubishi":
            return self._get_address_info_mitsubishi(call_back)
        return {}

    def get_recipe_name_with_id(self, recipe_id: int) -> str:
        """根据配方 id 获取配方名称.

        Args:
            recipe_id: 配方id.

        Returns:
            str: 配方名称.
        """
        recipe_info = self.config_data["recipes"]
        for recipe_id_str, recipe_name in recipe_info.items():
            if recipe_id_str == str(recipe_id):
                return recipe_name
        return ""

    def get_recipe_id_with_name(self, recipe_name: str) -> Optional[int]:
        """根据配方名称获取配方 id.

        Args:
            recipe_name: 配方名称.

        Returns:
            Optional[int]: 配方id.
        """
        recipe_info = self.config_data["recipes"]
        for recipe_id_str, _recipe_name in recipe_info.items():
            if _recipe_name == recipe_name:
                return int(recipe_id_str)
        return None

    def get_all_recipe_names(self) -> list:
        """获取设备的所有配方名称.

        Returns:
            list: 设备的配方名称列表.
        """
        recipe_name_list = []
        for recipe_id_str, recipe_name in self.config_data["all_recipe"].items():
            recipe_name_list.append(recipe_name)
        return recipe_name_list

    @staticmethod
    def _get_address_info_mitsubishi(origin_data_dict) -> dict:
        """获取读取三菱 plc 的地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取三菱 plc 的地址信息.

        """
        return {
            "address": origin_data_dict.get("address"),
            "data_type": origin_data_dict.get("data_type"),
            "size": origin_data_dict.get("size", 1)
        }

    @staticmethod
    def _get_address_info_modbus(origin_data_dict) -> dict:
        """获取读取 modbus 通讯的地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取 modbus 通讯的地址信息.

        """
        return {
            "address": origin_data_dict.get("address"),
            "data_type": origin_data_dict.get("data_type"),
            "size": origin_data_dict.get("size", 1),
            "bit_index": origin_data_dict.get("bit_index", 0)
        }

    @staticmethod
    def _get_address_info_tag(origin_data_dict) -> dict:
        """获取读取汇川标签通讯的地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取汇川标签通讯的地址信息.

        """
        return {
            "tag_name": origin_data_dict.get("address"),
            "data_type": origin_data_dict.get("data_type")
        }

    @staticmethod
    def _get_address_info_snap7(origin_data_dict) -> dict:
        """获取读取S7通讯的地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取S7通讯的地址信息.

        """
        return {
            "address": origin_data_dict.get("address"),
            "data_type": origin_data_dict.get("data_type"),
            "db_num": origin_data_dict("db_num", 1998),
            "size": origin_data_dict.get("size", 2),
            "bit_index": origin_data_dict.get("bit_index", 0)
        }

    @staticmethod
    def _get_premise_address_info_tag(origin_data_dict) -> dict:
        """获取读取汇川标签通讯的 premise 地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取汇川标签通讯的地址信息.

        """
        return {
            "tag_name": origin_data_dict.get("premise_address"),
            "data_type": origin_data_dict.get("premise_data_type")
        }

    @staticmethod
    def _get_premise_address_info_snap7(origin_data_dict) -> dict:
        """获取读取S7通讯的 premise 地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取S7通讯的地址信息.

        """
        return {
            "address": origin_data_dict.get("premise_address"),
            "data_type": origin_data_dict.get("premise_data_type"),
            "db_num": origin_data_dict("db_num", 1998),
            "size": origin_data_dict.get("premise_size", 2),
            "bit_index": origin_data_dict.get("premise_bit_index", 0)
        }

    @staticmethod
    def _get_premise_address_info_mitsubishi(origin_data_dict) -> dict:
        """获取读取S7通讯的 premise 地址信息.

        Args:
            origin_data_dict: 传进来的地址信息.

        Returns:
            dict: 读取S7通讯的地址信息.

        """
        return {
            "address": origin_data_dict.get("premise_address"),
            "data_type": origin_data_dict.get("premise_data_type")
        }
