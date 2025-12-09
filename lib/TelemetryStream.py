import socket
import threading
import time
import random
from math import sqrt

from .logging import log
from .structs.Telemetry import Telemetry, OperationalStatus
from .structs.Mission import Mission

class TelemetryStreamClient:
    """
    A TCP client that handles telemetry sending for a rover.
    Generates telemetry, moves toward mission targets, and sends updates automatically.
    """

    def __init__(self, server_ip: str, server_port: int, rover_id: str, missions: list[Mission]):
        """
        Args:
            server_ip: Telemetry server IP
            server_port: Telemetry server port
            rover_id: Rover identifier
            missions: List of missions to perform
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.rover_id = rover_id
        self.missions = missions  # copy of the list
        self.current_mission_index = 0
        self.current_telemetry: Telemetry | None = None

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self._stop_event = threading.Event()

        self._telemetry_lock = threading.Lock()

    def start(self):
        """
        Connects to the Server
        """
        self.connect()
        if not self.connected:
            log("Cannot start telemetry loop — no connection.", "Error")
            return

        log("[TELEMETRY CLIENT] Starting mission loop and telemetry sender...", "Info")

        while not self._stop_event.is_set() and self.connected:
            self._mission_loop()

    def stop(self):
        """Stops loop and closes connection."""
        self._stop_event.set()
        if self.connected:
            self.socket.close()
        self.connected = False
        log("[TELEMETRY CLIENT] Stopped telemetry loop.", "Info")

    def connect(self):
        try:
            self.socket.connect((self.server_ip, self.server_port))
            self.connected = True
            log(f"[TELEMETRY CLIENT] Connected to {self.server_ip}:{self.server_port}", "Info")
        except Exception as e:
            log(f"[TELEMETRY CLIENT] Connection failed: {e}", "Error")
            self.connected = False

    def _mission_loop(self):
        """Loop over missions and update telemetry towards mission goals."""
        if self.current_mission_index >= len(self.missions):
            return  # no more missions

        mission = self.missions[self.current_mission_index]

        # generates its own telemetry once
        if self.current_telemetry is None:
            self.current_telemetry = self._generate_initial_telemetry()

        # given the mission updates its telemetry
        self._update_telemetry_for_mission(mission)

        self._send_current_telemetry()

        # if finished then send final packet
        if self.current_telemetry.get_operational_status == OperationalStatus.FINISHED:
            log(f"[ROVER] Mission {mission._mission_id} finished", "Info")
            self.current_mission_index += 1
            return 

        time.sleep(mission._report_time / 100) 

    def _generate_initial_telemetry(self) -> Telemetry:
        """Generates a random initial telemetry at the start of a mission."""
        position = (
            random.uniform(0, 100),
            random.uniform(0, 100),
            random.uniform(0, 10)
        )
        battery_level = 100.0
        velocity = random.uniform(0.5, 5.0)
        return Telemetry(
            rover_id=self.rover_id,
            position=position,
            battery_level=battery_level,
            velocity=velocity,
            operational_status=OperationalStatus.DOING
        )

    def _update_telemetry_for_mission(self, mission: Mission):
        """Move rover towards mission end coordinates and updates its telemetry."""
        if not self.current_telemetry:
            return

        current_x, current_y, current_z = self.current_telemetry.get_position
        target_x, target_y = mission._area[1]

        dx = target_x - current_x
        dy = target_y - current_y
        distance = sqrt(dx**2 + dy**2)

        if distance < 0.1:
            new_position = (target_x, target_y, current_z)
            new_status = OperationalStatus.FINISHED
        else:
            step_size = min(self.current_telemetry.get_velocity, distance)
            new_x = current_x + dx / distance * step_size
            new_y = current_y + dy / distance * step_size
            new_position = (new_x, new_y, current_z)
            new_status = OperationalStatus.DOING

        new_battery = max(0.0, self.current_telemetry.get_battery_level - 0.2)

        updated_telemetry = Telemetry(
            rover_id=self.rover_id,
            position=new_position,
            battery_level=new_battery,
            velocity=self.current_telemetry.get_velocity,
            operational_status=new_status
        )

        with self._telemetry_lock:
            self.current_telemetry = updated_telemetry

    def _send_current_telemetry(self):
        """Send the latest telemetry to the server."""
        with self._telemetry_lock:
            telemetry = self.current_telemetry
        if telemetry is None:
            return

        try:
            msg = telemetry.serialize()
            size = len(msg).to_bytes(4, "big")
            self.socket.sendall(size + msg)
            log(f"[TELEMETRY CLIENT] Sent telemetry: {telemetry}", "Debug")
        except Exception as e:
            log(f"[TELEMETRY CLIENT] Failed to send telemetry: {e}", "Error")
            self.connected = False
            self.socket.close()

class TelemetryStreamServer:
    """
    A class to handle telemetry data streaming over a network socket.
    """
    def __init__(self, address: str, port: int):
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = False
        self.client_threads = []
        self.telemetry_data: dict[str, Telemetry] = {}
        self.lock = threading.Lock()

    def start_stream(self):
        """
        Starts the telemetry TCP server.
        For each accepted connection, a new thread is spawned to handle the rover's telemetry data.
        """
        self.socket.bind((self.address, self.port))
        self.socket.listen(10) # max number of clients trying to connect
        self.is_running = True

        log(f"[TELEMETRY SERVER] Listening on {self.address}:{self.port}", "Info")

        while True:
            try:
                client_socket, client_address = self.socket.accept()
                log(f"[TELEMETRY SERVER] Rover connected from {client_address}", "Info")
                t = threading.Thread(
                    target=self.__handle_client,
                    args=(client_socket, client_address),
                    daemon=True,
                )
                t.start()
                self.client_threads.append(t)
            except KeyboardInterrupt:
                self.stop_server()

            except Exception as e:
                log(f"Error accepting connection: {e}.")

    def __handle_client(self, client_sock, client_addr):
        """Receives telemetry data from the rover, deserializes it, and logs the information.

        Args:
            client_sock: The socket connected to the rover.
            client_addr: The address of the connected rover.

        Logs:
            Info: When telemetry data is received.
            Warning: When the rover disconnects.
            Error: If there is an exception during data reception.
        """
        try:
            while self.is_running:
                # Read message size (first 4 bytes)
                size_bytes = client_sock.recv(4)
                if not size_bytes:
                    log(f"[TELEMETRY SERVER] Rover {client_addr} disconnected.", "Warning")
                    return

                size = int.from_bytes(size_bytes, "big")
                data = client_sock.recv(size, socket.MSG_WAITALL)
                telemetry = Telemetry.deserialize(data)

                # Store latest telemetry
                with self.lock:
                    self.telemetry_data[telemetry.get_rover_id] = telemetry

                log(f"[TELEMETRY SERVER] Received telemetry from Rover[{telemetry.get_rover_id}]: {telemetry}", "Info")

        except KeyboardInterrupt:
            log("Server interrupted manually. Stopping.", "INFO")
            self.stop_server()

        except Exception as e:
            log(f"[TELEMETRY SERVER] Connection with {client_addr} ended: {e}", "Error")

        finally:
            client_sock.close()

    def stop_server(self):
        """Stops the telemetry server and closes the listening socket."""
        self.is_running = False
        self.socket.close()
        log("[TELEMETRY SERVER] Server stopped.", "Info")

    def get_latest_telemetry(self, rover_id: str) -> Telemetry | None:
        """Return the latest telemetry for a given rover_id."""
        with self.lock:
            return self.telemetry_data.get(rover_id)
