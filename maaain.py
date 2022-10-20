import asyncio
import logging

from bleak import discover
from bleak import BleakClient

devices_dict = {}
devices_list = []
receive_data = []

async def scan():
    """ Scan for BLE devices. """

    devices_dict.clear()
    devices_list.clear()
    
    dev = await discover()
    for i in range(0,len(dev)):
        # Print the devices discovered
        print("[" + str(i) + "]" + dev[i].address,dev[i].name,dev[i].metadata["uuids"])
        # Put devices information into list
        devices_dict[dev[i].address] = []
        devices_dict[dev[i].address].append(dev[i].name)
        devices_dict[dev[i].address].append(dev[i].metadata["uuids"])
        devices_list.append(dev[i].address)

# An easy notify function, just print the received data
def notification_handler(_, data: bytearray):
    print(', '.join('{:02x}'.format(x) for x in data))

async def run(address, debug=False):
    log = logging.getLogger(__name__)
    if debug:
        import sys

        log.setLevel(logging.DEBUG)
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.DEBUG)
        log.addHandler(h)

    async with BleakClient(address) as client:
        x = await client.is_connected()
        log.info("Connected: {0}".format(x))

        CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
        characteristic = None
        for service in client.services:
            for char in service.characteristics:
                print(f"Characteristic: {char.uuid} ({char.description})")
                if char.uuid == CHARACTERISTIC_UUID:
                    characteristic = char
                    break

        char_value = await client.read_gatt_char(characteristic)
        print(f"Value: {char_value}")

def do_scan() -> str:
    """
    Set up the event loop and run the scan.
    After scan is done, asks user to select a device to connect and return its choice.
    """

    print("Scanning for peripherals...")

    # Build an event loop
    loop = asyncio.get_event_loop()
    # Run the discover event
    loop.run_until_complete(scan())

    # let user chose the device
    index = input('please select device from 0 to ' + str(len(devices_list)) + ":")
    
    return index

if __name__ == "__main__":
    while True:
        index = do_scan()

        if (index == 'r'):
            # retry scan
            continue
        elif (index == 'q'):
            # quit scan
            break

        index = int(index)
        address = devices_list[index]
        print("Address is " + address)

        #Run notify event
        loop = asyncio.get_event_loop()
        loop.set_debug(True)
        loop.run_until_complete(run(address, True))