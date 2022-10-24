import logging
import os
from re import I
import subprocess
import asyncio
from sys import argv
import time
from typing import List, Optional
from bleak import AdvertisementData, BLEDevice, BleakClient, BleakScanner

# Time the notification of the ble characteristic is active
NOTIFICATION_WINDOW_SIZE = 10  # seconds

logger = logging.getLogger(__name__)

base_path = os.path.realpath(__file__)
base_path = os.path.dirname(base_path)

my_service_uuid = "0000ffe0-0000-1000-8000-00805f9b34fb"
my_char_uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"
my_char_desc = "00002902-0000-1000-8000-00805f9b34fb"


async def run_ble_client(device: BLEDevice, queue: asyncio.Queue):
    async def callback(_, data: bytearray):
        await queue.put((time.time(), data))

    logger.debug(f"called {run_ble_client.__name__}")
    logger.debug(f"device trying to connect to {device}")

    async with BleakClient(device) as client:
        await client.start_notify(my_char_uuid, callback)
        await asyncio.sleep(NOTIFICATION_WINDOW_SIZE)
        await client.stop_notify(my_char_uuid)
        # send an "exit" message to the queue
        await client.disconnect()
        await queue.put((time.time(), None))


async def run_queue_consumer(queue: asyncio.Queue):
    logger.debug(f"called {run_queue_consumer.__name__}")

    def run_script(data: bytearray):
        data: List[str] = data.decode("utf-8").split()
        data[0] = './scripts/' + data[0]
        logger.info(f"running script {data}")
        try:
            subprocess.run(data)
        except Exception as e:
            logger.error(e)

    while True:
        epoch, data = await queue.get()
        if data is None:
            logger.info("received exit message")
            break
        logger.info(f"received data {data} at epoch {epoch}")
        run_script(data)


async def app():
    logger.info(f"scanning for devices")

    device_to_connect_to: Optional[BLEDevice] = None
    stop_event = asyncio.Event()

    def callback(device: BLEDevice, advertising_data: AdvertisementData):
        logger.info("found device {0}".format(device))

        nonlocal device_to_connect_to

        if my_service_uuid in advertising_data.service_uuids:
            logger.info(f"found device with service {my_service_uuid}")
            device_to_connect_to = device
            stop_event.set()  # awakens stop_event.wait()

    async with BleakScanner(callback, service_uuids=[my_service_uuid]) as _:
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()

    if isinstance(device_to_connect_to, BLEDevice):
        queue = asyncio.Queue()
        client_task = run_ble_client(device_to_connect_to, queue)
        consumer_task = run_queue_consumer(queue)
        await asyncio.gather(client_task, consumer_task)
    logger.info("done")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # set the notification window size
    if len(argv) > 1:
        if argv[1].isdigit():
            NOTIFICATION_WINDOW_SIZE = int(argv[1])
    logger.info(f"notification window size set to {NOTIFICATION_WINDOW_SIZE}")

    asyncio.run(app())
