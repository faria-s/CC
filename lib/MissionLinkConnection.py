import time

from .structs.Packet import Packet, PacketType
from .structs.RegisterRoverResponse import RegisterRoverResponse
from .structs.ACK import Ack
from .structs.EndConnection import EndConnection
from logging import log

INITIAL_TIMEOUT = 5 # seconds
MINIMUM_TIMEOUT = 0.005 # seconds (needed to avoid busy waiting on localhost)
RETRANSMISSION_PENALIZATION = 1.25 # times original RTT estimation

WINDOW_SIZE = 32 # messages

class MissionLinkConnectionException(Exception):
    pass

class MissionLinkConnection:

    def __init__(self, own_address: str):
        current_time = time.time()

        self.__own_address = own_address

        #Incoming Data
        self.__received_queue: dict[int, Packet] = {}      # Packets received but not yet processed: dict[sequence_number,Packet]
        self.__last_known_other_alive = current_time        # Time of the last packet arriving 

        #Outgoing Data
        self.__sent_not_acknowledge: dict[int,Packet] = {}  # Packets sent waiting to be acknowledge (in window): dict[ack_number, Packet]
        self.__not_sent: list[Packet] = []           # Packets ready to be sent, wainting to enter window 
        self.__last_know_sent = current_time                # Time of the last packet sent

        #Flow Control
        self.__sent_packets = 0                             # Number of packets sent, waiting for ack response
        self.__messages_removed_from_receive_queue = 0

        self.__has_mission: bool = False

        # RTT



    def handle_received_ack(self, ack: Packet) -> bool:

        try:
            if ack.ack_number in self.__sent_not_acknowledge:
                del self.__sent_not_acknowledge[ack.ack_number]
                self.__sent_packets -= 1
                return True

        except Exception as e:
            log(e)
            return False



    def handle_sendable_register_response(self, response: Packet) -> "RegisterRoverResponse":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return RegisterRoverResponse(seq_number,ack_number)

    def handle_sendable_ack(self, response: Packet) -> "Ack":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return Ack(seq_number,ack_number)
        
    def handle_sendable_end_connection(self, response: Packet) -> "EndConnection":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return EndConnection(seq_number,ack_number)

    def get_sendable_packets(self) -> list[Packet]:
        ready_to_be_sent = []

        while self.__sent_packets < WINDOW_SIZE:
            try:
                packet_to_send = self.__not_sent.pop(0)
                ready_to_be_sent.append(packet_to_send)
                self.__sent_packets += 1

            except IndexError:
                break

            return ready_to_be_sent


    def update_seq_ack_number(self,packet: Packet) -> (int,int):
        seq_number = packet.sequence_number + 1
        ack_number = packet.ack_number + 1

        return (seq_number,ack_number)

    def add_sent_not_acked(self, ack_number: int,packet: Packet):
        self.__sent_not_acknowledge[ack_number] = Packet


    def add_packet_to_send(self, packet: Packet) -> bool:

        try:
            self.__not_sent.append(packet)
            return True

        except Exception as e:
            log(e, "Error")
            return False

    
    @property
    def has_mission(self):
        return self.__has_mission
    
    def set_has_mission(self, value: bool):
        self.__has_mission = value
