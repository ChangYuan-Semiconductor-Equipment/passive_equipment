# pylint: skip-file
from operator import itemgetter
from typing import Any

from passive_equipment import models_class, plc_address_info
from passive_equipment.factory import get_mysql_secs


def get_mes_herat(equipment_name) -> dict[str, Any]:
    """获取 MES 心跳地址信息.

    Returns:
        dict[str, Any]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}MesAddressList")
    address_info_list = mysql.query_data(models_class_instance, {"description": "MES 心跳"})
    address_info = address_info_list[0]
    return get_address_info(equipment_name, address_info)


def get_control_state(equipment_name) -> dict[str, Any]:
    """获取控制状态地址信息.

    Returns:
        dict[str, Any]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}PlcAddressList")
    address_info_list = mysql.query_data(models_class_instance, {"description": "设备的控制状态"})
    address_info = address_info_list[0]
    return get_address_info(equipment_name, address_info)


def get_machine_state(equipment_name) -> dict[str, Any]:
    """获取运行状态地址信息.

    Returns:
        dict[str, Any]: 返回 MES 心跳地址信息.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}PlcAddressList")
    address_info_list = mysql.query_data(models_class_instance, {"description": "设备的运行状态"})
    address_info = address_info_list[0]
    return get_address_info(equipment_name, address_info)


def get_alarm_address_info(equipment_name) -> dict[str, Any]:
    """获取报警地址信息.

    Returns:
        dict[str, Any]: 返回 获取报警地址信息.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}PlcAddressList")
    address_info_list = mysql.query_data(models_class_instance, {"description": "报警 id"})
    address_info = address_info_list[0]
    return get_address_info(equipment_name, address_info)


def get_signal_address_list(equipment_name) -> list[dict]:
    """获取所有的信号地址.

    Returns:
        list[dict]: 返回所有的信号地址.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}SignalAddressList")
    address_info_list = mysql.query_data(models_class_instance)
    return address_info_list


def get_signal_address_info(equipment_name, address: str) -> dict[str, Any]:
    """获取信号地址信息.

    Args:
        equipment_name: 设备名称.
        address: 地址.

    Returns:
        dict[str, Any]: 返回信号地址信息.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_instance = getattr(models_class, f"{flag}SignalAddressList")
    address_info_list = mysql.query_data(models_class_instance, {"address": address})
    address_info = address_info_list[0]
    return get_address_info(equipment_name, address_info)


def get_signal_callbacks(equipment_name, address: str) -> list[dict[str, Any]]:
    """获取信号的流程信息.

    Args:
        equipment_name: 设备名称.
        address: 信号地址.
    """
    mysql = get_mysql_secs()
    flag = equipment_name.split("_")[0].capitalize()
    models_class_plc = getattr(models_class, f"{flag}PlcAddressList")
    models_class_mes = getattr(models_class, f"{flag}MesAddressList")
    models_class_flow_func = models_class.FlowFunc
    filter_dict = {"associate_signal": address}
    callbacks_plc = mysql.query_data(models_class_plc, filter_dict)
    callbacks_mes = mysql.query_data(models_class_mes, filter_dict)
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
    if "inovance" in equipment_name:
        address_info_expect = {"address": address_info["address"], "data_type": address_info["data_type"]}
    elif "snap7" in equipment_name:
        address_info_expect = {
            "address": address_info["address"], "data_type": address_info["data_type"],
            "size": address_info["size"], "db_num": address_info["db_num"],
            "bit_index": address_info["bit_index"]
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


if __name__ == '__main__':
    get_signal_callbacks("inovance_aaa", "Application.gvl_OPMODE01_MES.mes2plc.TrackOut")