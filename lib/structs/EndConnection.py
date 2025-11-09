import struct
from typing import Optional

from .Packet import Packet, PacketType 


class EndConnection(Packet):

    def __init__(self, sequence_number: Optional[int] = None, ack_number: Optional[int] = None):
        super().__init__(PacketType.EndConnection,sequence_number, ack_number)


    def serialize(self) -> bytes:

        packet_bytes = super().serialize()

        return packet_bytes 

    @staticmethod
    def deserialize(data: bytes) -> "EndConnection":

        sequence_number = struct.unpack('>I', data[1:5])[0]
        ack_number = struct.unpack('>I', data[5:9])[0]

        return Ack(sequence_number, ack_number)



