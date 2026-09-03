from __future__ import annotations

import struct as _struct
import typing
import io

from typing import TYPE_CHECKING, Callable, Any, Optional, Self
from enum import Enum, auto

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer

class Event(Enum):
    CONNECT = auto()
    DISCONNECT = auto()
    PACKET = auto()
    
type _Address = tuple[str, int]
type _Listener = Callable[..., Any]

class Type[T]():
    format: str | bytes

    @classmethod
    def size(cls, data: ReadableBuffer | None = None) -> int:
        return _struct.calcsize(cls.format)

    @classmethod
    def pack(cls, value: T) -> bytes:
        return _struct.pack(cls.format, value)

    @classmethod
    def unpack(cls, data: ReadableBuffer) -> T:
        return _struct.unpack(cls.format, data)[0]

class u8(Type[int]):
    format = "!B"

class u16(Type[int]):
    format = "!H"

class u32(Type[int]):
    format = "!I"

class u64(Type[int]):
    format = "!Q"

class i8(Type[int]):
    format = "!b"

class i16(Type[int]):
    format = "!h"

class i32(Type[int]):
    format = "!i"

class i64(Type[int]):
    format = "!q"

class f32(Type[float]):
    format = "!f"

class f64(Type[float]):
    format = "!d"

class boolean(Type[bool]):
    format = "?"

class char(Type[str]):
    format = "!c"

    @classmethod
    def pack(cls, value: str) -> bytes:
        return _struct.pack(cls.format, value.encode("ascii"))

    @classmethod
    def unpack(cls, data: ReadableBuffer) -> str:
        return _struct.unpack(cls.format, data)[0].decode("ascii")

class string(Type[str]):
    @classmethod
    def size(cls, data: ReadableBuffer) -> int:
        length: int = u16.unpack(data[:u16.size()])
        return u16.size() + length
    
    @classmethod
    def pack(cls, value: str) -> bytes:
        data: bytes = value.encode()
        return u16.pack(len(data)) + data

    @classmethod
    def unpack(cls, data: bytes) -> str:
        length: int = u16.unpack(data[:u16.size()])
        value: bytes = data[u16.size():u16.size() + length]
        return value.decode()

class array(Type[list[Any]]):
    _type: type[Type] | None = None

    def __class_getitem__(cls, _type: type[Type]):
        assert cls._type is None, "array type already specified"
        assert issubclass(_type, Type), f"array type must be a subclass of Type"

        class _array(cls):
            ...

        _array._type = _type

        return _array

    @classmethod
    def size(cls, data: ReadableBuffer) -> int:
        assert cls._type is not None, "array type cannot be None. Use array[type].size(...)"

        length: int = u16.unpack(data[:u16.size()])
        cursor: int = u16.size()

        for _ in range(length):
            cursor += cls._type.size(data[cursor:])

        return cursor
    
    @classmethod
    def pack(cls, items: list[Any]) -> bytes:
        assert cls._type is not None, "array type cannot be None. Use array[type].pack(...)"
        
        array_length: int = len(items)
        array_data: io.BytesIO = io.BytesIO()
        
        for item in items:
            array_data.write(cls._type.pack(item))

        return u16.pack(array_length) + array_data.getvalue()

    @classmethod
    def unpack(cls, data: ReadableBuffer) -> list[Any]:
        assert cls._type is not None, "array type cannot be None. Use array[type].unpack(...)"

        length: int = u16.unpack(data[:u16.size()])
        cursor: int = u16.size()

        items: list[Any] = []

        for _ in range(length):
            size: int = cls._type.size(data[cursor:])
            items.append(cls._type.unpack(data[cursor:cursor + size]))

            cursor += size

        return items

class optional(Type[Optional[Any]]):
    _type: type[Type] | None = None
    
    def __class_getitem__(cls, _type: type[Type]):
        assert cls._type is None, "optional type already specified"
        assert issubclass(_type, Type), f"optional type must be a subclass of Type"

        class _optional(cls):
            ...

        _optional._type = _type

        return _optional

    @classmethod
    def size(cls, data: ReadableBuffer) -> int:
        assert cls._type is not None, "optional type cannot be None. Use optional[type].size(...)"

        present: bool = boolean.unpack(data[:boolean.size()])

        if present:
            return boolean.size() + cls._type.size(data[boolean.size():])
        else:
            return boolean.size()

    @classmethod
    def pack(cls, value: Optional[Any]) -> bytes:
        assert cls._type is not None, "optional type cannot be None. Use optional[type].pack(...)"

        if value is None:
            return boolean.pack(False)
        else:
            return boolean.pack(True) + cls._type.pack(value)

    @classmethod
    def unpack(cls, data: ReadableBuffer) -> Optional[Any]:
        assert cls._type is not None, "optional type cannot be None. Use optional[type].unpack(...)"

        present: bool = boolean.unpack(data[:boolean.size()])
        return cls._type.unpack(data[boolean.size():]) if present else None

class enum(Type[Any]):
    _type: type[Type] | None = None
        
    def __class_getitem__(cls, _type: type[Type]):
        assert cls._type is None, "enum type already specified"
        assert issubclass(_type, Type), f"enum type must be a subclass of Type"

        enum_type: type[Type] = _type

        class _enum(cls):
            _type = enum_type

        return _enum

    def __init_subclass__(cls):
        super().__init_subclass__()
        assert cls._type is not None, "enum type cannot be None. Use enum[type]"

    @classmethod
    def size(cls, data: ReadableBuffer | None = None) -> int:
        return cls._type.size()

    @classmethod
    def pack(cls, value: Any) -> bytes:
        assert cls._type is not None, "enum type cannot be None. Use enum[type]"
        return cls._type.pack(value)

    @classmethod
    def unpack(cls, data: ReadableBuffer) -> Any:
        assert cls._type is not None, "enum type cannot be None. Use enum[type]"
        return cls._type.unpack(data)

class field[T]:
    def __get__(self, instance: Any, owner: type[Any] | None = None) -> T:
        ...

    def __set__(self, instance: Any, owner: type[Any] | None = None) -> None:
        ...

class struct(Type[Any]):
    @classmethod
    def get_fields(cls) -> list[tuple[str, type, type[Type]]]:
        _fields: list[tuple[str, type, type[Type]]] = []

        for name, annotation in typing.get_type_hints(cls).items():
            if typing.get_origin(annotation) is not field:
                continue

            pytype: type = typing.get_args(annotation)[0]
            _type: type[Type] = getattr(cls, name)

            assert issubclass(_type, Type), f"field type must be a subclass of Type"
            
            _fields.append((name, pytype, _type))

        return _fields

    def __init__(self, *args, **kwargs) -> None:
        _fields: list[tuple[str, type, type[Type]]] = self.get_fields()

        assert len(args) <= len(_fields), f"{self.__class__.__name__} expected at most {len(_fields)} argument{'s' if len(_fields) != 1 else ''}, got {len(args)}"

        _seen: set[str] = set()

        for (name, *_), value in zip(_fields, args):
            setattr(self, name, value)
            _seen.add(name)

        for name, value in kwargs.items():
            assert name not in _seen, f"{self.__class__.__name__} got multiple values for argument '{name}'"
            assert any(field == name for field, *_ in _fields), f"{self.__class__.__name__} got an unexpected keyword argument '{name}'"
            setattr(self, name, value)

        for name, *_ in _fields:
            assert hasattr(self, name), f"{self.__class__.__name__} missing required argument '{name}'"

    @classmethod
    def size(cls, data: ReadableBuffer | None = None) -> int:
        cursor: int = 0

        for *_, _type in cls.get_fields():
            cursor += _type.size(data[cursor:] if data is not None else None)

        return cursor

    def pack(self, **_overrides: Any) -> bytes:
        data: io.BytesIO = io.BytesIO()

        for name, _, _type in self.get_fields():
            value: Any = _overrides.get(name, getattr(self, name))
            data.write(_type.pack(value))

        return data.getvalue()

    @classmethod
    def unpack(cls, data: ReadableBuffer | None = None) -> Self:
        kwargs: dict[str, Any] = {}
        cursor: int = 0

        for name, _, _type in cls.get_fields():
            size: int = _type.size(data[cursor:])
            kwargs[name] = _type.unpack(data[cursor:cursor + size])
            cursor += size

        return cls(**kwargs)

__all__ = (
    "Event", "_Address", "_Listener", "u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64", "f32", "f64",
    "boolean", "char", "string", "array", "optional", "enum", "field", "struct"
)