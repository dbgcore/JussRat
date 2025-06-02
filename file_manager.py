import os
import json
import base64
import io
from PIL import Image
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QTreeWidget,
                             QTreeWidgetItem, QMenu, QInputDialog, QFileDialog, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

class FileManagerWindow(QMainWindow):
    def __init__(self, client_id, client_socket, client_ip, server_gui):
        super().__init__()
        self.client_id = client_id
        self.client_socket = client_socket
        self.client_ip = client_ip
        self.server_gui = server_gui
        self.setWindowTitle(f"File Manager - {client_ip}")
        self.setGeometry(100, 100, 800, 600)
        self.current_path = "C:\\"
        self.pending_operations = {}  # To track pending operations

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        button_panel = QWidget()
        button_layout = QVBoxLayout(button_panel)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_files)
        self.create_folder_btn = QPushButton("Create Folder")
        self.create_folder_btn.clicked.connect(self.create_folder)
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.upload_file)
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download_file)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_file)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.create_folder_btn)
        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.delete_btn)
        layout.addWidget(button_panel)

        self.path_label = QLabel(self.current_path)
        layout.addWidget(self.path_label)

        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(1, 1)
        layout.addWidget(self.preview_label, stretch=1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.setColumnWidth(0, 400)
        self.tree.itemDoubleClicked.connect(self.on_double_click)
        self.tree.itemClicked.connect(self.on_item_click)
        layout.addWidget(self.tree)

        self.context_menu = QMenu(self)
        self.context_menu.addAction("Refresh", self.refresh_files)
        self.context_menu.addAction("Create Folder", self.create_folder)
        self.context_menu.addAction("Upload", self.upload_file)
        self.context_menu.addAction("Download", self.download_file)
        self.context_menu.addAction("Delete", self.delete_file)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        self.refresh_files()

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item:
            self.tree.setCurrentItem(item)
            self.context_menu.exec_(self.tree.mapToGlobal(pos))

    def refresh_files(self):
        try:
            request_id = os.urandom(16).hex()  # Generate unique request ID
            self.pending_operations[request_id] = {
                'type': 'list',
                'path': self.current_path
            }
            
            self.client_socket.send(json.dumps({
                'type': 'file_operation',
                'request_id': request_id,
                'data': {'operation': 'list', 'path': os.path.normpath(self.current_path)}
            }).encode())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to request file list: {str(e)}")

    def handle_response(self, response):
        try:
            data = json.loads(response)
            request_id = data.get('request_id')
            operation = self.pending_operations.pop(request_id, None) if request_id else None
            
            if data.get('status') == 'error':
                QMessageBox.critical(self, "Error", data.get('message', 'Unknown error occurred'))
                return

            if operation and operation['type'] == 'list':
                self.update_file_list(data.get('data', []))
            elif operation and operation['type'] == 'download':
                if data.get('is_image', False):
                    self.update_preview(data.get('content', ''))
                else:
                    self.save_downloaded_file(data.get('content', ''), data.get('filename'))
            elif operation and operation['type'] == 'delete':
                QMessageBox.information(self, "Success", "File/folder deleted successfully")
                self.refresh_files()
            elif operation and operation['type'] == 'create':
                QMessageBox.information(self, "Success", "Folder created successfully")
                self.refresh_files()
            elif operation and operation['type'] == 'upload':
                QMessageBox.information(self, "Success", "File uploaded successfully")
                self.refresh_files()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to handle response: {str(e)}")

    def update_file_list(self, file_list):
        try:
            self.tree.clear()
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("No preview")
            
            # Add parent directory item (except for root)
            if self.current_path != "C:\\":
                parent_item = QTreeWidgetItem(["..", "Parent Directory"])
                self.tree.addTopLevelItem(parent_item)
            
            for file in file_list:
                item = QTreeWidgetItem([file['name'], "Folder" if file['is_dir'] else "File"])
                self.tree.addTopLevelItem(item)
                
            self.path_label.setText(os.path.normpath(self.current_path))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update file list: {str(e)}")

    def on_item_click(self, item):
        file_name = item.text(0)
        file_type = item.text(1)
        
        if file_name == ".." and file_type == "Parent Directory":
            return
            
        if file_type == "File" and file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            try:
                request_id = os.urandom(16).hex()
                self.pending_operations[request_id] = {
                    'type': 'download',
                    'path': os.path.normpath(os.path.join(self.current_path, file_name)),
                    'is_image': True
                }
                
                self.client_socket.send(json.dumps({
                    'type': 'file_operation',
                    'request_id': request_id,
                    'data': {
                        'operation': 'download',
                        'path': os.path.normpath(os.path.join(self.current_path, file_name))
                    }
                }).encode())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to request preview: {str(e)}")

    def update_preview(self, image_data):
        try:
            img_data = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_data))
            img_rgb = img.convert('RGB')
            qimg = QImage(img_rgb.tobytes(), img_rgb.width, img_rgb.height, img_rgb.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.preview_label.width(), self.preview_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(pixmap)
        except Exception as e:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Preview unavailable")

    def on_double_click(self, item):
        file_name = item.text(0)
        file_type = item.text(1)
        
        if file_name == ".." and file_type == "Parent Directory":
            # Go up one directory
            self.current_path = os.path.dirname(self.current_path)
            self.refresh_files()
            return
            
        if file_type == "Folder":
            self.current_path = os.path.normpath(os.path.join(self.current_path, file_name))
            self.refresh_files()

    def create_folder(self):
        folder_name, ok = QInputDialog.getText(self, "Create Folder", "Enter folder name:")
        if ok and folder_name:
            try:
                request_id = os.urandom(16).hex()
                self.pending_operations[request_id] = {
                    'type': 'create',
                    'path': os.path.normpath(os.path.join(self.current_path, folder_name))
                }
                
                self.client_socket.send(json.dumps({
                    'type': 'file_operation',
                    'request_id': request_id,
                    'data': {
                        'operation': 'create',
                        'path': os.path.normpath(os.path.join(self.current_path, folder_name))
                    }
                }).encode())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder: {str(e)}")

    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self)
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    file_data = base64.b64encode(f.read()).decode()
                
                filename = os.path.basename(file_path)
                request_id = os.urandom(16).hex()
                self.pending_operations[request_id] = {
                    'type': 'upload',
                    'path': os.path.normpath(os.path.join(self.current_path, filename))
                }
                
                self.client_socket.send(json.dumps({
                    'type': 'file_operation',
                    'request_id': request_id,
                    'data': {
                        'operation': 'upload',
                        'path': os.path.normpath(os.path.join(self.current_path, filename)),
                        'content': file_data
                    }
                }).encode())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to upload file: {str(e)}")

    def download_file(self):
        item = self.tree.currentItem()
        if not item:
            return
            
        file_name = item.text(0)
        file_type = item.text(1)
        
        if file_name == ".." and file_type == "Parent Directory":
            return
            
        if file_type == "Folder":
            QMessageBox.warning(self, "Warning", "Cannot download a folder")
            return
            
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, "Save File", file_name)
            if not save_path:
                return
                
            request_id = os.urandom(16).hex()
            self.pending_operations[request_id] = {
                'type': 'download',
                'path': os.path.normpath(os.path.join(self.current_path, file_name)),
                'save_path': save_path
            }
            
            self.client_socket.send(json.dumps({
                'type': 'file_operation',
                'request_id': request_id,
                'data': {
                    'operation': 'download',
                    'path': os.path.normpath(os.path.join(self.current_path, file_name))
                }
            }).encode())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to download file: {str(e)}")

    def save_downloaded_file(self, content, filename):
        try:
            if not content:
                raise ValueError("No content received")
                
            # Use the save_path from pending operations if available
            request_id = next((k for k, v in self.pending_operations.items() 
                             if v.get('type') == 'download' and v.get('path').endswith(filename)), None)
            
            if request_id:
                save_path = self.pending_operations[request_id].get('save_path', filename)
                self.pending_operations.pop(request_id, None)
            else:
                save_path = filename
                
            with open(save_path, 'wb') as f:
                f.write(base64.b64decode(content))
                
            QMessageBox.information(self, "Success", f"File saved to {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

    def delete_file(self):
        item = self.tree.currentItem()
        if not item:
            return
            
        file_name = item.text(0)
        file_type = item.text(1)
        
        if file_name == ".." and file_type == "Parent Directory":
            return
            
        reply = QMessageBox.question(
            self, 'Confirm Delete',
            f"Are you sure you want to delete {file_name}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                request_id = os.urandom(16).hex()
                self.pending_operations[request_id] = {
                    'type': 'delete',
                    'path': os.path.normpath(os.path.join(self.current_path, file_name))
                }
                
                self.client_socket.send(json.dumps({
                    'type': 'file_operation',
                    'request_id': request_id,
                    'data': {
                        'operation': 'delete',
                        'path': os.path.normpath(os.path.join(self.current_path, file_name))
                    }
                }).encode())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete file: {str(e)}")