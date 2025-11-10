import sqlite3
from lib.logging import log
import json

class DatabaseException(Exception):
    pass

class Database:
    '''
    Initializes the database by creating the necessary tables if they do not exist.

    Creates two tables:
    - `missions`: Stores missons to be send to the rovers.
    - `reports`: Stores the reports sent by the rovers about the missions.

    Args:
        path (str): The file path to the SQLite database.

    Returns:
        None
    '''

    def __init__(self, path: str):
        try:
            self.__connection = sqlite3.connect(path)
            cursor = self.__connection.cursor()

            # Added "state" column (INTEGER, because it maps to MissionState.value)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT NOT NULL,
                    area TEXT NOT NULL,
                    task TEXT NOT NULL,
                    duration REAL,
                    report_time REAL,
                    state INTEGER NOT NULL
                )
            ''')

            self.__connection.commit()

            log("Missions table and database started successfully.")

        except sqlite3.Error as e:
            raise DatabaseException("Failed to initialize database") from e

    def insert_mission(self,
                       mission_id: str,
                       area: list[tuple[float, float]],
                       task: str,
                       duration: int,
                       report_time: int,
                       state: int) -> None:
        """
        Insert a mission into the missions table.
        state: integer representing MissionState.value
        """
        try:
            cursor = self.__connection.cursor()

            area_json = json.dumps(area)

            cursor.execute('''
                INSERT INTO missions (mission_id, area, task, duration, report_time, state)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (mission_id, area_json, task, duration, report_time, state))

            self.__connection.commit()

        except sqlite3.Error as e:
            raise DatabaseException("Failed to insert mission") from e

    def fetch_all_missions(self) -> list[tuple]:
        """Fetch all missions (raw tuples)."""
        try:
            cursor = self.__connection.cursor()
            cursor.execute("SELECT mission_id, area, task, duration, report_time, state FROM missions")
            rows = cursor.fetchall()

            missions = []
            for mission_id, area_json, task, duration, report_time, state in rows:
                area = json.loads(area_json)
                missions.append((mission_id, area, task, duration, report_time, state))

            return missions

        except sqlite3.Error as e:
            raise DatabaseException("Failed to fetch missions") from e


    def close(self) -> None:
        """Close the database connection."""
        try:
            self.__connection.close()
        except sqlite3.Error as e:
            raise DatabaseException("Failed to close database") from e
