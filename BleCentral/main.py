import logging
import os
import argparse
import shlex
import subprocess
import asyncio
from sys import argv
import time
from typing import List, Optional
from bleak import AdvertisementData, BLEDevice, BleakClient, BleakScanner

from config import APP_CONFIG as C
from strings import strings as s


logger = logging.getLogger(__name__)


# variables to meter the connection latency
devices_discovery_time: dict[BLEDevice, Optional[float]] = {}
latencies: List[float] = []


def device_has_service(advertising_data: AdvertisementData, service_uuid: str) -> bool:
    '''
    Checks if the device advertises the service with the given uuid
    '''
    return service_uuid in advertising_data.service_uuids


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
        await client.start_notify(C.CHAR_UUID, notification_callback)
        await asyncio.sleep(C.NOTIFICATION_WINDOW_SIZE)
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


async def app():
    '''
    Scan for devices with a given service uuid, then connect to them and read the characteristic
    on notification, then invoke the script indicated by the characteristic.
    '''
    logger.info(f"scanning for devices")

    device_to_connect_to: Optional[BLEDevice] = None
    stop_event = asyncio.Event()

    def scan_callback(device: BLEDevice, advertising_data: AdvertisementData):
        nonlocal device_to_connect_to
        logger.info(f"found device {device}")

        if not device_has_service(advertising_data, C.SERVICE_UUID):
            logger.info(
                f"device {device} does not have service {C.SERVICE_UUID}")
            return

        logger.info(f"device {device} has service {C.SERVICE_UUID}")
        if devices_discovery_time.get(device) is None:
            devices_discovery_time[device] = time.time()
            logger.debug(
                f"discovery time: {devices_discovery_time[device]}")

        device_to_connect_to = device
        stop_event.set()  # awakens stop_event.wait()

    async with BleakScanner(scan_callback, service_uuids=[C.SERVICE_UUID]) as _:
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()

    if isinstance(device_to_connect_to, BLEDevice):
        queue = asyncio.Queue()
        client_task = run_ble_client(device_to_connect_to, queue)
        consumer_task = run_queue_consumer(queue)
        await asyncio.gather(client_task, consumer_task)


def has_max_running_time_elapsed_builder(start_time: float, max_running_time: int) -> callable:
    '''
    Returns a function that checks if the max running time has elapsed
    '''
    def has_max_running_time_elapsed() -> bool:
        return time.time() - start_time > max_running_time
    return has_max_running_time_elapsed


if __name__ == "__main__":
    # Command line arguments parsing
    parser = argparse.ArgumentParser(description=s.app_description)
    parser.add_argument("--log-level", default="INFO", help=s.log_level_help)
    parser.add_argument("--log-file", default=C.LOG_FILE, help=s.log_file_help)
    parser.add_argument("--notification-window-size", default=C.NOTIFICATION_WINDOW_SIZE,
                        type=int, help=s.notification_window_size_help)
    parser.add_argument("--max-running-time", default=C.MAX_RUNNING_TIME,
                        type=int, help=s.max_running_time_help)

    args = parser.parse_args(argv[1:])

    # Configuration setup
    C.LOG_LEVEL = args.log_level
    C.LOG_FILE = args.log_file
    C.NOTIFICATION_WINDOW_SIZE = args.notification_window_size
    C.MAX_RUNNING_TIME = args.max_running_time

    logging.basicConfig(filename=C.LOG_FILE, level=C.LOG_LEVEL)

    logger.debug(f"Searched service uuid: {C.SERVICE_UUID}")
    logger.debug(f"Searched characteristic uuid: {C.CHAR_UUID}")
    logger.debug(f"With characteristic descriptor uuid: {C.CHAR_DESC_UUID}")
    logger.info(f"notification window size set to {C.NOTIFICATION_WINDOW_SIZE}")

    has_max_running_time_elapsed = has_max_running_time_elapsed_builder(
        start_time=time.time(), max_running_time=C.MAX_RUNNING_TIME)
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
