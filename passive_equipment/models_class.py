# pylint: skip-file
"""数据表模型."""
import datetime

from mysql_api.mysql_database import MySQLDatabase
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base

BASE = declarative_base()
mysql_api = MySQLDatabase("root", "liuwei.520")


class EquipmentState(BASE):
    """Mes 状态模型."""
    __tablename__ = "equipment_state"
    __table_args__ = {"comment": "设备状态表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    eap_state = Column(Integer, nullable=True, comment="0: plc 离线, 1: 本地模式, 2: 远程模式")
    machine_state = Column(Integer, nullable=True, comment="1: Manual, 2: Auto, 3: Auto Run, 4: Alarm")
    mes_state = Column(Integer, nullable=True, comment="0: 设备 MES 服务未打开, 1: 设备 MES 服务已打开")

    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class LotList(BASE):
    """工单列表模型."""
    __tablename__ = "lot_list"
    __table_args__ = {"comment": "工单列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    lot_name = Column(String(50),  unique=True, comment="工单名称")
    recipe_name = Column(String(50), nullable=True, comment="配方名称")
    lot_quantity = Column(Integer, nullable=True, comment="工单数量")
    lot_state = Column(Integer, nullable=True, default=1, comment="工单状态")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class SvList(BASE):
    """SV列表模型."""
    __tablename__ = "sv_list"
    __table_args__ = {"comment": "sv 列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    sv_id = Column(Integer, nullable=True, comment="sv id")
    sv_name = Column(String(50), nullable=True, comment="sv 名称")
    value_type = Column(String(50), nullable=True, comment="sv 值类型")
    base_value_type = Column(String(50), nullable=True, comment="若 sv 值类型是 ARRAY, 子元素值类型")
    value = Column(JSON, nullable=True, comment="sv 值")
    description = Column(String(250), nullable=True, comment="sv 描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class DvList(BASE):
    """SV列表模型."""
    __tablename__ = "dv_list"
    __table_args__ = {"comment": "dv 列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    dv_id = Column(Integer, nullable=True, comment="dv id")
    dv_name = Column(String(50), nullable=True, comment="dv 名称")
    value_type = Column(String(50), nullable=True, comment="dv 值类型")
    base_value_type = Column(String(50), nullable=True, comment="若 dv 值类型是 ARRAY, 子元素值类型")
    value = Column(JSON, nullable=True, comment="dv 值")
    description = Column(String(250), nullable=True, comment="dv 描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class EcList(BASE):
    """EC列表模型."""
    __tablename__ = "ec_list"
    __table_args__ = {"comment": "ec 列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    ec_id = Column(Integer, nullable=True, comment="ec id")
    ec_name = Column(String(50), nullable=True, comment="ec 名称")
    value_type = Column(String(50), nullable=True, comment="ec 值类型")
    value = Column(JSON, nullable=True, comment="ec 值")
    description = Column(String(250), nullable=True, comment="ec 描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class ReportList(BASE):
    """报告列表模型."""
    __tablename__ = "report_list"
    __table_args__ = {"comment": "报告列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    report_id = Column(Integer, nullable=True, comment="报告 id")
    associate_sv = Column(String(250), nullable=True, comment="关联的 sv")
    associate_dv = Column(String(250), nullable=True, comment="关联的 dv")
    description = Column(String(250), nullable=True, comment="报告描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventList(BASE):
    """事件列表模型."""
    __tablename__ = "event_list"
    __table_args__ = {"comment": "事件列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    event_id = Column(Integer, nullable=True, comment="事件 id")
    event_name = Column(String(250), nullable=True, comment="事件名称")
    associate_report = Column(String(250), nullable=True, comment="关联的报告")
    description = Column(String(250), nullable=True, comment="报告描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class RemoteCommandList(BASE):
    """远程命令列表模型."""
    __tablename__ = "remote_command_list"
    __table_args__ = {"comment": "远程命令列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    remote_command = Column(String(250), nullable=True, comment="远程命令")
    parameters = Column(String(520), nullable=True, comment="要传入的参数")
    description = Column(String(250), nullable=True, comment="远程命令描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class AlarmList(BASE):
    """报警信息模型."""
    __tablename__ = "alarm_list"
    __table_args__ = {"comment": "报警信息模型"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    alarm_id = Column(Integer, nullable=True, unique=True, comment="报警 id")
    alarm_text_zh = Column(String(520), nullable=True, comment="中文报警内容")
    alarm_text_en = Column(String(520), nullable=True, comment="英文报警内容")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class AlarmRecordList(BASE):
    """报警信息模型."""
    __tablename__ = "alarm_record_list"
    __table_args__ = {"comment": "设备报警记录模型"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    alarm_id = Column(Integer, nullable=True, comment="报警 id")
    alarm_text = Column(String(520), nullable=True, comment="报警内容")
    created_at = Column(DateTime, default=datetime.datetime.now)


class PlcAddressList(BASE):
    """PLC plc 2 mes 地址列表模型."""
    __tablename__ = "plc_address_list"
    __table_args__ = {"comment": "plc 2 mes 地址列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    address = Column(String(250), nullable=True, comment="标签地址")
    data_type = Column(
        String(250), nullable=True,
        comment="标签地址值数据类型: bool, string, sint, int, dint, lint, byte, word, dword, lword, real, lreal"
    )
    bit_index = Column(Integer, nullable=True, comment="bool 类型的 bit 位")
    size = Column(Integer, nullable=True, comment="地址大小")
    count_num = Column(Integer, nullable=True, default=1, comment="当这个地址连续时, 代表连续读或写几个")
    gap = Column(Integer, nullable=True, default=1, comment="当这个地址连续时, 每两个地址的见间隔大小")
    operation_type = Column(String(50), nullable=True, comment="操作地址的方式, 读或写(read or write)")
    associate_sv_or_dv = Column(String(250), nullable=True, comment="关联的 sv 或 dv")
    associate_signal = Column(String(250), nullable=True, comment="关联信号")
    step = Column(Integer, nullable=True, comment="所属信号的第几步流程")
    event_id = Column(Integer, nullable=True, comment="要发送的事件id")
    description = Column(String(250), nullable=True, comment="地址描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class MesAddressList(BASE):
    """PLC plc 2 mes 地址列表模型."""
    __tablename__ = "mes_address_list"
    __table_args__ = {"comment": "mes 2 plc 地址列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    address = Column(String(250), nullable=True, comment="标签地址")
    data_type = Column(
        String(250), nullable=True,
        comment="标签地址值数据类型: bool, string, sint, int, dint, lint, byte, word, dword, lword, real, lreal"
    )
    size = Column(Integer, nullable=True, comment="地址大小")
    count_num = Column(Integer, nullable=True, default=1, comment="当这个地址连续时, 代表连续读或写几个")
    gap = Column(Integer, nullable=True, default=1, comment="当这个地址连续时, 每两个地址的见间隔大小")
    operation_type = Column(String(50), nullable=True, comment="操作地址的方式, 读或写(read or write)")
    associate_sv_or_dv = Column(String(250), nullable=True, comment="关联的 sv 或 dv")
    associate_signal = Column(String(250), nullable=True, comment="关联信号")
    step = Column(Integer, nullable=True, comment="所属信号的第几步流程")
    event_id = Column(Integer, nullable=True, comment="要发送的事件id")
    description = Column(String(250), nullable=True, comment="地址描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class SignalAddressList(BASE):
    """PLC 信号地址列表模型."""
    __tablename__ = "signal_address_list"
    __table_args__ = {"comment": "PLC 信号地址列表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    address = Column(String(250), nullable=True, comment="标签地址")
    data_type = Column(
        String(250), nullable=True,
        comment="标签地址值数据类型: bool, string, sint, int, dint, lint, byte, word, dword, lword, real, lreal"
    )
    signal_value = Column(Integer, nullable=True, comment="监控信号值")
    clean_signal_value = Column(Integer, nullable=True, comment="清除信号值")
    state = Column(Integer, nullable=True, comment="是否监控地址信号, 1: 监控, 0: 不监控")
    description = Column(String(250), nullable=True, comment="地址描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class FlowFunc(BASE):
    """流程函数的表模型."""
    __tablename__ = "flow_func"
    __table_args__ = {"comment": "流程函数的表模型"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    func_name = Column(String(50), nullable=True, comment="函数名称")
    associate_dv = Column(String(250), nullable=True, comment="关联dv")
    associate_signal = Column(String(250), nullable=True, comment="关联信号")
    step = Column(Integer, nullable=True, comment="所属信号的第几步流程")
    is_wait = Column(Integer, nullable=True, comment="是否需要等待 eap 回复, 1: 需要, 0: 不需要")
    description = Column(String(250), nullable=True, comment="函数描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


class Recipes(BASE):
    """配方表模型."""
    __tablename__ = "recipes"
    __table_args__ = {"comment": "配方表模型"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    recipe_id = Column(Integer, nullable=True, unique=True, comment="配方 id")
    recipe_name = Column(String(50), nullable=True, comment="配方名称")
    description = Column(String(250), nullable=True, comment="描述信息")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)
