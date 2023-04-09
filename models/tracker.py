from typing import Tuple, Dict, List, Optional
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

    def get_random_seeder_data(self, file_name: str) -> Optional[SeederData]:
        """
        This function handles get file requests in a lazy manner.
        It randomly chooses a SeederData and if it isn't active,
        it chooses another one until no other SeederData exists.
        If a SeederData isn't active then it proceeds to remove
        it from that file seeders. This way the requests are handled
        more efficiently and each file's SeederDatas are updated.
        :param: file_name: file to download
        :return: SeederData to download from. None if not exist
        """
        seeders = self._file_seeders_dict[file_name]
        random_seeder_data = None
        while len(seeders) > 0:
            random_seeder_data = seeders[randrange(len(seeders))]
            if self.is_seeder_active(random_seeder_data):
                break
            else:
                seeders.remove(random_seeder_data)
                self._active_seeders_dict.pop(random_seeder_data)
                print(f'{str(random_seeder_data)} disconnected')
                random_seeder_data = None

        return random_seeder_data

    @staticmethod
    def get_seeder_data(addr: str) -> SeederData:
        host, port = addr.split(':')
        return SeederData(host, port)

    async def handle_active(self, addr: str):
        seeder_data = self.get_seeder_data(addr)
        if seeder_data not in self._active_seeders_dict:
            print(f'{str(seeder_data)} connected')
        self._active_seeders_dict[seeder_data] = datetime.now().timestamp()

    async def handle_get(self, addr, file_name):
        encoded_msg = FILE_NOT_FOUND_MSG.encode(ENCODING_PROTOCOL)
        await self._lock.acquire()
        self.add_log(f'request {addr} get {file_name}')
        try:
            if file_name in self._file_seeders_dict.keys():
                random_seeder_data = self.get_random_seeder_data(file_name)
                if random_seeder_data:
                    encoded_msg = f'receive_from {str(random_seeder_data)}'.encode(ENCODING_PROTOCOL)
                    self.add_log(f'response {addr} download {file_name} from {str(random_seeder_data)}')
        finally:
            self._lock.release()
        self.transport.sendto(encoded_msg, addr)

    async def handle_seed(self, addr, file_name):
        seeder_data = self.get_seeder_data(addr)
        await self._lock.acquire()
        try:
            if file_name not in self._file_seeders_dict.keys():
                self._file_seeders_dict[file_name] = []
            if seeder_data not in self._file_seeders_dict[file_name]:
                self._file_seeders_dict[file_name].append(seeder_data)
                self._active_seeders_dict[seeder_data] = datetime.now().timestamp()
                print(f'{str(seeder_data)} connected')
                self.add_log(f'file_log {addr} started to seed {file_name}')
        finally:
            self._lock.release()

    async def handle_log(self, log_request: str):
        log = log_request.replace('log ', '', 1)
        self._logs.append(log)

    async def handle_bad_request(self, addr):
        encoded_msg = BAD_REQUEST_MSG.encode(ENCODING_PROTOCOL)
        self.transport.sendto(encoded_msg, addr)

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        loop = asyncio.get_event_loop()
        request: str = data.decode(ENCODING_PROTOCOL)
        if request.startswith('active'):
            addr = request.split()[1]
            loop.create_task(self.handle_active(addr))
        elif request.startswith('get'):
            file_name = request.split()[1]
            loop.create_task(self.handle_get(addr, file_name))
        elif request.startswith('seed'):
            file_name = request.split()[1]
            addr = request.split()[2]
            loop.create_task(self.handle_seed(addr, file_name))
        elif request.startswith('log'):
            loop.create_task(self.handle_log(request))
        else:
            loop.create_task(self.handle_bad_request(addr))

    def add_log(self, log: str):
        self._logs.append(log)
        print(log)

    def print_logs(self):
        for log in self._logs:
            if log.startswith('file_log'):
                continue
            else:
                print(log)

    def print_file_logs(self, file_name: Optional[str] = None):
        if file_name:
            if file_name not in self._file_seeders_dict.keys():
                print('file does not exist')
            else:
                for log in self._logs:
                    if file_name in log:
                        print(log)
        else:
            for log in self._logs:
                if log.startswith('file_log'):
                    print(log)
