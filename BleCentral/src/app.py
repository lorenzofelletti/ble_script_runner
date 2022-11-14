import os
import logging
import asyncio
import time
from typing import Optional
from bleak import BleakScanner, BLEDevice, AdvertisementData

from src.constants import constants as c, log_directory
from src.performance_metrics import devices_discovery_time, latencies
from src.ble_client import run_ble_client, run_queue_consumer
from src.utilities import device_has_service

# logging setup
log_file_path = os.path.join(log_directory, "app.log")
logging.basicConfig(filename=log_file_path, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def app():
    '''
    Scan for devices with a given service uuid, then connect to them and read the characteristic
    on notification, then invoke the script indicated by the characteristic.
    '''
    logger.info(f"scanning for devices")

    device_to_connect_to: Optional[BLEDevice] = None
    stop_event = asyncio.Event()

    def scan_callback(device: BLEDevice, _: AdvertisementData):
        nonlocal device_to_connect_to
        logger.info(f"found device {device}")

        if not device_has_service(device, c.my_service_uuid):
            logger.info(f"device {device} does not have service {c.my_service_uuid}")
            return

        logger.info(f"with service {c.my_service_uuid}")
        if devices_discovery_time.get(device) is None:
            devices_discovery_time[device] = time.time()
            logger.debug(
                f"discovery time: {devices_discovery_time[device]}")

        device_to_connect_to = device
        stop_event.set()  # awakens stop_event.wait()

    async with BleakScanner(scan_callback, service_uuids=[c.my_service_uuid]) as _:
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()

    if isinstance(device_to_connect_to, BLEDevice):
        queue = asyncio.Queue()
        client_task = run_ble_client(device_to_connect_to, queue)
        consumer_task = run_queue_consumer(queue)
        await asyncio.gather(client_task, consumer_task)
