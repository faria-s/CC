import threading
import time
from typing import Optional

from .logging import log
from .structs.ACK import Ack
from .structs.EndConnection import EndConnection
from .structs.Packet import Packet
from .structs.RegisterRoverResponse import RegisterRoverResponse

INITIAL_TIMEOUT = 5  # seconds
MINIMUM_TIMEOUT = 0.05  # seconds (needed to avoid busy waiting on localhost)
RETRANSMISSION_PENALIZATION = 1.5  # times original RTT estimation

WINDOW_SIZE = 32  # messages
DELTA = 0.125
BETA = 0.25


class MissionLinkConnectionException:
    pass


class MissionLinkConnection:
    def __init__(self, own_address: str):
        current_time = time.time()
        
        self.__own_address = own_address

        # Incoming Data
        self.__received_queue: dict[int, Packet] = {}           # Packets received but not yet processed: dict[sequence_number,Packet]
        self.__last_known_other_alive = current_time            # Time of the last packet arriving

        # Outgoing Data
        self.__sent_not_acknowledge: dict[int, Packet] = {}     # Packets sent waiting to be acknowledge (in window): dict[ack_number, Packet]
        self.__not_sent: list[Packet] = []                      # Packets ready to be sent, wainting to enter window
        self.__last_know_sent = current_time                    # Time of the last packet sent

        # Flow Control
        self.__sent_packets = 0                                 # Number of packets sent, waiting for ack response
        self.__messages_removed_from_receive_queue = 0

        self.__has_mission: bool = False

        # RTT estimation
        self.__rtt_avg_estimate: Optional[float] = None
        self.__rtt_sample_rtt: Optional[float] = None
        self.__rtt_stdev_estimate: Optional[float] = None
        self.__send_times: dict[int, float] = {}
        self.__running = False
        self.__retransmission_thread = None
        self.__thread_lock = threading.Lock()

    def handle_received_ack(self, ack: Packet) -> bool:
        try:
            ack_num = ack.sequence_number
            if ack_num in self.__sent_not_acknowledge:
                del self.__sent_not_acknowledge[ack_num]
                self.__sent_packets -= 1

            if ack_num in self.__send_times:
                send_time = self.__send_times.pop(ack_num)
                sample_rtt = time.time() - send_time

                self.update_rtt_estimates(sample_rtt)

            return True

        except Exception as e:
            log(f"{e}", "Error")
            return False

    def handle_sendable_register_response(
        self, response: Packet, rover_id: str
    ) -> "RegisterRoverResponse":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return RegisterRoverResponse(seq_number, ack_number, rover_id)

    def handle_sendable_ack(self, response: Packet) -> "Ack":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return Ack(seq_number, ack_number)

    def handle_sendable_end_connection(self, response: Packet) -> "EndConnection":
        seq_number, ack_number = self.update_seq_ack_number(response)
        return EndConnection(seq_number, ack_number)

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

    def update_seq_ack_number(self, packet: Packet) -> tuple[int, int]:
        seq_number = packet.sequence_number + 1
        ack_number = packet.ack_number + 1

        return (seq_number, ack_number)

    def add_sent_not_acked(self, ack_number: int, packet: Packet):
        self.__sent_not_acknowledge[ack_number] = packet

    def add_packet_to_send(self, packet: Packet) -> bool:
        try:
            self.__not_sent.append(packet)
            return True

        except Exception as e:
            log(e, "Error")
            return False

    def update_rtt_estimates(self, sample_rtt: float) -> None:
        """
        Update RTT estimates using TCP-style smoothing:

            EstimatedRTT = (1 - DELTA) * EstimatedRTT + DELTA * SampleRTT
            DevRTT = (1 - BETA) * DevRTT + BETA * |SampleRTT - EstimatedRTT|

        If no prior estimates exist, initializes them from the first sample.
        """

        if self.__rtt_avg_estimate is None or self.__rtt_stdev_estimate is None:
            self.__rtt_avg_estimate = sample_rtt
            self.__rtt_stdev_estimate = sample_rtt / 2
            self.__rtt_sample_rtt = sample_rtt
            return

        self.__rtt_sample_rtt = sample_rtt

        self.__rtt_avg_estimate = (
            1 - DELTA
        ) * self.__rtt_avg_estimate + DELTA * sample_rtt

        self.__rtt_stdev_estimate = (1 - BETA) * self.__rtt_stdev_estimate + BETA * abs(
            sample_rtt - self.__rtt_avg_estimate
        )

    def get_timeout(self) -> float:
        """Returns the timeout value, handling uninitialized RTT estimates."""

        if self.__rtt_avg_estimate is None or self.__rtt_stdev_estimate is None:
            return INITIAL_TIMEOUT

        return self.__rtt_avg_estimate + 4 * self.__rtt_stdev_estimate

    def start_retransmission_thread(self, socket, client_address):
        """
        Starts a background thread that periodically checks for packet timeouts
        and retransmits unacknowledged packets. Only starts if not already running.
        """

        with self.__thread_lock:
            if self.__running and self.__retransmission_thread is not None:
                return

            self.__running = True
            self.__retransmission_thread = threading.Thread(
                target=self.__retransmission_worker,
                args=(socket, client_address),
                daemon=True,
            )
            self.__retransmission_thread.start()

    def __retransmission_worker(self, socket, client_address):
        """
        Periodically checks sent-but-not-acknowledged packets and retransmits
        those whose ACKs did not arrive in time. Stops when no packets remain.
        """

        while self.__running:
            try:
                if not self.__sent_not_acknowledge:
                    time.sleep(MINIMUM_TIMEOUT)
                    continue

                now = time.time()

                for ack_num, packet in list(self.__sent_not_acknowledge.items()):
                    if ack_num not in self.__send_times:
                        continue

                    send_time = self.__send_times[ack_num]
                    timeout = (
                        self.get_timeout()
                        if self.__rtt_avg_estimate
                        else INITIAL_TIMEOUT
                    )

                    if now - send_time > timeout:
                        socket.sendto(packet.serialize(), client_address)
                        self.__send_times[ack_num] = time.time()

                        self.__rtt_avg_estimate = (
                            self.__rtt_avg_estimate * RETRANSMISSION_PENALIZATION
                            if self.__rtt_avg_estimate
                            else INITIAL_TIMEOUT
                        )

                        print(
                            f"[RETRANSMIT] Packet Seq={packet.sequence_number} to {client_address}, timeout={timeout:.3f}s"
                        )

                time.sleep(MINIMUM_TIMEOUT)

            except Exception as e:
                print(f"[Retransmission error] {e}")
                break

        print(f"[RETRANSMIT] Thread stopping for {client_address}")

    def stop_retransmission_thread(self):
        """Signals the retransmission loop to exit cleanly."""

        with self.__thread_lock:
            if not self.__running:
                return

            self.__running = False

            if self.__retransmission_thread is not None:
                self.__retransmission_thread.join(timeout=1.0)
                self.__retransmission_thread = None

            if (
                self.__rtt_avg_estimate is not None
                and self.__rtt_stdev_estimate is not None
            ):
                self.__rtt_avg_estimate *= RETRANSMISSION_PENALIZATION
                self.__rtt_stdev_estimate *= RETRANSMISSION_PENALIZATION**0.5
            else:
                self.__rtt_avg_estimate = INITIAL_TIMEOUT
                self.__rtt_stdev_estimate = INITIAL_TIMEOUT / 2

    @property
    def has_mission(self):
        return self.__has_mission

    @property
    def sent_not_acknowledge(self):
        return self.__sent_not_acknowledge

    def set_send_times(self, seq_number: int, time: float):
        self.__send_times[seq_number] = time

    def set_has_mission(self, value: bool):
        self.__has_mission = value