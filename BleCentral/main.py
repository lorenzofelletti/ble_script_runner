import logging
import os
import argparse
import shlex
import subprocess
import asyncio
from sys import argv
import time
from typing import Callable, List, Optional
from bleak import AdvertisementData, BLEDevice, BleakClient, BleakScanner, BleakError

from config import APP_CONFIG as C
from strings import strings as s


logger = logging.getLogger(__name__)


# variables to meter the connection latency
scanning_start_time: float
devices_discovery_time: dict[BLEDevice, Optional[float]] = {}
discovery_latencies: List[float] = []
connection_latencies: List[float] = []


def device_has_service(advertising_data: AdvertisementData, service_uuid: str) -> bool:
    '''
    Checks if the device advertises the service with the given uuid
    '''
    return service_uuid in advertising_data.service_uuids


async def run_ble_client(device: BLEDevice, queue: asyncio.Queue):
    '''
    Connects to the device and reads the characteristic, then puts the data into the queue
    '''
    disconnection_event = asyncio.Event()  # set by the disconnect callback

    def disconnection_callback(_):
        logger.debug(
            "disconnection callback called. setting disconnection event")
        nonlocal disconnection_event
        disconnection_event.set()

    async def disconnection_handler(client: Optional[BleakClient]):
        '''
        Disconnects from the device and waits for the disconnection event.
        Pass client=None when the client is already disconnected (e.g. after timeout).
        '''
        if client is not None:
            await client.disconnect()
        logger.info(f"Disconnected from {device}")
        print(f"disconnected from {device}")
        await queue.put((time.time(), None, None))

    logger.debug(f"Attempting connection to {device}")
    print(f"Attempting connection to {device}")

    try:
        async with BleakClient(device, disconnected_callback=disconnection_callback) as client:
            async def notification_callback(_, data: bytearray):
                nonlocal client
                logger.debug(f"putting data:'{data}' in queue")
                await queue.put((time.time(), data, client))

            await client.connect()
            logger.info(f"Connected to {device}")
            connection_time = time.time()
            logger.debug(f"connection time: {connection_time}")
            connection_latencies.append(
                connection_time - devices_discovery_time[device])
            logger.debug(f"connection latency: {connection_latencies[-1]}")
            devices_discovery_time.pop(device)

            print(f"Connected to {device}")
            await client.start_notify(C.CHAR_UUID, notification_callback)
            try:
                await asyncio.wait_for(disconnection_event.wait(), C.NOTIFICATION_WINDOW_SIZE)
            except asyncio.TimeoutError:
                logger.info("timeout error. disconnecting")
            except BleakError as e:
                logger.error("bleak error. disconnecting")
                logger.error(e)
                disconnection_event.set()
            finally:
                await disconnection_handler(None if disconnection_event.is_set() else client)
    except Exception as e:
        logger.error(e)
        await disconnection_handler(None)


async def run_queue_consumer(queue: asyncio.Queue):
    '''
    Consumes the queue and invokes the script indicated by the queue data.
    The queue data is a tuple of (timestamp, data, client)
    '''
    def run_script(data: bytearray) -> int:
        '''
        Runs the script indicated by the data. Returns the exit code.
        '''
        data: List[str] = shlex.split(data.decode("utf-8"))
        data[0] = os.path.join(C.SCRIPT_DIR_PATH, data[0])
        logger.info(f"running script {data}")
        try:
            process = subprocess.run(data)
            return process.returncode
        except Exception as e:
            logger.error(e)
            return 255

    while True:
        epoch, data, client = await queue.get()
        logger.info(
            f"received data {data} at epoch {epoch}" if data is not None
            else "received exit message")
        if data is None:
            break
        if client is not None and client.is_connected():
            await client.read_gatt_char(C.CHAR_MONITORING_UUID, )
        res = run_script(data)
        if client is not None and client.is_connected():
            print(f"script exit code: {res}")
            logger.info(f"script exit code: {res}")
            await client.write_gatt_char(C.CHAR_MONITORING_UUID, bytearray(str(res % 256).encode("utf-8")), True)


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
            discovery_latencies.append(
                devices_discovery_time[device] - scanning_start_time)
            logger.debug(f"discovery latency: {discovery_latencies[-1]}")
        device_to_connect_to = device
        stop_event.set()  # awakens stop_event.wait()

    async with BleakScanner(scan_callback, service_uuids=[C.SERVICE_UUID]) as _:
        scanning_start_time = time.time()
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()

    if isinstance(device_to_connect_to, BLEDevice):
        queue = asyncio.Queue()
        client_task = run_ble_client(device_to_connect_to, queue)
        consumer_task = run_queue_consumer(queue)
        await asyncio.gather(client_task, consumer_task)


def has_max_running_time_elapsed_builder(start_time: float, max_running_time: int) -> Callable[[], bool]:
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
    parser.add_argument("--follow-log", "-f",
                        action="store_true", help=s.follow_log_help)

    args = parser.parse_args(argv[1:])

    # Configuration setup
    C.LOG_LEVEL = args.log_level
    C.LOG_FILE = args.log_file
    C.NOTIFICATION_WINDOW_SIZE = args.notification_window_size
    C.MAX_RUNNING_TIME = args.max_running_time

    logging.basicConfig(filename=C.LOG_FILE, level=C.LOG_LEVEL)

    logger.info(f"--- STARTING: {s.app_name} ---")
    logger.info(f"Searched service uuid: {C.SERVICE_UUID}")
    logger.info(f"Searched characteristic uuid: {C.CHAR_UUID}")
    logger.info(f"With characteristic descriptor uuid: {C.CHAR_DESC_UUID}")
    logger.info(
        f"Notification window size set to {C.NOTIFICATION_WINDOW_SIZE}")

    # Run the app
    try:
        if args.follow_log:  # Follows the log file if requested
            log_follow_process = subprocess.Popen(["tail", "-f", C.LOG_FILE])

        has_max_running_time_elapsed = has_max_running_time_elapsed_builder(
            start_time=time.time(), max_running_time=C.MAX_RUNNING_TIME)
        while not has_max_running_time_elapsed():
            logger.info(f"starting app")
            asyncio.run(app())
            logger.info(f"app finished")
    except KeyboardInterrupt:
        logger.info(f"KeyboardInterrupt")
    except Exception as e:
        logger.error(e)
        tasks = asyncio.all_tasks()
        for task in tasks:
            task.cancel()
    finally:
        if args.follow_log:
            log_follow_process.kill()
        if has_max_running_time_elapsed():
            logger.info(f"max running time elapsed")
        if len(discovery_latencies) > 0:
            mean_discovery_latency = sum(
                discovery_latencies) / len(discovery_latencies)
            logger.debug(f"mean discovery latency: {mean_discovery_latency}")
            print(f"mean discovery latency: {mean_discovery_latency}")
        if len(connection_latencies) > 0:
            mean_connection_latency = sum(
                connection_latencies) / len(connection_latencies)
            logger.debug(f"mean connection latency: {mean_connection_latency}")
            print(f"mean connection latency: {mean_connection_latency}")
        logger.info(f"--- FINISHED: {s.app_name} ---")
