import struct
from enum import Enum
from typing import Optional

from .Packet import Packet, PacketType

class MissionState(Enum):
    NOT_ATTRIBUTED = 0
    ATTIBUTED = 1
    DOING = 2
    FINISHED = 3

class Mission():

    def __init__(self, mission_id: str, 
                 coordinates_beg: tuple[float,float], 
                 coordinates_end: tuple[float,float], 
                 task:str, 
                 duration: int, 
                 report_time: int,
                 state: MissionState = MissionState.NOT_ATTRIBUTED): 

        self._mission_id = mission_id
        self._area = [coordinates_beg, coordinates_end]
        self._task = task
        self._duration = duration
        self._report_time = report_time
        self._state = state
    
    def serialize(self) -> bytes:
        """
        Serialize the mission into bytes:
        mission_id\0 | 4 floats | task\0 | 2 ints | 1 byte (state)
        """
        # Optional parent serialization
        packet_bytes = super().serialize() if hasattr(super(), "serialize") else b""

        mission_id_bytes = self._mission_id.encode('utf-8') + b'\0'

        coordinates_bytes = struct.pack(
            '>4f',
            self._area[0][0], self._area[0][1],
            self._area[1][0], self._area[1][1]
        )

        task_bytes = self._task.encode('utf-8') + b'\0'

        timing_bytes = struct.pack('>II', self._duration, self._report_time)

        state_bytes = struct.pack('>B', self._state.value)  # 1 byte for enum value

        return b''.join([
            packet_bytes,
            mission_id_bytes,
            coordinates_bytes,
            task_bytes,
            timing_bytes,
            state_bytes
        ])

    @classmethod
    def deserialize(cls, data: bytes):
        try:
            offset = 0

            # Mission ID
            mid_end = data.index(b'\0', offset)
            mission_id = data[offset:mid_end].decode('utf-8')
            offset = mid_end + 1

            # Coordinates
            coords = struct.unpack_from('>4f', data, offset)
            coordinates_beg = (coords[0], coords[1])
            coordinates_end = (coords[2], coords[3])
            offset += 16

            # Task
            task_end = data.index(b'\0', offset)
            task = data[offset:task_end].decode('utf-8')
            offset = task_end + 1

            # Duration + Report Time
            duration, report_time = struct.unpack_from('>II', data, offset)
            offset += 8

            # State (1 byte)
            state_value = struct.unpack_from('>B', data, offset)[0]
            offset += 1

            # Convert to Enum safely
            state = MissionState(state_value) if state_value in [s.value for s in MissionState] else MissionState.NOT_ATTRIBUTED

            return cls(
                mission_id,
                coordinates_beg,
                coordinates_end,
                task,
                duration,
                report_time,
                state
            )

        except (ValueError, struct.error, UnicodeDecodeError) as e:
            raise SerializationException('Invalid Mission message') from e

    def __repr__(self) -> str:
        return (
            f"Mission("
            f"mission_id={self._mission_id}, "
            f"area={self._area}, "
            f"task={self._task}, "
            f"duration={self._duration}, "
            f"report_time={self._report_time}, "
            f"state={self._state.name}"
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

    @property
    def state(self) -> MissionState:
        return self._state
