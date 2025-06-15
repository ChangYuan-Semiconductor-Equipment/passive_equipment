# pylint: skip-file
from inovance_tag.tag_communication import TagCommunication
from socket_cyg.socket_server_asyncio import CygSocketServerAsyncio

from passive_equipment.handler_passive import HandlerPassive


if __name__ == '__main__':
    control_dict = {
        "uploading_tag": TagCommunication("127.0.0.1"),
        "place_solder_sheet": CygSocketServerAsyncio("127.0.0.1", 1830),
        "cutting_tag": TagCommunication("127.0.0.2")
    }
    handler_passive = HandlerPassive(__file__, control_dict, open_flag=False)
