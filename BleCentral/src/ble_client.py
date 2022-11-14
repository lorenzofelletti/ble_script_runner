import os
import shlex
import subprocess
import time
import logging
import asyncio
from typing import List
from bleak import BleakClient, BLEDevice

from src.constants import constants as consts
from src.constants import log_directory
from src.performance_metrics import devices_discovery_time, latencies

# logging setup
log_file_path = os.path.join(log_directory, "ble_client.log")
logging.basicConfig(filename=log_file_path, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def run_ble_client(device: BLEDevice, queue: asyncio.Queue):
    '''
    Connects to the device and reads the characteristic, then puts the data into the queue
    '''
    async def notification_callback(_, data: bytearray):
        logger.debug(f"putting data:'{data}' in queue")
        await queue.put((time.time(), data))

    logger.debug(f"Attempting connection to {device}")
    print(f"Attempting connection to {device}")

    async with BleakClient(device) as client:
        await client.connect()
        logger.info(f"Connected to {device}")
        connection_time = time.time()
        logger.debug(f"connection time: {connection_time}")
        latencies.append(connection_time - devices_discovery_time[device])
        logger.debug(f"latency: {latencies[-1]}")
        devices_discovery_time.pop(device)

        print(f"Connected to {device}")
        await client.start_notify(consts.my_char_uuid, notification_callback)
        await asyncio.sleep(consts.NOTIFICATION_WINDOW_SIZE)
        print(f"disconnecting from {device}")
        await client.disconnect()
        await queue.put((time.time(), None))


async def run_queue_consumer(queue: asyncio.Queue):
    '''
    Consumes the queue and invokes the script indicated by the queue data
    '''
    def run_script(data: bytearray):
        data: List[str] = shlex.split(data.decode("utf-8"))
        data[0] = f'./scripts/{data[0]}'
        logger.info(f"running script {data}")
        try:
            subprocess.run(data)
        except Exception as e:
            logger.error(e)

    while True:
        epoch, data = await queue.get()
        logger.info(
            f"received data {data} at epoch {epoch}" if data is not None
            else "received exit message")
        if data is None:
            break
        run_script(data)
