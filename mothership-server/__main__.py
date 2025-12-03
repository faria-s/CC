import sys 
from threading import Thread
from lib.logging import log

from .Parser import Parser
from .Database import Database
from lib import MissionLink
from lib import TelemetryStreamServer

from lib import (MISSIONLINK_DEFAULT_PORT, TELEMETRY_DFAULT_PORT)

SERVER_IP = "0.0.0.0"

'''
def handle_missionLink_message(missions: dict[str, list[MessageTask]],
                           database: Database,
                           missionLink: MissionLink,
                           message_bytes: bytes,
                           agent: str) -> None:
    try:
        mission = Mission.deserialize(message_bytes)

        if isinstance(mission, MessageTasksRequest):
            if agent in tasks:
                for task in tasks[agent]:
                    missionLink.send(task.serialize(), agent)
                print(f'Sent tasks to {agent}')
            else:
                print(f'Ignoring MessageTasksRequest from unknown agent {agent}',
                      file=sys.stderr)
                nettask.close(agent)
        else:
            database.register_task(agent, False, message)
    except SerializationException as e:
        print(f'Ignoring SerializationException: {e}', file=sys.stderr)
    except DatabaseException as e:
        print(f'Ignoring DatabaseException: {e}', file=sys.stderr)

'''

def main(argv: list[str]) -> None:
    if len(argv) != 3:
        print('Usage: python -m mothership-server <missions_file> <database_file>')
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
            state=mission.state.value
        )
        log(f"Mission {mission.mission_id} inserted successfully")

    missionLink = MissionLink(SERVER_IP, MISSIONLINK_DEFAULT_PORT)
    missionLink.add_missions(missions)

    missionLink_thread = Thread(target=missionLink.start,daemon=True)
    missionLink_thread.start()

    telemetry_server = TelemetryStreamServer(SERVER_IP, TELEMETRY_DFAULT_PORT)
    telemetry_thread = Thread(target=telemetry_server.start_stream, daemon=True)
    telemetry_thread.start()

    missionLink_thread.join()
    database.close()

if __name__ == '__main__':
    main(sys.argv)
