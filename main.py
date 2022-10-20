import asyncio
import logging

from bleak import discover
from bleak import BleakClient

devices_dict = {}
devices_list = []
receive_data = []

#To discover BLE devices nearby 
async def scan():
    devices_dict.clear()
    devices_list.clear()
    
    dev = await discover()
    for i in range(0,len(dev)):
        #Print the devices discovered
        print("[" + str(i) + "]" + dev[i].address,dev[i].name,dev[i].metadata["uuids"])
        #Put devices information into list
        devices_dict[dev[i].address] = []
        devices_dict[dev[i].address].append(dev[i].name)
        devices_dict[dev[i].address].append(dev[i].metadata["uuids"])
        devices_list.append(dev[i].address)

#An easy notify function, just print the recieve data
def notification_handler(sender, data):
    print(', '.join('{:02x}'.format(x) for x in data))

async def run(address, debug=False):
    log = logging.getLogger(__name__)
    if debug:
        import sys

        log.setLevel(logging.DEBUG)
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.DEBUG)
        log.addHandler(h)

    #address = "f8:0f:f9:f1:e8:63"
    async with BleakClient(address) as client:
        x = await client.is_connected()
        log.info("Connected: {0}".format(x))

        for service in client.services:
            log.info("[Service] {0}: {1}".format(service.uuid, service.description))
            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        bytes_value = await client.read_gatt_char(char.handle)
                        value = int.from_bytes(bytes_value, byteorder="big")
                        client.read_gatt_char(char.uuid)
                    except Exception as e:
                        value = str(e).encode()
                else:
                    value = None
                log.info(
                    "\t[Characteristic] {0}: (Handle: {1}) ({2}) | Name: {3}, Value: {4} ".format(
                        char.uuid,
                        char.handle,
                        ",".join(char.properties),
                        char.description,
                        value,
                    )
                )
                #for descriptor in char.descriptors:
                #    value = await client.read_gatt_descriptor(descriptor.handle)
                #    log.info(
                #        "\t\t[Descriptor] {0}: (Handle: {1}) | Value: {2} ".format(
                #            descriptor.uuid, descriptor.handle, bytes(value)
                #        )
                #    )
                
                #Characteristic uuid
                #CHARACTERISTIC_UUID = "put your characteristic uuid"
                #CHARACTERISTIC_UUID = "23782c92-139c-4846-aac5-31d1b078d440"

                #await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
                #await asyncio.sleep(5.0)
                #await client.stop_notify(CHARACTERISTIC_UUID)


def do_scan():
    print("Scanning for peripherals...")

    #Build an event loop
    loop = asyncio.get_event_loop()
    #Run the discover event
    loop.run_until_complete(scan())

    #let user chose the device
    index = input('please select device from 0 to ' + str(len(devices_list)) + ":")
    
    return index

if __name__ == "__main__":
    while True:
        index = do_scan()

        if (index == 'r'):
            continue
        elif (index == 'q'):
            break

        index = int(index)
        address = devices_list[index]
        print("Address is " + address)

        #Run notify event
        loop = asyncio.get_event_loop()
        loop.set_debug(True)
        loop.run_until_complete(run(address, True))