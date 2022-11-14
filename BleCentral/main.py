import logging
import os
import shlex
import subprocess
import asyncio
from sys import argv
import time
from typing import List, Optional
from bleak import BLEDevice

from src.constants import constants as c, log_directory
from src.app import app
from src.utilities import has_max_running_time_elapsed_builder
from src.performance_metrics import latencies

# logging setup
log_file_path = os.path.join(log_directory, "main.log")
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(
        filename=log_file_path, level=logging.DEBUG)

    logger.debug(f"Searched service uuid: {c.my_service_uuid}")
    logger.debug(f"Searched characteristic uuid: {c.my_char_uuid}")
    logger.debug(f"With characteristic descriptor uuid: {c.my_char_desc}")

    # set the notification window size
    if len(argv) > 1:
        if argv[1].isdigit():
            NOTIFICATION_WINDOW_SIZE = int(argv[1])
    logger.info(f"notification window size set to {NOTIFICATION_WINDOW_SIZE}")

    has_max_running_time_elapsed = has_max_running_time_elapsed_builder(
        start_time=time.time(), max_running_time=c.max_running_time)
    while True:
        logger.info(f"starting app")
        asyncio.run(app())
        logger.info(f"app finished")
        if has_max_running_time_elapsed():
            logger.info(f"max running time reached, exiting")
            break

    mean_latency = sum(latencies) / len(latencies)
    logger.debug(f"mean connection latency: {mean_latency}")
    print(f"mean connection latency: {mean_latency}")
