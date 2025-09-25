# pylint: skip-file
"""示例."""
from siemens_plc.s7_plc import S7PLC

from passive_equipment.handler_passive import HandlerPassive


class Example(HandlerPassive):
    """示例 class."""
    def __init__(self):
        super().__init__("upload_snap7", S7PLC("192.168.180.170"), open_flag=False)


if __name__ == '__main__':
    Example()
