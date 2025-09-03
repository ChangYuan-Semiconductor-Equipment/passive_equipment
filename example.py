# pylint: skip-file
"""示例."""
from inovance_tag.tag_communication import TagCommunication
from passive_equipment.handler_passive import HandlerPassive


class Example(HandlerPassive):
    """示例 class."""
    def __init__(self):
        control_dict = {
            "cutting_tag": TagCommunication("10.21.142.60")
        }
        super().__init__(control_dict, open_flag=False)


if __name__ == '__main__':
    Example()
