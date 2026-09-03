import time
import socket
import threading

from typing import Callable, Collection

from .packet import Packet
from .types_ import _Address, _Listener, Event

class Connection():
    def __init__(self, server: Server, address: _Address):
        self._server: Server = server
        self._address: _Address = address
        self._last_heartbeat: float = time.monotonic()
        self._next_seq: int = 0

    @property
    def address(self) -> _Address:
        return self._address

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    def _heartbeat(self) -> None:
        self._last_heartbeat = time.monotonic()

    def send(self, packet: Packet) -> None:
        self._server.send(packet, self._next_seq, self.address)
        self._next_seq = (self._next_seq + 1) & 0xFFFF

    def send_bytes(self, data: bytes) -> None:
        self._server.send_bytes(data, self.address)

class Server():
    def __init__(self, *, timeout: float = 0.1, bufsize: int = 1024, heartbeat_timeout: float = 15.0) -> None:
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._address: _Address | None = None

        self._timeout: float = timeout
        self._bufsize: int = bufsize
        self._heartbeat_timeout: float = heartbeat_timeout
        
        self._connections: dict[_Address, Connection] = {}
        self._listeners: dict[Event, list[_Listener]] = {e: [] for e in Event}
        self._listening: bool = False

        self._listen_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

        self._heartbeat_event: threading.Event = threading.Event()

    @property
    def address(self) -> _Address | None:
        return self._address

    @property
    def heartbeat_timeout(self) -> float:
        return self._heartbeat_timeout

    @property
    def connections(self) -> Collection[Connection]:
        return self._connections.values()

    @property
    def listening(self) -> bool:
        return self._listening

    def _listen(self) -> None:
        while self.listening:
            try:
                data: tuple[bytes, _Address] = self._socket.recvfrom(self._bufsize)
            except socket.timeout:
                continue

            packet_bytes, address = data
            connection: Connection | None = self._connections.get(address)

            if connection is None:
                connection = Connection(self, address)
                self._connections[address] = connection
                
                for listener in self._listeners[Event.CONNECT]:
                    listener(connection)

            packet: Packet = Packet.unpack(packet_bytes)
            connection._heartbeat()

            for listener in self._listeners[Event.PACKET]:
                listener(packet, connection)

    def _heartbeat(self) -> None:
        while self._listening:
            for address, connection in list(self._connections.items()):
                if time.monotonic() - connection.last_heartbeat >= self.heartbeat_timeout:
                    del self._connections[address]

                    for listener in self._listeners[Event.DISCONNECT]:
                        listener(connection)

            if self._heartbeat_event.wait(1.0):
                break

    def bind(self, address: _Address) -> None:
        self._address = address

        self._socket.settimeout(self._timeout)
        self._socket.bind((self.address))

        self._listening = True
        self._heartbeat_event.clear()

        self._listen_thread = threading.Thread(target = self._listen)
        self._listen_thread.start()

        self._heartbeat_thread = threading.Thread(target = self._heartbeat)
        self._heartbeat_thread.start()

    def send(self, packet: Packet, seq: int, address: _Address) -> None:
        self.send_bytes(packet.pack(seq = seq), address)

    def send_bytes(self, data: bytes, address: _Address) -> None:
        self._socket.sendto(data, address)

    def stop(self) -> None:
        self._listening = False
        self._heartbeat_event.set()

        if self._listen_thread is not None:
            self._listen_thread.join()
            self._listen_thread = None

        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join()
            self._heartbeat_thread = None

    def on(self, event: Event) -> Callable[[_Listener], _Listener]:
        def wrapper(listener: _Listener) -> _Listener:
            self._listeners[event].append(listener)
            return listener

        return wrapper

__all__ = ("Connection", "Server")