import struct
from enum import Enum
from typing import Optional

from .Packet import Packet, PacketType




class Mission(Packet):

    def __init__(self, mission_id: str, 
                 coordinates_beg: tuple[float,float], 
                 coordinates_end: tuple[float,float], 
                 task:str, 
                 duration: int, 
                 report_time: int, 
                 sequence_number: Optional[int] = 0,
                 ack_number: Optional[int] = 0):

        super().__init__(sequence_number,ack_number)
        self._mission_id = mission_id
        self._area = [coordinates_beg, coordinates_end],
        self._task = task
        self._duration = duration
        self._report_time = report_time
    
    def _message_serialize(self) -> bytes:

        packet_bytes = super().serialize()

        mission_id_bytes = self.mission_id.encode('utf-8') + b'\0'

        coordinates_bytes = struct.pack('>4f', 
            self.area[0][0], self.area[0][1],
            self.area[1][0], self.area[1][1]
        )

        task_bytes = self.task.encode('utf-8') + b'\0'

        timing_bytes = struct.pack('>II', self.duration, self.report_time)

        # Combine all pieces in an empty byte sequence (b'')
        return b''.join([
            packet_bytes,
            mission_id_bytes,
            coordinates_bytes,
            task_bytes,
            timing_bytes
        ])

    @classmethod
    def deserialize(cls, data: bytes):
        try:
            sequence_number = struct.unpack_from('>I', data, 0)[0]
            ack_number = struct.unpack_from('>I', data, 4)[0]
            offset = 8  # after sequence+ack

            mid_end = data.index(b'\0', offset)
            mission_id = data[offset:mid_end].decode('utf-8')
            offset = mid_end + 1

            coords = struct.unpack_from('>4f', data, offset)
            coordinates_beg = (coords[0], coords[1])
            coordinates_end = (coords[2], coords[3])
            offset += 16

            task_end = data.index(b'\0', offset)
            task = data[offset:task_end].decode('utf-8')
            offset = task_end + 1

            duration, report_time = struct.unpack_from('>II', data, offset)
            offset += 8

            return cls(
                mission_id, coordinates_beg, coordinates_end,
                task, duration, report_time,
                sequence_number, ack_number
            )

        except (ValueError, struct.error, UnicodeDecodeError) as e:
            raise SerializationException('Invalid Mission message') from e
    

    def __repr__(self) -> str:
        return (
            f"Mission("
            f"sequence_number={self.sequence_number}, "
            f"ack_number={self.ack_number}, "
            f"mission_id={self.mission_id}, "
            f"area={self.area}, "
            f"task={self.task}, "
            f"duration={self.duration}, "
            f"report_time={self.report_time}"
            f")"
        )


# - - - - - - - - - - - GETTERS - - - - - - - - - - - -
    @property
    def mission_id(self) -> str:
        return self._mission_id

    @property
    def area(self) -> list[tuple[float, float]]:
        return self._area

    @property
    def task(self) -> str:
        return self._task

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def report_time(self) -> int:
        return self._report_time

    # @property
    # def state(self) -> MissionState:
    #     return self._state
