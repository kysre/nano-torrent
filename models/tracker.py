from typing import Tuple, Dict, List
from datetime import datetime
from dataclasses import dataclass
from random import randrange
import asyncio

from consts import (
    ENCODING_PROTOCOL,
    SEEDER_TIMEOUT_THRESHOLD,
    FILE_NOT_FOUND_MSG,
    BAD_REQUEST_MSG,
)


@dataclass
class SeederData:
    host: str = '127.0.0.1'
    port: int = None

    def __str__(self):
        return f'{self.host}:{self.port}'

    def __hash__(self):
        return int(''.join(filter(str.isdigit, self.__str__())))

    def get_address(self):
        return self.host, self.port


class TrackerUDPServer:
    def __init__(self, addr: Tuple[str, int]):
        self._lock: asyncio.Lock = asyncio.Lock()
        self._addr: Tuple[str, int] = addr
        self._active_seeders_dict: Dict[SeederData, float] = {}
        self._file_seeders_dict: Dict[str, List[SeederData]] = {}
        self._logs: List[str] = []

    def is_seeder_active(self, seeder_data: SeederData):
        if seeder_data not in self._active_seeders_dict.keys():
            return False
        last_heartbeat_timestamp = self._active_seeders_dict[seeder_data]
        delta = abs(datetime.now().timestamp() - last_heartbeat_timestamp)
        return delta <= SEEDER_TIMEOUT_THRESHOLD

    def get_random_seeder_data(self, file_name):
        seeders = self._file_seeders_dict[file_name]
        random_seeder_data = None
        while len(seeders) > 0:
            random_seeder_data = seeders[randrange(len(seeders))]
            if self.is_seeder_active(random_seeder_data):
                break
            else:
                seeders.remove(random_seeder_data)
                self._active_seeders_dict.pop(random_seeder_data)
                random_seeder_data = None

        return random_seeder_data

    async def handle_active(self, addr):
        seeder_data = SeederData(addr[0], addr[1])
        self._active_seeders_dict[seeder_data] = datetime.now().timestamp()

    async def handle_get(self, addr, file_name):
        encoded_msg = FILE_NOT_FOUND_MSG.encode(ENCODING_PROTOCOL)
        await self._lock.acquire()
        try:
            if file_name in self._file_seeders_dict.keys():
                random_seeder_data = self.get_random_seeder_data(file_name)
                if random_seeder_data:
                    encoded_msg = f'receive_from {str(random_seeder_data)}'.encode(ENCODING_PROTOCOL)
        finally:
            self._lock.release()
        self.transport.sendto(encoded_msg, addr)

    async def handle_seed(self, addr, file_name):
        seeder_data = SeederData(addr[0], addr[1])
        await self._lock.acquire()
        try:
            if file_name not in self._file_seeders_dict.keys():
                self._file_seeders_dict[file_name] = []
            if seeder_data not in self._file_seeders_dict[file_name]:
                self._file_seeders_dict[file_name].append(seeder_data)
                self._active_seeders_dict[seeder_data] = datetime.now().timestamp()
        finally:
            self._lock.release()

    async def handle_bad_request(self, addr):
        encoded_msg = BAD_REQUEST_MSG.encode(ENCODING_PROTOCOL)
        self.transport.sendto(encoded_msg, addr)

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        loop = asyncio.get_event_loop()
        request: str = data.decode(ENCODING_PROTOCOL)
        if request.startswith('active'):
            addr = request.split()[2]
            loop.create_task(self.handle_active(addr))
        elif request.startswith('get'):
            file_name = request.split()[1]
            loop.create_task(self.handle_get(addr, file_name))
        elif request.startswith('seed'):
            file_name = request.split()[1]
            addr = request.split()[2]
            loop.create_task(self.handle_seed(addr, file_name))
        else:
            loop.create_task(self.handle_bad_request(addr))
