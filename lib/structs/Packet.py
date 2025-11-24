import random
import struct
from enum import Enum
from typing import Optional


class PacketType(Enum):
    RegisterRover = 0
    RegisterRoverResponse = 1
    Telemetry = 2
    Mission = 3
    Report = 4
    Ack = 5
    EndConnection = 6

class Packet():
    '''
    Base class for packets with utility methods for checksum calculation and validation.
    '''
    def __init__(self, packet_type: PacketType, sequence_number: Optional[int] = None, ack_number: Optional[int] = None, body: Optional[bytes] = None):
        '''
        Initializes a generic packet.

        Args:
            packet_type (PacketType): Type of Packet to be created.
            sequence_number (int, optional): Sequence number of the packet. Defaults to None.
            ack_number (int, optional): Acknowledgment number of the packet. Defaults to None.
        '''
        self.__packet_type = packet_type
        self.__sequence_number = sequence_number or random.randint(0, 2**32 - 1)
        self.__ack_number = ack_number or (self.__sequence_number + 1)
        self.__body = body


    def serialize(self) -> bytes:
        packet_type_bytes = struct.pack('>B', self.__packet_type.value)
        sequence_number_bytes = struct.pack('>I', self.__sequence_number)
        ack_number_bytes = struct.pack('>I', self.__ack_number)

        parts = [packet_type_bytes, sequence_number_bytes, ack_number_bytes]

        if self.__body is not None:
            if not isinstance(self.__body, (bytes, bytearray)):
                raise TypeError("Packet body must be bytes or None")
            parts.append(self.__body)

        return b''.join(parts)

    @classmethod
    def deserialize(cls, data: bytes) -> "Packet":
        """
        Deserialize bytes into a Packet instance.

        Args:
            data (bytes): Serialized packet data.

        Returns:
            Packet: The reconstructed Packet object.
        """
        try:
            if len(data) < 9:
                raise SerializationException("Data too short to be a valid Packet")

            # 1 byte: packet type
            packet_type_value = struct.unpack_from('>B', data, 0)[0]
            try:
                packet_type = PacketType(packet_type_value)
            except ValueError:
                raise SerializationException(f"Invalid packet type: {packet_type_value}")

            # 4 bytes: sequence number
            sequence_number = struct.unpack_from('>I', data, 1)[0]

            # 4 bytes: ack number
            ack_number = struct.unpack_from('>I', data, 5)[0]

            # Remaining bytes: body
            body = data[9:] if len(data) > 9 else None

            return cls(packet_type, sequence_number, ack_number, body)

        except (struct.error, IndexError) as e:
            raise SerializationException("Failed to deserialize Packet") from e


    def __repr__(self) -> str:
        return (
            f"{self.__packet_type}("
            f"sequence_number={self.__sequence_number}, "
            f"ack_number={self.__ack_number}, "
            f")"
        )

    @property
    def sequence_number(self):
        return self.__sequence_number

    @property
    def ack_number(self):
        return self.__ack_number

    @property
    def packet_type(self):
        return self.__packet_type

    @property
    def body(self):
        return self.__body
    