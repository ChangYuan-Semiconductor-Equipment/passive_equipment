# pylint: skip-file
"""数据表模型."""
import datetime

from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base


BASE = declarative_base()

class EquipmentState(BASE):
    """Mes 状态模型."""
    __tablename__ = "equipment_state"
    __table_args__ = {"comment": "设备状态表"}

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    control_state = Column(Integer, nullable=True, comment="0: plc 离线, 1: 本地模式, 2: 远程模式")
    control_state_message = Column(String(50), nullable=True, comment="设备控制状态描述信息")
    machine_state = Column(Integer, nullable=True, comment="1: Manual, 2: Auto, 3: Auto Run, 4: Alarm")
    machine_state_message = Column(String(50), nullable=True, comment="设备运行状态描述信息")
    eap_connect_state = Column(Integer, nullable=True, comment="0: 未连接, 1: eap 已连接")
    eap_connect_state_message = Column(String(50), nullable=True, comment="eap 连接 mes 服务描述信息")
    mes_state = Column(Integer, nullable=True, comment="0: 设备 MES 服务未打开, 1: 设备 MES 服务已打开")
    mes_state_message = Column(String(50), nullable=True, comment="设备 MES 服务状态信息")

    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)

    def as_dict_all(self):
        """获取字典形式的数据."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns.values()}

    def as_dict_include(self, include_fields: list) -> dict:
        """获取字典形式的数据，支持排除指定字段。

        Args:
            include_fields: 获取指定字段值.

        Returns:
            dict: 字典形式的数据.
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns.values()
            if column.name in include_fields
        }

    def as_dict_exclude(self, exclude_fields: list) -> dict:
        """获取字典形式的数据，支持排除指定字段。

        Args:
            exclude_fields: 需要排除的字段列表, 默认为 ["id", "updated_at", "created_at"]

        Returns:
            dict: 字典形式的数据.
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns.values()
            if column.name not in exclude_fields
        }