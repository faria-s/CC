import sys
from socket import gethostname
from threading import Thread

from lib import (MISSIONLINK_DEFAULT_PORT,TELEMETRY_DFAULT_PORT, MissionLink)



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


if __name__ == '__main__':
    main(sys.argv)
