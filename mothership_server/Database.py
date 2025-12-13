import json
import sqlite3
from typing import Optional

from lib.logging import log


class DatabaseException(Exception):
    pass


class Database:
    """
    Initializes the database by creating the necessary tables if they do not exist.

    Tables:
    - missions: Stores missions to be sent to the rovers
    - telemetry: Stores telemetry data sent by the rovers
    """

    def __init__(self, path: str):
        try:
            self.__connection = sqlite3.connect(path, check_same_thread=False)
            cursor = self.__connection.cursor()

            # Missions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT NOT NULL,
                    area TEXT NOT NULL,
                    task TEXT NOT NULL,
                    duration REAL,
                    report_time REAL,
                    state INTEGER NOT NULL
                )
            """)

            # Telemetry table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    rover_id TEXT NOT NULL,
                    position TEXT NOT NULL,
                    battery_level REAL NOT NULL,
                    velocity REAL NOT NULL,
                    mission_id TEXT,
                    operational_status INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.__connection.commit()
            log("Database started successfully (missions + telemetry tables ready).")

        except sqlite3.Error as e:
            raise DatabaseException("Failed to initialize database") from e

    # ------------------------------------------------------------------
    # MISSIONS
    # ------------------------------------------------------------------

    def insert_mission(
        self,
        mission_id: str,
        area: list[tuple[float, float]],
        task: str,
        duration: int,
        report_time: int,
        state: int,
    ) -> None:
        try:
            cursor = self.__connection.cursor()
            area_json = json.dumps(area)

            cursor.execute(
                """
                INSERT INTO missions (mission_id, area, task, duration, report_time, state)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mission_id, area_json, task, duration, report_time, state),
            )

            self.__connection.commit()

        except sqlite3.Error as e:
            raise DatabaseException("Failed to insert mission") from e

    def fetch_all_missions(self) -> list[tuple]:
        try:
            cursor = self.__connection.cursor()
            cursor.execute(
                """
                SELECT mission_id, area, task, duration, report_time, state
                FROM missions
                """
            )

            rows = cursor.fetchall()
            missions = []

            for mission_id, area_json, task, duration, report_time, state in rows:
                area = json.loads(area_json)
                missions.append((mission_id, area, task, duration, report_time, state))

            return missions

        except sqlite3.Error as e:
            raise DatabaseException("Failed to fetch missions") from e

    # ------------------------------------------------------------------
    # TELEMETRY
    # ------------------------------------------------------------------

    def insert_telemetry(
        self,
        rover_id: str,
        position: tuple[float, float, float],
        battery_level: float,
        velocity: float,
        operational_status: int,
        mission_id: Optional[str] = None,
    ) -> None:
        """
        Inserts telemetry data into the telemetry table.
        mission_id is optional.
        """
        try:
            cursor = self.__connection.cursor()
            position_json = json.dumps(position)

            cursor.execute(
                """
                INSERT INTO telemetry (
                    rover_id,
                    position,
                    battery_level,
                    velocity,
                    mission_id,
                    operational_status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rover_id,
                    position_json,
                    battery_level,
                    velocity,
                    mission_id,  # can be None
                    operational_status,
                ),
            )

            self.__connection.commit()

        except sqlite3.Error as e:
            log(f"[DB ERROR] Failed to insert telemetry: {e}")
            raise DatabaseException("Failed to insert telemetry") from e

    def fetch_latest_telemetry(self, rover_id: str) -> Optional[tuple]:
        try:
            cursor = self.__connection.cursor()
            cursor.execute(
                """
                SELECT rover_id, position, battery_level, velocity, mission_id, operational_status, timestamp
                FROM telemetry
                WHERE rover_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (rover_id,),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            (
                rover_id,
                position_json,
                battery,
                velocity,
                mission_id,
                status,
                timestamp,
            ) = row
            position = tuple(json.loads(position_json))

            return rover_id, position, battery, velocity, mission_id, status, timestamp

        except sqlite3.Error as e:
            raise DatabaseException("Failed to fetch latest telemetry") from e

    def fetch_all_telemetry(self) -> list[tuple]:
        try:
            cursor = self.__connection.cursor()
            cursor.execute(
                """
                SELECT rover_id, position, battery_level, velocity, mission_id, operational_status, timestamp
                FROM telemetry
                ORDER BY timestamp DESC
                """
            )

            rows = cursor.fetchall()
            telemetry = []

            for (
                rover_id,
                position_json,
                battery,
                velocity,
                mission_id,
                status,
                timestamp,
            ) in rows:
                position = tuple(json.loads(position_json))
                telemetry.append(
                    (
                        rover_id,
                        position,
                        battery,
                        velocity,
                        mission_id,
                        status,
                        timestamp,
                    )
                )

            return telemetry

        except sqlite3.Error as e:
            raise DatabaseException("Failed to fetch telemetry") from e


    def update_mission_state(self, mission_id: str, state: int) -> None:
        cursor = self.__connection.cursor()
        cursor.execute(
            "UPDATE missions SET state = ? WHERE mission_id = ?",
            (state, mission_id),
        )
        self.__connection.commit()

    # ------------------------------------------------------------------
    # CLOSE
    # ------------------------------------------------------------------

    def close(self) -> None:
        try:
            self.__connection.close()
        except sqlite3.Error as e:
            raise DatabaseException("Failed to close database") from e
