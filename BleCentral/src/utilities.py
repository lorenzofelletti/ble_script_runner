import time

from bleak import BLEDevice


def has_max_running_time_elapsed_builder(start_time: float, max_running_time: int) -> callable:
    '''
    Returns a function that checks if the max running time has elapsed
    '''
    def has_max_running_time_elapsed() -> bool:
        return time.time() - start_time > max_running_time
    return has_max_running_time_elapsed


def device_has_service(device: BLEDevice, service_uuid: str) -> bool:
    '''
    Checks if the device advertises the service with the given uuid
    '''
    return service_uuid in device.service_uuids
