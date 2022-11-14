import logging
import os
import shlex
import subprocess
import asyncio
from sys import argv
import time
from typing import List, Optional
from bleak import AdvertisementData, BLEDevice, BleakClient, BleakScanner

# Time the notification of the ble characteristic is active
NOTIFICATION_WINDOW_SIZE = 10  # seconds
MAX_RUNNING_TIME = 60 * 60 * 8  # 8h in seconds

logger = logging.getLogger(__name__)

base_path = os.path.realpath(__file__)
base_path = os.path.dirname(base_path)

my_service_uuid = "0000ffe0-0000-1000-8000-00805f9b34fb"
my_char_uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"
my_char_desc = "00002902-0000-1000-8000-00805f9b34fb"

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
        await client.start_notify(my_char_uuid, notification_callback)
        await asyncio.sleep(NOTIFICATION_WINDOW_SIZE)
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
        logger.info(f"found device {device}")

        nonlocal device_to_connect_to
        if device_has_service(advertising_data, my_service_uuid):
            logger.info(f"with service {my_service_uuid}")
            if devices_discovery_time.get(device) is None:
                devices_discovery_time[device] = time.time()
                logger.debug(
                    f"discovery time: {devices_discovery_time[device]}")

            device_to_connect_to = device
            stop_event.set()  # awakens stop_event.wait()

    async with BleakScanner(scan_callback, service_uuids=[my_service_uuid]) as _:
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
    logging.basicConfig(
        filename=f"{base_path}/logs/main.log", level=logging.DEBUG)

    logger.debug(f"Searched service uuid: {my_service_uuid}")
    logger.debug(f"Searched characteristic uuid: {my_char_uuid}")
    logger.debug(f"With characteristic descriptor uuid: {my_char_desc}")

    # set the notification window size
    if len(argv) > 1:
        if argv[1].isdigit():
            NOTIFICATION_WINDOW_SIZE = int(argv[1])
    logger.info(f"notification window size set to {NOTIFICATION_WINDOW_SIZE}")

    has_max_running_time_elapsed = has_max_running_time_elapsed_builder(
        start_time=time.time(), max_running_time=MAX_RUNNING_TIME)
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
