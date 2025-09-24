# pylint: skip-file
from operator import itemgetter
from typing import Any, Optional

from passive_equipment import models_class
from passive_equipment.factory import get_mysql_secs


def get_mes_herat(equipment_name) -> Optional[dict[str, Any]]:
    """获取 MES 心跳地址信息.

    Returns:
       Optional[dict[str, Any]]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.MesAddressList, {"description": "MES 心跳"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_control_state(equipment_name) -> Optional[dict[str, Any]]:
    """获取控制状态地址信息.

    Returns:
        Optional[dict[str, Any]]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.PlcAddressList, {"description": "设备的控制状态"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_recipe_address_info(equipment_name) -> Optional[dict[str, Any]]:
    """获取配方 id 地址信息.

    Returns:
        Optional[dict[str, Any]]: 返回 配方 id 地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.PlcAddressList, {"description": "当前配方id"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_do_quantity_address_info(equipment_name) -> Optional[dict[str, Any]]:
    """获取已生产数量地址信息.

    Returns:
        Optional[dict[str, Any]]: 返回 已生产数量地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.PlcAddressList, {"description": "当前设备已生产的工单数量"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_machine_state(equipment_name) -> Optional[dict[str, Any]]:
    """获取运行状态地址信息.

    Returns:
         Optional[dict[str, Any]]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.PlcAddressList, {"description": "设备的运行状态"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_alarm_address_info(equipment_name) -> Optional[dict[str, Any]]:
    """获取报警地址信息.

    Returns:
        Optional[dict[str, Any]]: 返回 获取报警地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.PlcAddressList, {"description": "出现报警时报警 id"})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_signal_address_list() -> list[dict]:
    """获取所有的信号地址.

    Returns:
        list[dict]: 返回所有的信号地址.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.SignalAddressList)
    return address_info_list


def get_signal_address_info(equipment_name, address: str) -> Optional[dict[str, Any]]:
    """获取信号地址信息.

    Args:
        equipment_name: 设备名称.
        address: 地址.

    Returns:
        Optional[dict[str, Any]]: 返回信号地址信息.
    """
    mysql = get_mysql_secs()
    address_info_list = mysql.query_data(models_class.SignalAddressList, {"address": address})
    if address_info_list:
        address_info = address_info_list[0]
        return get_address_info(equipment_name, address_info)
    return None


def get_signal_callbacks(address: str) -> list:
    """获取信号的流程信息.

    Args:
        address: 信号地址.

    Returns:
        list: 返回排序后的 call back 列表.
    """
    mysql = get_mysql_secs()
    models_class_flow_func = models_class.FlowFunc
    filter_dict = {"associate_signal": address}
    callbacks_plc = mysql.query_data(models_class.PlcAddressList, filter_dict)
    callbacks_mes = mysql.query_data(models_class.MesAddressList, filter_dict)
    callbacks_flow_func = mysql.query_data(models_class_flow_func, filter_dict)
    callbacks = callbacks_plc + callbacks_mes + callbacks_flow_func
    callbacks_return = sorted(callbacks, key=itemgetter("step"))
    return callbacks_return


def get_address_info(equipment_name, address_info) -> dict[str, Any]:
    """根据数据库查询的地址信息获取整理后的地址信息.

    Args:
        equipment_name: 设备名称.
        address_info: 数据库获取的地址信息

    Returns:
        dict[str, Any]: 整理后的地址信息.
    """
    if "tag" in equipment_name:
        address_info_expect = {"address": address_info["address"], "data_type": address_info["data_type"]}
    elif "snap7" in equipment_name:
        address_info_expect = {
            "address": address_info["address"], "data_type": address_info["data_type"],
            "size": address_info.get("size", 2), "db_num": address_info.get("db_num", 1998),
            "bit_index": address_info.get("bit_index", 0)
        }
    elif "mitsubishi" in equipment_name:
        address_info_expect = {
            "address": address_info["address"], "data_type": address_info["data_type"],
            "size": address_info["size"]
        }
    elif "modbus" in equipment_name:
        address_info_expect = {
            "address": address_info["address"], "data_type": address_info["data_type"],
            "size": address_info["size"], "bit_index": address_info["bit_index"]
        }
    else:
        address_info_expect = {}
    return address_info_expect
