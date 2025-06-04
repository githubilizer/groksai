from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal

class PromptPanel(QWidget):
    prompt_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel("Enter your prompt:")
        layout.addWidget(self.label)

        self.input = QLineEdit()
        layout.addWidget(self.input)

        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.submit_prompt)
        layout.addWidget(self.submit_btn)

    def submit_prompt(self):
        prompt = self.input.text()
        if prompt:
            self.prompt_submitted.emit(prompt)
            self.input.clear() 