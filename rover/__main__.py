import sys
from socket import gethostname
from threading import Thread

from lib import (MISSIONLINK_DFAULT_PORT, TELEMETRY_DFAULT_PORT, MissionLink)



def main(argv: list[str]) -> None:

    if len(argv) != 2:
        print('Usage: python -m rover <server_address>')
        sys.exit(1)

    server_address = argv[1]

    missions = []

    missionLink = MissionLink(gethostname())
    missionLink.request_connection(server_address, MISSIONLINK_DFAULT_PORT)
    missionLink.start(None, missions)


if __name__ == '__main__':
    main(sys.argv)
