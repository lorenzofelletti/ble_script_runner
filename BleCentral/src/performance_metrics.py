from typing import Annotated, List, Optional
from bleak import BLEDevice

devices_discovery_time: Annotated[dict[BLEDevice,
                                       Optional[float]], "time of discovery of each device"] = {}
latencies: Annotated[List[float],
                     "list of connection latencies, i.e. time elapsed from device discovery to connection"] = []
