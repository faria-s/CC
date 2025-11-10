# UDP layered protocol

import socket
from threading import Condition, Thread

from .structs.Packet import Packet, PacketType
from .structs.RegisterRover import RegisterRover
from .structs.RegisterRoverResponse import RegisterRoverResponse
from .structs.Mission import Mission
from .structs.ACK import Ack 
from .structs.EndConnection import EndConnection
from .MissionLinkConnection import MissionLinkConnection, MissionLinkConnectionException

from .logging import log

from typing import Optional


class MissionLinkRuntimeException(Exception):
    pass

class MissionLink:

    def __init__(self, host: str, port: Optional[int] = None):
        '''
        Initializes the UDP server with the specified parameters.

        Args:
            host (str): Hostname or IP address to bind the server to.
            server_port (int): Port number to bind the server to.
        '''
        self._host = host
        self._port = port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__is_server = port is not None
        self.__accepting_connections = self.__is_server
        if self.__is_server:
            self.__socket.bind(('0.0.0.0', port))
        self.__is_running = False

        self.__missions: list[Mission] = []

        #Current active connections with rovers (str): rover ip
        self.__clients_addr: dict[str,tuple[str,int]] = {}
        self.__connections: dict[str,MissionLinkConnection] = {}



        self.__condition = Condition()


    def start(self, server_address: Optional[tuple[int,str]] = None, missions: Optional[list[Mission]] = None, received_mission: Optional[list[Mission]] = None):
            '''
            Starts the UDP server to listen for incoming packets.

            Continuously listens for incoming packets and spawns threads to handle them.
            '''
            self.__is_running = True
            hostname, port = self.__socket.getsockname()

            log(f"MissionLink server started on {hostname}:{port}.")

            if not self.__is_server:
                self.request_connection(server_address)

            while self.__is_running:
                try:
                    message, client_address = self.__socket.recvfrom(1024)

                    # Start a new thread for handling the received packet
                    mission = Thread(
                        target=self.handle_packet,
                        args=(message, client_address, missions),
                        daemon=True
                    ).start()

                    if mission:
                        received_missions.append(mission)
                        
                except KeyboardInterrupt:
                    log("Server interrupted manually. Stopping.", "INFO")
                    self.__stop()
                except Exception as e:
                    log(f"{e}", "ERROR")


    def stop(self):
        '''
        Stops the UDP server and releases the socket.
        '''
        self.is_running = False
        self.socket.close()
        log("MissionLink Server stopped.", "INFO")


    def handle_packet_deserialize(self, data: bytes):
        '''
        Deserializes the raw packet data into the appropriate packet type.

        Args:
            data (bytes): Raw packet data.

        Returns:
            Packet: An instance of the appropriate packet subclass.
        '''
        packet_type_value = data[0]
        packet_type = PacketType(packet_type_value)

        match packet_type:
            case PacketType.RegisterRover:
                return RegisterRover.deserialize(data)

            case PacketType.RegisterRoverResponse:
                return RegisterRoverResponse.deserialize(data)

            case PacketType.Mission:
                return Mission.deserialize(data)

            case PacketType.Ack:
                return Ack.deserialize(data)

            case PacketType.EndConnection:
                return EndConnection.deserialize(data)

            case _:
                raise ValueError("Unknown packet type.")

    def handle_packet(self, message: bytes, client_address: tuple[str,int], missions: Optional[list[Mission]] = None):
        '''
        Handles incoming packets from clients.

        Processes the packet, verifies checksums, and adds it to the appropriate client queue.

        Args:
            message (bytes): The raw packet data received from the client.
            client_address (tuple): The address of the client sending the packet.
        ''' 
        try:

            host, port = client_address
            received_packet = self.handle_packet_deserialize(message)
            message = ""
                    

            # Initializing connection
            if self.__is_server and isinstance(received_packet,RegisterRover):

                if host not in self.__clients_addr:
                    self.__clients_addr[host] = client_address

                connection = self.__connections[host] = MissionLinkConnection(host)

                response = self.__connections[host].handle_sendable_register_response(received_packet)
                connection.add_packet_to_send(response)

                message = f"Server confirms connection with {host}:{port}" 


            elif isinstance(received_packet, RegisterRoverResponse):

                connection = self.__connections[host] = MissionLinkConnection(host)

                ack = self.__connections[host].handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                message = f"Sending Ack={ack.ack_number} to {host}:{port}"


            elif isinstance(received_packet, Ack):

                connection = self.__connections[host]
                connection.handle_received_ack(received_packet)

            elif isinstance(received_packet, Mission):

                connection = self.__connections[host]

                ack = connection.handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                message = f"Sending Ack={ack.ack_number} to {host}:{port}"

                
            elif isinstance(received_packet, EndConnection):

                connection = self.__connections[host]

                ack = connection.handle_sendable_ack(received_packet)
                connection.add_packet_to_send(ack)

                try:
                    del self.__connections[host]
                except Exception as e:
                    log(e)
                    return

                message = f"Ending Connection with {host}:{port}"
                
            else:
                raise ValueError("Unknown packet type.")
                return 

            connection = self.__connections[host]
            packets = connection.get_sendable_packets()
            self.send_packets(packets, client_address)
            log(message)

        except Exception as e:
            log(f"Error handling packet from {client_address}: {e}", "ERROR")


    def send_packet(self, packet: bytes, client_address: tuple[str,int] ):
        try:
            self.__socket.sendto(packet, client_address)
        except OSError:
            pass
        
    def send_packets(self, packets: list[Packet], address: tuple[int,str]):
        try:
            if packets:
                for packet in packets:
                    self.send_packet(packet.serialize(), address)

        except Exception as e:
            log(e, "Error")




    def send_ack(self, ack: Ack, client_address: tuple[str,int]):
        try:
            log(f"Sending ACK={packet.ack_number}")
            self.send_packet(ack,client_address)
        except Exception as e:
            log(e, "Error")


    def send_missions(self, client_address: tuple[str,int]):
        host, port = client_address

        try:
            if self.__missions:
                for mission in self.__missions:

                    
                    packet = Packet(PacketType.Mission,mission.serialize())
                    log(f"Sending Pakcet Seq={packet.sequence_number}")
                    self.send_packet(packet.serialize(), client_address)

        except MissionLinkConnectionException:
            pass
    

    def request_connection(self,server_address: tuple[int,str]):
        host,port = server_address

        self.__clients_addr[host] = server_address
        
        request_packet = RegisterRover().serialize()

        own_addr, own_port = self.__socket.getsockname()
        log(f"Rover {own_addr}:{own_port}: requesting connection")

        self.send_packet(request_packet, (host,port))



    def add_missions(self, missions: list[Mission]):

        if missions:
            for mission in missions:
                self.__missions.append(Mission)
