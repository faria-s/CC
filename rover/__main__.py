import sys
import time
from socket import gethostname
from threading import Thread

from lib import (MISSIONLINK_DEFAULT_PORT,TELEMETRY_DFAULT_PORT, MissionLink)
from lib.TelemetryStream import TelemetryStreamClient, Telemetry

# to do: update telemetry and send periodically


def main(argv: list[str]) -> None:

    if len(argv) != 2:
        print('Usage: python -m rover <server_address>')
        sys.exit(1)

    server_address = argv[1]
    address = (server_address,MISSIONLINK_DEFAULT_PORT)

    missions = []

    missionLink = MissionLink(gethostname())
    missionLink_thread = Thread(target=missionLink.start,args=(address,),daemon=False)
    missionLink_thread.start()

    time.sleep(5)
    print("\n")

    missionLink._id_assigned_event.wait()  # blocks until ID is assigned
    print("Assigned rover ID:", missionLink.rover_id)

    missionLink._missions_assigned_event.wait()  # blocks until at least one mission received
    print("Missions received by rover:")
    for mission in missionLink.received_missions:
        print(mission)

    """
    
    telemetry_client = TelemetryStreamClient(server_address, TELEMETRY_DFAULT_PORT)
    telemetry_client.connect()
    telem_thread = Thread(target=telemetry_loop, args=(telemetry_client, missionLink.rover_id), daemon=True)
    telem_thread.start()
    """
    missionLink_thread.join()
    #telem_thread.join()

if __name__ == '__main__':
    main(sys.argv)
