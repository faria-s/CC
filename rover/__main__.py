import sys
import time
from socket import gethostname
from threading import Thread

from lib import (MISSIONLINK_DEFAULT_PORT,TELEMETRY_DFAULT_PORT, MissionLink)
from lib.TelemetryStream import TelemetryStreamClient, Telemetry

def main(argv: list[str]) -> None:

    if len(argv) != 2:
        print('Usage: python -m rover <server_address>')
        sys.exit(1)

    server_address = argv[1]
    address = (server_address,MISSIONLINK_DEFAULT_PORT)

    missionLink = MissionLink(gethostname())
    missionLink_thread = Thread(target=missionLink.start,args=(address,),daemon=False)
    missionLink_thread.start()

    time.sleep(5)
    print("\n")

    # Waits until the rover ID is assigned
    missionLink._id_assigned_event.wait()
    rover_id = missionLink.rover_id
    print(f"[ROVER] Assigned ID from server: {rover_id}")

    # Waits until all missions are assigned to the rover
    missionLink._missions_assigned_event.wait()
    print("[ROVER] Missions received by rover:")
    for mission in missionLink.received_missions:
        print(mission)

    missions = missionLink.received_missions.copy()

    telemetry_client = TelemetryStreamClient(
        server_ip=server_address,
        server_port=TELEMETRY_DFAULT_PORT,
        rover_id=rover_id,
        missions=missions
    )
    telemetry_thread = Thread(target=telemetry_client.start, daemon=True)
    telemetry_thread.start()

    missionLink_thread.join()
    telem_thread.join()

if __name__ == '__main__':
    main(sys.argv)