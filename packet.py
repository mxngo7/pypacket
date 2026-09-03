from __future__ import annotations

import time

from typing import TYPE_CHECKING

from .types_ import u8, u16, u64, struct, field

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer

class Header(struct):
    id: field[int] = u8
    seq: field[int] = u16
    ack: field[int] = u16
    timestamp: field[int] = u64

class Packet(struct):
    _next_id: int = 0
    _registry: dict[int, type[Packet]] = {}

    header: field[Header] = Header

    def __init_subclass__(cls):
        super().__init_subclass__()

        cls._packet_id = Packet._next_id
        Packet._registry[Packet._next_id] = cls
        Packet._next_id += 1

    def __init__(self, *args, **kwargs) -> None:
        header: Header = Header(self._packet_id, 0, 0, 0)

        if kwargs.get("header") is None:
            super().__init__(header, *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    @staticmethod
    def get_header(data: ReadableBuffer) -> Header:
        return Header.unpack(data)

    def pack(self, *, seq: int = 0, ack: int = 0) -> bytes:
        header: Header = Header(
            self._packet_id,
            seq,
            ack,
            int(time.time_ns() / 1e6)
        )

        return super().pack(header = header)

    @classmethod
    def _unpack(cls, data: ReadableBuffer) -> Packet:
        return super().unpack(data)
    
    @classmethod
    def unpack(cls, data: ReadableBuffer) -> Packet:
        header: Header = Packet.get_header(data)
        assert header.id in Packet._registry, "packet id not found"
        return Packet._registry[header.id]._unpack(data)

class Heartbeat(Packet):
    ...

__all__ = ("Packet", "Header", "Heartbeat")