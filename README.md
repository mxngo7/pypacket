# pypacket
Type-orientated serialisation and networking library

### Example

```py
from pypacket import Packet, field, struct, string, f64, u16, boolean

class Vector2(struct):
    # fields of type float, which are serialised as float64s
    x: field[float] = f64
    y: field[float] = f64

class PlayerUpdatePacket(Packet):
    # field of type str, serialised as a string
    name: field[str] = string
    # field of type Vector2, which is serialised as a Vector2 struct
    # (and will be deserialised back into a Vector2 object)
    position: field[Vector2] = Vector2
    # field of type int, serialised as an unsigned 16-bit integer
    health: field[int] = u16
    # field of type boolean, you get the point
    is_alive: field[bool] = boolean

packet = PlayerUpdatePacket(
    "Bob",
    Vector2(3.5, 9.2),
    75,
    True
)

data: bytes = packet.pack()
print(data) 
# Outputs:
# b'\x01\x00\x00\x00\x00\x00\x00\x01\xa0g\xcb\xe0\xb7\x00\x03Bob@\x0c\x00\x00\x00\x00\x00\x00@"ffffff\x00K\x01'

packet: PlayerUpdatePacket = PlayerUpdatePacket.unpack(data)
print(packet.__dict__)
# Outputs:
# {'header': <pypacket.packet.Header object at 0x000001C0BF2DD0F0>, 'name': 'Bob',
# 'position': <__main__.Vector2 object at 0x000001C0BF2C5A90>, 'health': 75, 'is_alive': True}
```