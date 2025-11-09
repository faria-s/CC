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

        #Current active connections with rovers (str): rover ip
        self.__clients_addr: dict[str,tuple[str,int]] = {}
        self.__connections: dict[str,MissionLinkConnection] = {}


        self.__condition = Condition()


    def start(self, missions: Optional[list[Mission]] = None, received_mission: Optional[list[Mission]] = None):
            '''
            Starts the UDP server to listen for incoming packets.

            Continuously listens for incoming packets and spawns threads to handle them.
            '''
            self.__is_running = True
            hostname, port = self.__socket.getsockname()

            log(f"MissionLink server started on {hostname}:{port}.")


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

    def handle_packet(self, message: bytes, client_address: tuple[str,int], missions: Optional[list[Mission]] = None) -> Packet:
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

                    

            # Initializing connection
            if self.__is_server and isinstance(received_packet,RegisterRover):

                if host not in self.__clients_addr:
                    self.__clients_addr[host] = client_address

                self.__connections[host] = MissionLinkConnection(host)

                response = RegisterRoverResponse().serialize()

                log(f"Server confirms connection with {host}:{port}")
                self.send_packet(response, client_address)

            elif isinstance(received_packet, RegisterRoverResponse):

                self.__connections[host] = MissionLinkConnection(host)

                response = self.__connections[host].handle_sendable_ack(received_packet)

                log(f"Sending Ack={response.ack_number} to {host}:{port}")
                self.send_packet(response.serialize(), client_address)

            elif isinstance(received_packet, Ack):
                connection = self.__connections[host]
                packets_to_send = connection.handle_received_ack(received_packet)

                self.send_packets(packets_to_send, client_address)

            elif isinstance(received_packet, Mission):
                connection = self.__connections[host]
                ack = connection.handle_sendable_ack(received_packet)
                self.send_ack(ack)
                return Mission
                
            elif isinstance(received_packet, EndConnection):
                del self.__connections[host]

                ack = handle_sendable_ack(received_packet)
                self.send_ack(ack)
                

            else:
                raise ValueError("Unknown packet type.")

            
            return None
            
        except Exception as e:
            log(f"Error handling packet from {client_address}: {e}", "ERROR")


    def send_packet(self, packet: bytes, client_address: tuple[str,int] ):
        try:
            self.__socket.sendto(packet, client_address)
        except OSError:
            pass
        
    def send_ack(self, ack: Ack, client_address: tuple[str,int]):
        try:
            log(f"Sending ACK={packet.ack_number}")
            self.send_packet(ack,client_address)
        except Exception as e:
            log(e, "Error")


    def send_packets(self, packets: list[Packet], client_address: tuple[str,int]):
        host, port = client_address

        try:
            if packets:
                for packet in packets:
                    log(f"Sending Pakcet Seq={packet.sequence_number}")
                    self.send_packet(packet.serialize(), client_address)

        except MissionLinkConnectionException:
            pass
    

    def request_connection(self,host: str, port: int):

        self.__clients_addr[host] = (host,port)
        
        request_packet = RegisterRover().serialize()

        own_addr, own_port = self.__socket.getsockname()
        log(f"Rover {own_addr}:{own_port}: requesting connection")

        self.send_packet(request_packet, (host,port))



