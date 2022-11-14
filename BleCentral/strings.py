from types import SimpleNamespace

strings_dict = {
    'app_description': 'Bluetooth Low Energy client searching for devices with \
        a given service uuid and executing a script indicated by the characteristic \
        value on notification. If the script is not found, the client will ignore it.',
    'log_level_help': 'Provide logging level. Example: --log-level DEBUG, default: INFO',
    'log_file_help': 'Provide logging file. Example: --log-file /tmp/main.log',
    'notification_window_size_help': 'Provide notification window size (in seconds). \
        Example: --notification-window-size 20. Default: 10',
    'max_running_time_help': 'Provide max running time (in seconds), i.e. the time after\
        which the client will exit. Example: --max-running-time 60. Default: 8h (28800s)',
}

strings = SimpleNamespace(**strings_dict)
