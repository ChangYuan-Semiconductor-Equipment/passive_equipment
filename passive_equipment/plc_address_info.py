# pylint: skip-file
from typing import Union, Any


class InovanceTagRead:
    """读取汇川 plc 标签通讯地址信息 class."""

    def __init__(self, address: str, data_type: str):
        """读取汇川plc标签通讯地址信息 class 构造函数.

        Args:
            address: 标签地址.
            data_type: 地址值数据类型.
        """
        self.address = address
        self.data_type = data_type


class InovanceTagWrite:
    """写入汇川 plc 标签通讯地址信息 class."""

    def __init__(self, address: str, data_type: str, value: Union[str, int, float, bool]):
        """读取汇川plc标签通讯地址信息 class 构造函数.

        Args:
            address: 标签地址.
            data_type: 地址值数据类型.
        """
        self.address = address
        self.data_type = data_type
        self.value = value


class ModbusRead:
    """读取 modbus 通讯地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int, bit_index: int = 0):
        """读取 modbus 通讯地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
            bit_index: bool 类型时 bit 位.
        """
        self.address = address
        self.data_type = data_type
        self.size = size
        self.bit_index = bit_index


class ModbusWrite:
    """写入 modbus 通讯地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int, value: Any, bit_index: int = 0):
        """写入 modbus 通讯地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
            value: 写入值.
            bit_index: bool 类型时 bit 位.
        """
        self.address = address
        self.data_type = data_type
        self.size = size
        self.value = value
        self.bit_index = bit_index


class Snap7Read:
    """读取 Snap7 通讯地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int, db_num: int, bit_index: int = 0):
        """读取 Snap7 通讯地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
            db_num: db_num
            bit_index: bool 类型时 bit 位.
        """
        self.address = address
        self.data_type = data_type
        self.size = size
        self.db_num = db_num
        self.bit_index = bit_index


class Snap7Write:
    """写入 Snap7 通讯地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int, db_num: int, value: Any, bit_index: int = 0):
        """写入 Snap7 通讯地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
            db_num: db_num
            value: 写入值.
            bit_index: bool 类型时 bit 位.
        """
        self.address = address
        self.data_type = data_type
        self.size = size
        self.db_num = db_num
        self.value = value
        self.bit_index = bit_index


class MitsubishiRead:
    """读取三菱 plc 地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int):
        """读取三菱 plc 地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
        """
        self.address = address
        self.data_type = data_type
        self.size = size

class MitsubishiWrite:
    """写入三菱 plc 地址信息 class."""

    def __init__(self, address: int, data_type: str, size: int, value: Any):
        """写入三菱 plc 地址信息 class 构造函数.

        Args:
            address: 地址.
            data_type: 地址值数据类型.
            size: 地址长度.
            value: 写入值.
        """
        self.address = address
        self.data_type = data_type
        self.size = size
        self.value = value
