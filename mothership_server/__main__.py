import signal
import sys
from threading import Thread

from lib import (
    MISSIONLINK_DEFAULT_PORT,
    TELEMETRY_DFAULT_PORT,
    MissionLink,
    TelemetryStreamServer,
    log,
)

from .Database import Database
from .Parser import Parser

# from .ObservationAPI import run_api

SERVER_IP = "0.0.0.0"


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        print("Usage: python -m mothership-server <missions_file> <database_file>")
        sys.exit(1)

    missions_file = argv[1]
    database_file = argv[2]

    missions = Parser.parse_missions(missions_file)
    database = Database(database_file)

    for mission in missions:
        database.insert_mission(
            mission_id=mission.mission_id,
            area=mission.area,
            task=mission.task,
            duration=mission.duration,
            report_time=mission.report_time,
            state=mission.state.value,
        )
        log(f"Mission {mission.mission_id} inserted successfully")

    missionLink = MissionLink(SERVER_IP, MISSIONLINK_DEFAULT_PORT)
    missionLink.add_missions(missions)

    missionLink_thread = Thread(target=missionLink.start, daemon=True)
    missionLink_thread.start()

    telemetry_server = TelemetryStreamServer(SERVER_IP, TELEMETRY_DFAULT_PORT, database)

    def shutdown_server(signal_received, frame):
        print("Shutting down server...")
        telemetry_server.stop_server()
        sys.exit(0)

    # Catch SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, shutdown_server)

    telemetry_thread = Thread(target=telemetry_server.start_stream, daemon=True)
    telemetry_thread.start()

    """
    api_thread = Thread(
        target=run_api,
        args=(database, telemetry_server, SERVER_IP, 8000),
        daemon=True,
    )
    api_thread.start()
    """
    missionLink_thread.join()
    database.close()


if __name__ == "__main__":
    main(sys.argv)
