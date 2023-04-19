import sys
import asyncio

from models.client import Client

if __name__ == '__main__':
    cmd = sys.argv[1]
    file_name = sys.argv[2]
    tracker_addr_str = sys.argv[3]
    tracker_addr = tracker_addr_str.split(':')[0], int(tracker_addr_str.split(':')[1])
    peer_listen_addr_str = sys.argv[4]
    peer_listen_addr = peer_listen_addr_str.split(':')[0], int(peer_listen_addr_str.split(':')[1])

    client = None
    if cmd == 'share':
        client = Client(peer_listen_addr, tracker_addr, file_name, True)
    elif cmd == 'get':
        client = Client(peer_listen_addr, tracker_addr, file_name, False)
    else:
        sys.exit(-1)

    asyncio.run(client.run_client())
