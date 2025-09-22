# pylint: skip-file
from typing import Any, Optional

from secsgem import gem

from passive_equipment import models_class, common_func
from passive_equipment.enum_sece_data_type import EnumSecsDataType
from passive_equipment.factory import get_mysql_secs


def get_sv_list() -> list[dict[int, gem.StatusVariable]]:
    """获取所有的 sv.

    Returns:
        list[dict[int, gem.StatusVariable]]: 返回 sv 列表.
    """
    mysql = get_mysql_secs()
    sv_list = mysql.query_data(models_class.SvList)
    sv_list_return = []
    for sv in sv_list:
        sv_id = sv["sv_id"]
        sv_dict = {
            "svid": sv_id, "name": sv["sv_name"], "unit": "",
            "value_type": getattr(EnumSecsDataType, sv["value_type"]).value,
            "value": common_func.parse_value(sv["value"], sv["value_type"])
        }
        sv_list_return.append({sv_id: gem.StatusVariable(**sv_dict)})
    return sv_list_return


def get_dv_info(filter_dict: dict) -> Optional[dict[str, Any]]:
    """根据条件获取 dv 信息.

    Returns:
        Optional[dict[str, Any]]: 返回 dv 信息, 查询不到返回 None.
    """
    mysql = get_mysql_secs()
    dv_list = mysql.query_data(models_class.DvList, filter_dict)
    if dv_list:
        return dv_list[0]
    return None

def get_dv_list() -> list[dict[int, gem.DataValue]]:
    """获取所有的 dv.

    Returns:
        list[dict[int, gem.DataValue]]: 返回 dv 列表.
    """
    mysql = get_mysql_secs()
    dv_list = mysql.query_data(models_class.DvList)
    dv_list_return = []
    for dv in dv_list:
        dv_id = dv["dv_id"]
        dv_dict = {
            "dvid": dv_id, "name": dv["dv_name"],
            "value_type": getattr(EnumSecsDataType, dv["value_type"]).value,
            "base_value_type": getattr(EnumSecsDataType, dv["base_value_type"]).value,
            "value": common_func.parse_value(dv["value"], dv["value_type"])
        }
        dv_list_return.append({dv_id: gem.DataValue(**dv_dict)})
    return dv_list_return


def get_ec_list() -> list[dict[int, gem.EquipmentConstant]]:
    """获取所有的 ec.

    Returns:
        list[dict[int, gem.EquipmentConstant]]: 返回 ec 列表.
    """
    mysql = get_mysql_secs()
    ec_list = mysql.query_data(models_class.EcList)
    ec_list_return = []
    for ec in ec_list:
        ec_id = ec["ec_id"]
        ec_value = common_func.parse_value(ec["value"], ec["value_type"])
        ec_dict = {
            "ecid": ec_id, "name": ec["ec_name"], "unit": "",
            "min_value": 0, "max_value": 0, "default_value": ec_value,
            "value_type": getattr(EnumSecsDataType, ec["value_type"]).value
        }
        ec_list_return.append({ec_id: gem.EquipmentConstant(**ec_dict)})
    return ec_list_return


def get_event_list() -> list[dict[int, gem.CollectionEvent]]:
    """获取所有的事件.

    Returns:
        list[dict[int, gem.CollectionEvent]]: 返回事件列表.
    """
    mysql = get_mysql_secs()
    event_list = mysql.query_data(models_class.EventList)
    event_list_return = []
    for event in event_list:
        event_id = event["event_id"]
        associate_report_id = int(event["associate_report"])
        report_info = mysql.query_data(models_class.ReportList, {"report_id": associate_report_id})[0]
        associate_sv_dv = report_info["associate_sv"] + report_info["associate_dv"]
        link_reports = {associate_report_id: [int(_) for _ in associate_sv_dv.split(",")]}
        event_dict = {
            "ceid": event_id, "name": event["event_name"], "data_values": [], "link_reports": link_reports
        }
        event_list_return.append({event_id: gem.CollectionEvent(**event_dict)})
    return event_list_return


def get_remote_command_list() -> list[dict[str, gem.RemoteCommand]]:
    """获取所有的远程命令.

    Returns:
        list[dict[str, gem.RemoteCommand]]: 返回远程命令列表.
    """
    mysql = get_mysql_secs()
    rc_list = mysql.query_data(models_class.RemoteCommandList)
    rc_list_return = []
    for rc in rc_list:
        rcmd = rc["remote_command"]
        params = rc["parameters"].split(",") if rc["parameters"] else []
        rc_dict = {
            "rcmd": rcmd, "name": rcmd, "params": params, "ce_finished": ""
        }
        rc_list_return.append({rcmd: gem.RemoteCommand(**rc_dict)})
    return rc_list_return


def get_alarm_list() -> list[dict[str, gem.Alarm]]:
    """获取所有的报警.

    Returns:
        list[dict[str, gem.Alarm]]: 返回报警列表.
    """
    mysql = get_mysql_secs()
    alarm_list = mysql.query_data(models_class.AlarmList)
    alarm_list_return = []
    for alarm in alarm_list:
        alid = alarm["alarm_id"]
        alarm_dict = {
            "alid": alid, "name": alid, "text": alarm["alarm_text_en"],
            "code": 128, "ce_on": "", "ce_off": "", "text_zh": alarm["alarm_text_zh"]
        }
        alarm_list_return.append({alid: gem.Alarm(**alarm_dict)})
    return alarm_list_return


def get_recipe_list() -> list[str]:
    """获取所有的配方名称.

    Returns:
        list[str]: 返回所有的配方名称.
    """
    mysql = get_mysql_secs()
    recipe_list = mysql.query_data(models_class.Recipes)
    recipe_list_return = []
    for recipe in recipe_list:
        recipe_list_return.append(recipe["recipe_name"])
    return recipe_list_return


def get_recipe_name_with_id(recipe_id: int) -> str:
    """根据配方 id 获取配方名称.

    Args:
        recipe_id: 配方id.

    Returns:
        str: 返回配方名称.
    """
    mysql = get_mysql_secs()
    recipe_list = mysql.query_data(models_class.Recipes)
    for recipe in recipe_list:
        if recipe["recipe_id"] == recipe_id:
            return recipe["recipe_name"]
    return ""


def get_recipe_id_with_name(recipe_name: str) -> int:
    """根据配方名称获取配方 id.

    Args:
        recipe_name: 配方名称.

    Returns:
        int: 返回配方 id.
    """
    mysql = get_mysql_secs()
    recipe_list = mysql.query_data(models_class.Recipes)
    for recipe in recipe_list:
        if recipe["recipe_name"] == recipe_name:
            return recipe["recipe_id"]
    return 0
