#import asyncio
#from bleak import BleakClient

##address = "f8:0f:f9:f1:e8:63"
#address = "a4:50:46:7e:eb:68"
#MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
#
#async def main(address):
#    async with BleakClient(address) as client:
#        model_number = await client.read_gatt_char(MODEL_NBR_UUID)
#        print("Model Number: {0}".format("".join(map(chr, model_number))))
#asyncio.run(main(address.upper()))

#import asyncio
#from typing import Sequence
#
#from bleak import BleakClient, BleakScanner
#from bleak.backends.device import BLEDevice
#
#
#async def find_all_devices_services():
#    scanner = BleakScanner()
#    devices: Sequence[BLEDevice] = await scanner.discover(timeout=5.0)
#    for d in devices:
#        async with BleakClient(d) as client:
#            print(client.services)
#
#
#asyncio.run(find_all_devices_services())

"""
Detection callback w/ scanner
--------------
Example showing what is returned using the callback upon detection functionality
Updated on 2020-10-11 by bernstern <bernie@allthenticate.net>
"""

import asyncio
import logging
import sys

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logger = logging.getLogger(__name__)


def simple_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    #logger.info(f"{device.address}: {advertisement_data}")
    if device.address == "a4:50:46:7e:eb:68" or device.address == "a450467eeb68" or device.address == "A4:50:46:7E:EB:68" or device.address == "A450467EEB68":
        print("Found device")


async def main(service_uuids):
    scanner = BleakScanner(simple_callback, service_uuids)

    while True:
        print("(re)starting scanner")
        await scanner.start()
        await asyncio.sleep(5.0)
        await scanner.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )
    service_uuids = sys.argv[1:]
    asyncio.run(main(service_uuids))