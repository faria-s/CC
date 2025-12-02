# UDP layered protocol

import socket
import time
from collections import deque
from threading import Condition, Thread
from typing import Optional

from .logging import log
from .MissionLinkConnection import MissionLinkConnection, MissionLinkConnectionException
from .structs.ACK import Ack
from .structs.EndConnection import EndConnection
from .structs.Mission import Mission
from .structs.Packet import Packet, PacketType
from .structs.RegisterRover import RegisterRover
from .structs.RegisterRoverResponse import RegisterRoverResponse


class MissionLinkRuntimeException(Exception):
    pass


class MissionLink:
    def __init__(self, host: str, port: Optional[int] = None):
        """
        Initializes the UDP server with the specified parameters.

        Args:
            host (str): Hostname or IP address to bind the server to.
            server_port (int): Port number to bind the server to.
        """
        self._host = host
        self._port = port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__is_server = port is not None
        self.__accepting_connections = self.__is_server
        if self.__is_server:
            self.__socket.bind(("0.0.0.0", port))
        self.__is_running = False

        self.__missions_to_send: deque[Mission] = deque()
        self.__missions_being_done: dict[str, Mission] = {}

        # Current active connections with rovers (str): rover ip
        self.__clients_addr: dict[str, tuple[str, int]] = {}
        self.__connections: dict[str, MissionLinkConnection] = {}

        self.__condition = Condition()

        self._rover_id: Optional[str] = None      # Only on rover
        self.__next_rover_id = 1                  # rover id counter

    @property
    def rover_id(self):
        return self._rover_id

    def start(
        self,
        server_address: Optional[tuple[str, int]] = None,
        missions: Optional[list[Mission]] = None,
        received_mission: Optional[list[Mission]] = None,
    ):
        """
        Starts the UDP server to listen for incoming packets.

        Continuously listens for incoming packets and spawns threads to handle them.
        """
        self.__is_running = True
        hostname, port = self.__socket.getsockname()

        log(f"MissionLink server started on {hostname}:{port}.")

        if not self.__is_server and server_address:
            self.request_connection(server_address)

        while self.__is_running:
            try:
                message, client_address = self.__socket.recvfrom(1024)

                # Start a new thread for handling the received packet
                Thread(
                    target=self.handle_packet,
                    args=(message, client_address, missions),
                    daemon=True,
                ).start()

            except KeyboardInterrupt:
                log("Server interrupted manually. Stopping.", "INFO")
                self.stop()
            except Exception as e:
                log(f"{e}", "ERROR")

    def stop(self):
        """
        Stops the UDP server and releases the socket.
        """
        self.is_running = False
        self.__socket.close()
        log("MissionLink Server stopped.", "INFO")

    def handle_packet_deserialize(self, data: bytes):
        """
        Deserializes the raw packet data into the appropriate packet type.

        Args:
            data (bytes): Raw packet data.

        Returns:
            Packet: An instance of the appropriate packet subclass.
        """
        packet_type_value = data[0]
        packet_type = PacketType(packet_type_value)

        match packet_type:
            case PacketType.RegisterRover:
                return RegisterRover.deserialize(data)

            case PacketType.RegisterRoverResponse:
                return RegisterRoverResponse.deserialize(data)

            case PacketType.Mission:
                return Packet.deserialize(data)

            case PacketType.Ack:
                return Ack.deserialize(data)

            case PacketType.EndConnection:
                return EndConnection.deserialize(data)

            case _:
                raise ValueError("Unknown packet type.")

    def handle_packet(
        self,
        packet_received: bytes,
        client_address: tuple[str, int],
        missions: Optional[list[Mission]] = None,
    ):
        """
        Handles incoming packets from clients.

        Processes the packet, verifies checksums, and adds it to the appropriate client queue.

        Args:
            message (bytes): The raw packet data received from the client.
            client_address (tuple): The address of the client sending the packet.
        """
        try:
            host, port = client_address
            received_packet = self.handle_packet_deserialize(packet_received)
            message: str = ""

            # Initializing connection
            if self.__is_server and isinstance(received_packet, RegisterRover):
                if host not in self.__clients_addr:
                    self.__clients_addr[host] = client_address

                    # Assign an ID to the rover
                    rover_id = f"rover_{self.__next_rover_id}"
                    self.__next_rover_id += 1
                    log(f"Assigned ID {rover_id} to {host}")
                    # CHANGED: Only create connection and start thread for NEW connections
                    connection = self.__connections[host] = MissionLinkConnection(host)
                    connection.start_retransmission_thread(
                        self.__socket, client_address
                    )

                # Get existing connection (just created or already exists)
                connection = self.__connections[host]
                rover_id = f"rover_{self.__next_rover_id - 1}"
                response = connection.handle_sendable_register_response(received_packet, rover_id)
                connection.add_packet_to_send(response)

                message = f"Server confirms connection with {host}:{port} (ID: {rover_id})"

            elif isinstance(received_packet, RegisterRoverResponse):
                connection = self.__connections[host]

                # Saves the rover id assigned by the server
                self._rover_id = received_packet.rover_id
                log(f"[ROVER] Assigned ID from server: {self._rover_id}")
                ack = connection.handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                message = f"Sending Ack={ack.sequence_number} to {host}:{port}"

            elif isinstance(received_packet, Ack):
                connection = self.__connections[host]
                connection.handle_received_ack(received_packet)

                if (not connection.has_mission) and self.__missions_to_send:
                    mission = self.__missions_to_send.popleft()
                    self.__missions_being_done[host] = mission
                    seq, ack = connection.update_seq_ack_number(received_packet)

                    packet = Packet(PacketType.Mission, seq, ack, mission.serialize())
                    connection.add_packet_to_send(packet)
                    connection.set_has_mission(True)

                    message = f"Sending Seq={packet.sequence_number} to {host}:{port}"
                else:
                    message = f"Received Ack={received_packet.sequence_number} from {host}:{port}"

            elif isinstance(received_packet, EndConnection):
                connection = self.__connections[host]
                ack = connection.handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                connection.stop_retransmission_thread()
                del self.__connections[host]

                message = f"Ending Connection with {host}:{port}"

            elif isinstance(received_packet, Packet):
                mission_body = received_packet.body

                if mission_body:
                    mission = Mission.deserialize(mission_body)

                connection = self.__connections[host]

                ack = connection.handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                message = f"Sending Ack={ack.sequence_number} to {host}:{port}"

            else:
                raise ValueError("Unknown packet type.")
                return

            connection = self.__connections[host]
            packets = connection.get_sendable_packets()
            self.send_packets(packets, client_address)
            log(message)

        except Exception as e:
            log(f"Error handling packet from {client_address}: {e}", "ERROR")

    def send_packet(
        self,
        packet: bytes,
        ack_number: int,
        client_address: tuple[str, int],
        connection: MissionLinkConnection,
    ):
        try:
            self.__socket.sendto(packet, client_address)
        except OSError:
            pass

    def send_packets(self, packets: list[Packet], address: tuple[str, int]):
        try:
            if packets:
                for packet in packets:
                    host, port = address
                    connection = self.__connections[host]
                    self.send_packet(
                        packet.serialize(), packet.ack_number, address, connection
                    )

                    if self.__is_server:
                        connection.add_sent_not_acked(packet.ack_number, packet)
                        connection.set_send_times(packet.ack_number, time.time())

        except Exception as e:
            log(f"{e}", "Error")

    def request_connection(self, server_address: tuple[str, int]):
        host, port = server_address

        self.__clients_addr[host] = server_address

        connection = self.__connections[host] = MissionLinkConnection(host)
        connection.start_retransmission_thread(self.__socket, server_address)

        request_packet = RegisterRover()
        ack = request_packet.ack_number

        own_addr, own_port = self.__socket.getsockname()
        log(f"Rover {own_addr}:{own_port}: requesting connection")

        self.send_packet(request_packet.serialize(), ack, (host, port), connection)

    def add_missions(self, missions: list[Mission]):
        if missions:
            for mission in missions:
                self.__missions_to_send.append(mission)