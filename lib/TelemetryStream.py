import socket
import threading

from structs.Telemetry import Telemetry
from .logging import log

class TelemetryStreamClient:
    '''
    A TCP client for sending alert messages to the server.
    '''
    def __init__(self, server_ip, server_port):
        '''
        Initializes the TCP client with the server's address and port.

        Args:
            server_ip (str): The server's IP address.
            server_port (int): The server's port number.
        '''
        self.server_ip = server_ip
        self.server_port = server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

    def connect(self):
        '''
        Connects to the server.
        '''
        try:
            self.socket.connect((self.server_ip, self.server_port))
            self.connected = True
            log(f"Connected to server at {self.server_ip}:{self.server_port}", "Info")
        except Exception as e:
            log(f"Failed to connect to server: {e}", "Error")   
            self.connected = False

    def send_telemetry(self, telemetry_message: Telemetry):
        '''
        Sends an alert message to the server.

        Args:
            telemetry_message: The telemetry message to send.
        '''
        if not self.connected:
            log("Not connected to server. Call connect() first.", "Warning")
            return

        try:
            msg = telemetry_message.serialize()

            # Send size first (4 bytes big-endian)
            size = len(msg).to_bytes(4, byteorder="big")
            self.socket.sendall(size + msg)

            log(f"[TELEMETRY CLIENT] Sent telemetry: {telemetry_message}", "Debug")
        except Exception as e:
            log(f"Failed to send alert message: {e}", "Error")
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
        self.socket.listen(10)
        self.is_running = True

        log(f"[TELEMETRY SERVER] Listening on {self.address}:{self.port}", "Info")

        while True:
            try:
                client_socket, client_address = self.socket.accept()
                threading.Thread(
                    target=self.__accept_clients,
                    args=(client_socket, client_address),
                    daemon=True
                ).start()
            except Exception as e:
                log(f"Error accepting connection: {e}.")

    def __accept_clients(self):
        """Accepts rover connections."""
        while self.is_running:
            try:
                client_sock, client_addr = self.socket.accept()
                log(f"[TELEMETRY SERVER] Rover connected from {client_addr}", "Info")

                t = threading.Thread(
                    target=self.__handle_client,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                t.start()
                self.client_threads.append(t)

            except Exception as e:
                if self.is_running:
                    log(f"[TELEMETRY SERVER] Accept error: {e}", "Error")

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

                # read the first 4 bytes (size)
                size_bytes = client_sock.recv(4)
                if not size_bytes:
                    log(f"[TELEMETRY SERVER] Rover {client_addr} disconnected.", "Warning")
                    return

                size = int.from_bytes(size_bytes, byteorder="big")
                data = client_sock.recv(size, socket.MSG_WAITALL)

                telemetry = Telemetry.deserialize(data)

                log(f"[TELEMETRY SERVER] Received telemetry from Rover[{telemetry.get_rover_id}]: {telemetry}", "Info")

        except Exception as e:
            log(f"[TELEMETRY SERVER] Connection with {client_addr} ended: {e}", "Error")
        finally:
            client_sock.close()
    
    def stop_server(self):
        """Stops the telemetry server and closes the listening socket."""
        self.is_running = False
        self.socket.close()
        log("[TELEMETRY SERVER] Server stopped.", "Info")