import time
import socket
import threading

from typing import Callable

from .packet import Packet, Heartbeat
from .types_ import Event, _Address, _Listener

class Client():
    def __init__(self, *, timeout: float = 0.1, bufsize: int = 1024, heartbeat_interval: float = 5.0) -> None:
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._address: _Address | None = None

        self._timeout: float = timeout
        self._bufsize: int = bufsize
        self._last_heartbeat_sent: float = time.monotonic()
        self._heartbeat_interval: float = heartbeat_interval
        self._next_seq: int = 0

        self._listeners: dict[Event, list[_Listener]] = {e: [] for e in Event}

        self._listening: bool = False
        self._listen_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

        self._send_lock: threading.Lock = threading.Lock()
        self._heartbeat_event: threading.Event = threading.Event()

    @property
    def address(self) -> _Address | None:
        return self._address

    @property
    def listening(self) -> bool:
        return self._listening

    def connect(self, address: _Address) -> None:
        self._address = address

        self._socket.settimeout(self._timeout)
        self._socket.connect(self.address)

    def send(self, packet: Packet) -> None:
        with self._send_lock:
            seq: int = self._next_seq
            self._next_seq = (self._next_seq + 1) & 0xFFFF

        self.send_bytes(packet.pack(seq = seq))

    def send_bytes(self, data: bytes) -> None:
        self._socket.send(data)

    def _listen(self) -> None:
        while self.listening:
            try:
                data: bytes = self._socket.recv(self._bufsize)
            except socket.timeout:
                continue

            packet: Packet = Packet.unpack(data)

            for listener in self._listeners[Event.PACKET]:
                listener(packet)

    def _heartbeat(self) -> None:
        while self.listening:
            self.send(Heartbeat())
            self._last_heartbeat_sent = time.monotonic()

            if self._heartbeat_event.wait(self._heartbeat_interval):
                break

    def listen(self) -> None:
        self._listening = True
        self._heartbeat_event.clear()

        self._listen_thread = threading.Thread(target = self._listen)
        self._listen_thread.start()

        self._heartbeat_thread = threading.Thread(target = self._heartbeat)
        self._heartbeat_thread.start()

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

__all__ = ("Client", )