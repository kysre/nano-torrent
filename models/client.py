import asyncio
import socket
import sys
from typing import Tuple, List
import asyncudp

from consts import (
    ENCODING_PROTOCOL,
    MAX_CLIENT_RETRY_COUNT,
    BUFFER_SIZE,
    BAD_REQUEST_MSG,
    FILE_NOT_FOUND_MSG,
)


class Client:
    def __init__(self,
                 addr: Tuple[str, int],
                 tracker_addr: Tuple[str, int],
                 file_name: str,
                 is_seeder: bool):

        self._addr: Tuple[str, int] = addr
        self._tracker_addr: Tuple[str, int] = tracker_addr
        self._file_to_seed: str = file_name
        if is_seeder:
            with open(f'db/{file_name}', 'rb') as f:
                self._file_content = f.read()
        else:
            self._file_content = None
        self._logs: List[str] = []

    async def get_response_from_tracker(self, request: str) -> str:
        sock = await asyncudp.create_socket(remote_addr=self._tracker_addr)
        sock.sendto(request.encode(ENCODING_PROTOCOL))
        encoded_resp, _ = await sock.recvfrom()
        sock.close()
        return encoded_resp.decode(ENCODING_PROTOCOL)

    async def get_seeder_from_tracker(self, file_name):
        for _ in range(MAX_CLIENT_RETRY_COUNT):
            resp = await self.get_response_from_tracker(f'get {file_name}')
            self._logs.append(f'{file_name} {resp}')
            if resp.startswith('receive_from'):
                seeder_addr_str = resp.split()[1]
                return seeder_addr_str.split(':')[0], int(seeder_addr_str.split(':')[1])
            await asyncio.sleep(1)
        return None

    async def get_file(self):
        seeder_addr = await self.get_seeder_from_tracker(self._file_to_seed)
        if not seeder_addr:
            await self.send_download_log_to_tracker('failed to get seeder address')
            sys.exit(-2)
        try:
            sock = socket.socket()
            sock.connect(seeder_addr)
            sock.send(f'get {self._file_to_seed}'.encode(ENCODING_PROTOCOL))
            self._file_to_seed = self._file_to_seed
            data = b''
            while True:
                chunk = sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
            self._file_content = data
            if not FILE_NOT_FOUND_MSG.encode(ENCODING_PROTOCOL) == self._file_content:
                with open(f'db/{self._addr[0]}_{self._addr[1]}_{self._file_to_seed}', 'wb') as f:
                    f.write(self._file_content)
            sock.close()
            await self.send_download_log_to_tracker(f'received {self._file_to_seed} from {seeder_addr}')
        except ConnectionRefusedError:
            await self.send_download_log_to_tracker(f'failed to connect to seeder {seeder_addr}')
        except TimeoutError:
            await self.send_download_log_to_tracker(f'timeout to receive {self._file_to_seed} from {seeder_addr}')
        except Exception as e:
            await self.send_download_log_to_tracker(f'exception {e}')

    async def send_download_log_to_tracker(self, msg: str):
        sock = await asyncudp.create_socket(remote_addr=self._tracker_addr)
        request = f'log result {self._addr[0]}:{self._addr[1]} {msg}'
        sock.sendto(request.encode(ENCODING_PROTOCOL))
        sock.close()

    async def send_seed_to_tracker(self):
        sock = await asyncudp.create_socket(remote_addr=self._tracker_addr)
        request = f'seed {self._file_to_seed} {self._addr[0]}:{self._addr[1]}'
        sock.sendto(request.encode(ENCODING_PROTOCOL))
        sock.close()

    async def send_active_to_tracker(self):
        sock = await asyncudp.create_socket(remote_addr=self._tracker_addr)
        request = f'active {self._addr[0]}:{self._addr[1]}'
        encoded_request = request.encode(ENCODING_PROTOCOL)
        while True:
            sock.sendto(encoded_request)
            await asyncio.sleep(0.5)

    async def handle_request(self, client):
        loop = asyncio.get_event_loop()
        encoded_request = await loop.sock_recv(client, BUFFER_SIZE)
        request = encoded_request.decode(ENCODING_PROTOCOL)
        response = BAD_REQUEST_MSG
        if request.startswith('get'):
            file_name = request.split()[1]
            if file_name == self._file_to_seed:
                response = self._file_content
            else:
                response = FILE_NOT_FOUND_MSG.encode(ENCODING_PROTOCOL)
        await loop.sock_sendall(client, response)
        client.close()

    async def start_seeding(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(self._addr)
        server.listen()
        server.setblocking(False)
        loop = asyncio.get_event_loop()
        await self.send_seed_to_tracker()
        loop.create_task(self.send_active_to_tracker())
        while True:
            client, _ = await loop.sock_accept(server)
            loop.create_task(self.handle_request(client))

    async def run_client(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.handle_logs(loop))
        if not self._file_content:
            await self.get_file()
        await self.start_seeding()

    async def handle_logs(self, loop):
        while True:
            command = await loop.run_in_executor(None, input)
            if command == 'request logs':
                self.print_logs()
            else:
                print('invalid command')

    def print_logs(self):
        for log in self._logs:
            print(log)
