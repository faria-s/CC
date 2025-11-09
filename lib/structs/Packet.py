import random
import struct
from enum import Enum
from typing import Optional



class PacketType(Enum):
    RegisterRover = 0
    RegisterRoverResponse = 1
    Mission = 3
    Report = 4
    Ack = 5
    EndConnection = 6

class Packet():
    '''
    Base class for packets with utility methods for checksum calculation and validation.
    '''
    def __init__(self, packet_type: PacketType, sequence_number: Optional[int] = None, ack_number: Optional[int] = None ):
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


    def serialize(self) -> bytes:
        packet_type_bytes = struct.pack('>B', self.__packet_type.value)   # 1 byte for type
        sequence_number_bytes = struct.pack('>I', self.__sequence_number) # 4 bytes, big-endian unsigned int
        ack_number_bytes = struct.pack('>I', self.__ack_number)           # 4 bytes, big-endian unsigned int

        return b''.join([
            packet_type_bytes,
            sequence_number_bytes,
            ack_number_bytes,
        ])


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
