import struct
from enum import Enum
from typing import Optional


class OperationalStatus(Enum):
    NOT_ATTRIBUTED = 0
    ATTRIBUTED = 1
    DOING = 2
    FINISHED = 3
    CHARGING = 4   

class Telemetry:
    def __init__(
        self,
        rover_id: str,
        position: tuple[float, float, float],
        battery_level: float,
        velocity: float,
        mission_id: Optional[str] = None,
        operational_status: OperationalStatus = OperationalStatus.NOT_ATTRIBUTED,
    ):
        self._rover_id = rover_id
        self._mission_id = mission_id
        self._position = (
            round(position[0], 2),
            round(position[1], 2),
            round(position[2], 2),
        )
        self._battery_level = round(battery_level, 2)
        self._velocity = round(velocity, 2)
        self._operational_status = operational_status

    def serialize(self) -> bytes:
        rover_id_bytes = self._rover_id.encode("utf-8") + b"\0"
        mission_id_bytes = (
            self._mission_id.encode("utf-8") + b"\0" if self._mission_id else b"\0"
        )

        position_bytes = struct.pack(">3f", *self._position)
        battery_bytes = struct.pack(">f", self._battery_level)
        velocity_bytes = struct.pack(">f", self._velocity)
        status_bytes = struct.pack(">B", self._operational_status.value)

        return b"".join(
            [
                rover_id_bytes,
                mission_id_bytes,
                position_bytes,
                battery_bytes,
                velocity_bytes,
                status_bytes,
            ]
        )

    @classmethod
    def deserialize(cls, data: bytes):
        try:
            offset = 0
            # Rover ID
            rid_end = data.index(b"\0", offset)
            rover_id = data[offset:rid_end].decode("utf-8")
            offset = rid_end + 1

            # Mission ID
            mid_end = data.index(b"\0", offset)
            mission_id_raw = data[offset:mid_end].decode("utf-8")
            mission_id = mission_id_raw if mission_id_raw else None
            offset = mid_end + 1

            # Position
            position = struct.unpack_from(">3f", data, offset)
            offset += 12

            # Battery
            battery_level = struct.unpack_from(">f", data, offset)[0]
            offset += 4

            # Velocity
            velocity = struct.unpack_from(">f", data, offset)[0]
            offset += 4

            # Status
            status_value = struct.unpack_from(">B", data, offset)[0]
            operational_status = OperationalStatus(status_value)

            return cls(
                rover_id=rover_id,
                position=position,
                battery_level=battery_level,
                velocity=velocity,
                operational_status=operational_status,
                mission_id=mission_id,
            )

        except Exception as e:
            raise ValueError(f"Failed to deserialize telemetry: {e}") from e

    def __repr__(self) -> str:
        return (
            f"Telemetry("
            f"rover_id={self._rover_id}, "
            f"mission_id={self._mission_id}, "
            f"position={self._position}, "
            f"battery_level={self._battery_level}, "
            f"velocity={self._velocity}, "
            f"operational_status={self._operational_status.name}"
            f")"
        )

    # ────────────── Properties ──────────────

    @property
    def rover_id(self) -> str:
        return self._rover_id

    @property
    def mission_id(self) -> Optional[str]:
        return self._mission_id

    @property
    def position(self) -> tuple[float, float, float]:
        return self._position

    @property
    def battery_level(self) -> float:
        return self._battery_level

    @property
    def velocity(self) -> float:
        return self._velocity

    @property
    def operational_status(self) -> OperationalStatus:
        return self._operational_status
