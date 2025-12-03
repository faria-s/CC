import struct
from enum import Enum
from typing import Optional

class OperationalStatus(Enum):
    NOT_ATTRIBUTED = 0
    ATTRIBUTED = 1
    DOING = 2
    FINISHED = 3

class Telemetry():

    def __init__(self, rover_id: str, 
                 position: tuple[float, float, float],
                 battery_level: float,
                 velocity: float,
                 operational_status: OperationalStatus = OperationalStatus.NOT_ATTRIBUTED):
        
        self._rover_id = rover_id
        self._position = position  # (x, y, z)
        self._battery_level = battery_level  # percentage
        self._velocity = velocity  # m/s
        self._operational_status = operational_status
    
    def serialize(self) -> bytes:
        """
        Serialize the telemetry into bytes:
        rover_id\0 | 3 floats (position) | 1 float (battery level) | 1 float (velocity) | 1 byte (operational status)
        """

        rover_id_bytes = self._rover_id.encode('utf-8') + b'\0'

        position_bytes = struct.pack(
            '>3f',
            self._position[0], self._position[1], self._position[2]
        )

        battery_bytes = struct.pack('>f', self._battery_level)

        velocity_bytes = struct.pack('>f', self._velocity)

        status_bytes = struct.pack('>B', self._operational_status.value)  # 1 byte for enum value

        return b''.join([
            rover_id_bytes,
            position_bytes,
            battery_bytes,
            velocity_bytes,
            status_bytes
        ])

    @classmethod
    def deserialize(cls, data: bytes):
        """
        Deserialize bytes into a Telemetry object.
        """
        try:
            offset = 0

            # Rover ID
            rid_end = data.index(b'\0', offset)
            rover_id = data[offset:rid_end].decode('utf-8')
            offset = rid_end + 1

            # Position (3 floats)
            pos = struct.unpack_from('>3f', data, offset)
            position = (pos[0], pos[1], pos[2])
            offset += 12

            # Battery level (1 float)
            battery_level = struct.unpack_from('>f', data, offset)[0]
            offset += 4

            # Velocity (1 float)
            velocity = struct.unpack_from('>f', data, offset)[0]
            offset += 4

            # Operational status (1 byte)
            status_value = struct.unpack_from('>B', data, offset)[0]
            offset += 1

            # Convert to Enum safely
            operational_status = OperationalStatus(status_value) if status_value in [s.value for s in OperationalStatus] else OperationalStatus.NOT_ATTRIBUTED

            return cls(
                rover_id,
                position,
                battery_level,
                velocity,
                operational_status
            )

        except (ValueError, struct.error, UnicodeDecodeError) as e:
            raise SerializationException('Invalid Telemetry message') from e

    def __repr__(self) -> str:
        return (
            f"Telemetry("
            f"rover_id={self._rover_id}, "
            f"position={self._position}, "
            f"battery_level={self._battery_level}, "
            f"velocity={self._velocity}, "
            f"operational_status={self._operational_status.name}"
            f")"
        )
    
    @property
    def get_rover_id(self) -> str:
        return self._rover_id
    
    @property
    def get_position(self) -> tuple[float, float, float]:
        return self._position   
    
    @property
    def get_battery_level(self) -> float:
        return self._battery_level  
    
    @property
    def get_velocity(self) -> float:
        return self._velocity   
    
    @property
    def get_operational_status(self) -> OperationalStatus:
        return self._operational_status

    def set_position(self, position: tuple[float, float, float]):
            self._position = position

    def set_battery_level(self, battery_level: float):
        self._battery_level = battery_level

    def set_velocity(self, velocity: float):
        self._velocity = velocity
        
    def set_operational_status(self, status: OperationalStatus):
        self._operational_status = status