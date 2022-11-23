import os
import platform
from types import SimpleNamespace


base_path = os.path.realpath(__file__)
base_path = os.path.dirname(base_path)

default_log_file = os.path.join(base_path, "main.log")
default_script_dir_path = os.path.join(base_path, "scripts")

scripts_extensions = {
    'Windows': '.ps1',
    'Linux': '.sh',
    'Darwin': '.sh',
}

app_config_dict = {
    'PLATFORM': platform.system(),
    'NOTIFICATION_WINDOW_SIZE': 10,  # seconds
    'MAX_RUNNING_TIME': 60 * 60 * 8,  # 8h
    'LOG_LEVEL': 'INFO',
    'LOG_FILE': default_log_file,
    'SCRIPT_DIR_PATH': default_script_dir_path,
    'SERVICE_UUID': "0000ffe0-0000-1000-8000-00805f9b34fb",
    'CHAR_UUID': "0000ffe1-0000-1000-8000-00805f9b34fb",
    'CHAR_DESC_UUID': "00002902-0000-1000-8000-00805f9b34fb",
    'CHAR_MONITORING_UUID': "0000ffe2-0000-1000-8000-00805f9b34fb",
}

APP_CONFIG = SimpleNamespace(**app_config_dict)
