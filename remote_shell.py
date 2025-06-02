from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import Qt

class RemoteShellDialog(QDialog):
    def __init__(self, client_id, client_manager, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.client_manager = client_manager
        self.setWindowTitle(f"Remote Shell - Client {client_id}")
        self.setGeometry(200, 200, 600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Output area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("background-color: #333; color: #fff; font-family: 'Consolas', monospace;")
        layout.addWidget(self.output_text)

        # Input area
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.returnPressed.connect(self.send_command)
        input_layout.addWidget(self.command_input)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_command)
        input_layout.addWidget(send_button)

        layout.addLayout(input_layout)
        self.setLayout(layout)

    def send_command(self):
        command = self.command_input.text().strip()
        if command:
            self.append_output(f"> {command}")
            self.client_manager.send_shell_command(self.client_id, command)
            self.command_input.clear()

    def append_output(self, text):
        self.output_text.append(text)
        self.output_text.ensureCursorVisible()