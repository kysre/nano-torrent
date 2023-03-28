import sys
import asyncio
from typing import Tuple

from models.tracker import TrackerUDPServer


async def run_tracker(tracker_server: TrackerUDPServer, addr: Tuple[str, int]):
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: tracker_server,
        local_addr=addr
    )
    print(f'Started tracker on {addr[0]}:{addr[1]}')
    while True:
        await asyncio.sleep(1000)

if __name__ == '__main__':
    tracker_addr_str = sys.argv[1]
    tracker_addr = tracker_addr_str.split(':')[0], int(tracker_addr_str.split(':')[1])

    tracker = TrackerUDPServer(tracker_addr)
    asyncio.run(run_tracker(tracker, tracker_addr))
