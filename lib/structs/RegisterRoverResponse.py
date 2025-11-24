import struct
from typing import Optional

from .Packet import Packet, PacketType 


class RegisterRoverResponse(Packet):

    def __init__(self, sequence_number: Optional[int] = None, ack_number: Optional[int] = None, rover_id: str | None = None):
        super().__init__(PacketType.RegisterRoverResponse,sequence_number, ack_number)
        self.rover_id = rover_id


    def serialize(self) -> bytes:
        packet_bytes = super().serialize()
        rover_id_bytes = self.rover_id.encode("utf-8")
        return packet_bytes + len(rover_id_bytes).to_bytes(1, 'big') + rover_id_bytes

    @staticmethod
    def deserialize(data: bytes) -> "RegisterRoverResponse":

        sequence_number = struct.unpack('>I', data[1:5])[0]
        ack_number = struct.unpack('>I', data[5:9])[0]
        id_len = struct.unpack('>B', data[9:10])[0]

        rover_id = data[10:10 + id_len].decode("utf-8")

        return RegisterRoverResponse(sequence_number, ack_number, rover_id)
