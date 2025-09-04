# pylint: skip-file
"""示例."""
from inovance_tag.tag_communication import TagCommunication
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment.handler_passive import HandlerPassive


class Example(HandlerPassive):
    """示例 class."""
    def __init__(self):
        control_dict = {
            "cutting": "socket"
        }
        super().__init__(control_dict, open_flag=True)


if __name__ == '__main__':
    Example()
