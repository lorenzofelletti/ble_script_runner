import os
from types import SimpleNamespace

base_path = os.path.realpath(__file__)
base_path = os.path.dirname(base_path)
base_path = os.path.join(base_path, "..")
log_directory = os.path.join(base_path, "logs")

constants_dict = {
    "NOTIFICATION_WINDOW_SIZE": 10, # seconds
    "MAX_RUNNING_TIME": 60 * 60 * 8, # 8 hours
    "my_service_uuid": "0000ffe0-0000-1000-8000-00805f9b34fb",
    "my_char_uuid": "0000ffe1-0000-1000-8000-00805f9b34fb",
    "my_char_desc": "00002902-0000-1000-8000-00805f9b34fb"
}

constants = SimpleNamespace(**constants_dict)
