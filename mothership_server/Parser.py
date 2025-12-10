import json
from typing import Any
from lib import (Mission)

class MissionsParserException(Exception):
    pass


class Parser:
    """Generic parser class for missions."""

    @staticmethod
    def __assert_condition(condition: bool) -> None:
        if not condition:
            raise MissionsParserException("JSON of missions doesn't match schema")

    @classmethod
    def __assert_type(cls, value: Any, type_name: type) -> None:
        cls.__assert_condition(isinstance(value, type_name))

    @classmethod
    def __assert_dict(cls, dictionary: Any, keys: dict[str, type]) -> None:
        cls.__assert_type(dictionary, dict)
        cls.__assert_condition(set(dictionary.keys()) == set(keys.keys()))
        for key, typ in keys.items():
            cls.__assert_type(dictionary[key], typ)

    @classmethod
    def _parse_coord(cls, coord_str: str) -> tuple[float, float]:
        coord_str = coord_str.strip("() ")
        parts = coord_str.split(",")
        cls.__assert_condition(len(parts) == 2)
        return (float(parts[0]), float(parts[1]))

    @classmethod
    def parse_missions(cls, file_path: str) -> list[Mission]:
        """Reads a JSON file and converts it into a list of Mission objects."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            cls.__assert_dict(data, {"missions": list})
            missions: list[Mission] = []

            for m in data["missions"]:
                cls.__assert_dict(
                    m,
                    {
                        "mission_id": str,
                        "area": dict,
                        "task": str,
                        "duration": int,
                        "report_time": int,
                    },
                )

                area = m["area"]
                cls.__assert_dict(
                    area,
                    {"coordinates_start": str, "coordinates_end": str},
                )

                coordinates_beg = cls._parse_coord(area["coordinates_start"])
                coordinates_end = cls._parse_coord(area["coordinates_end"])

                mission = Mission(
                    mission_id=m["mission_id"],
                    coordinates_beg=coordinates_beg,
                    coordinates_end=coordinates_end,
                    task=m["task"],
                    duration=m["duration"],
                    report_time=m["report_time"],
                )

                missions.append(mission)

            return missions

        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            raise MissionsParserException("Failed to parse missions JSON.") from e
