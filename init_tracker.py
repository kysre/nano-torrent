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
    loop.create_task(handle_logs(loop, tracker_server))
    print(f'Started tracker on {addr[0]}:{addr[1]}')
    while True:
        await asyncio.sleep(1000)


async def handle_logs(loop, tracker_server: TrackerUDPServer):
    while True:
        command = await loop.run_in_executor(None, input)
        if command == 'request logs':
            tracker_server.print_logs()
        elif command == 'file logs all':
            tracker_server.print_file_logs()
        elif command.startswith('file logs'):
            file_name = command.split()[2]
            tracker_server.print_file_logs(file_name)
        else:
            print('invalid command')


if __name__ == '__main__':
    tracker_addr_str = sys.argv[1]
    tracker_addr = tracker_addr_str.split(':')[0], int(tracker_addr_str.split(':')[1])

    tracker = TrackerUDPServer(tracker_addr)
    asyncio.run(run_tracker(tracker, tracker_addr))
