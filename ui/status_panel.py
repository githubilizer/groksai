from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # System status label
        self.status_label = QLabel("System Status: Ready")
        self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        
        # Model info frame
        model_frame = QFrame()
        model_frame.setFrameShape(QFrame.Shape.StyledPanel)
        model_layout = QVBoxLayout(model_frame)
        
        self.model_label = QLabel("Ollama Model: Not set")
        self.model_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.model_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        model_layout.addWidget(self.model_label)
        
        layout.addWidget(model_frame)
        
        # Testing mode indicator
        testing_frame = QFrame()
        testing_frame.setFrameShape(QFrame.Shape.StyledPanel)
        testing_layout = QVBoxLayout(testing_frame)
        
        self.testing_mode_label = QLabel("Testing Mode: Automatic Incremental")
        self.testing_mode_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.testing_mode_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        testing_layout.addWidget(self.testing_mode_label)
        
        self.testing_info_label = QLabel("The system is automatically running tests incrementally with pauses between cycles.")
        self.testing_info_label.setWordWrap(True)
        self.testing_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        testing_layout.addWidget(self.testing_info_label)
        
        self.next_test_label = QLabel("Next Test: Waiting...")
        self.next_test_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        testing_layout.addWidget(self.next_test_label)
        
        layout.addWidget(testing_frame)
        
        # Memory usage progress bar
        self.memory_label = QLabel("Memory Usage:")
        self.memory_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.memory_label)
        
        self.memory_bar = QProgressBar()
        self.memory_bar.setRange(0, 100)
        self.memory_bar.setValue(0)
        self.memory_bar.setTextVisible(True)
        self.memory_bar.setFormat("%p%")
        layout.addWidget(self.memory_bar)
        
        # CPU usage progress bar
        self.cpu_label = QLabel("CPU Usage:")
        self.cpu_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.cpu_label)
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setTextVisible(True)
        self.cpu_bar.setFormat("%p%")
        layout.addWidget(self.cpu_bar)
        
        # GPU usage progress bar
        self.gpu_label = QLabel("GPU Usage:")
        self.gpu_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.gpu_label)
        
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setValue(0)
        self.gpu_bar.setTextVisible(True)
        self.gpu_bar.setFormat("%p%")
        layout.addWidget(self.gpu_bar)
        
        # Add stretch to push widgets to the top
        layout.addStretch()
        
    def update_status(self, status):
        if isinstance(status, str):
            self.status_label.setText(f"System Status: {status}")
        else:
            # It's a dictionary with full status
            running = status.get('running', False)
            paused = status.get('paused', False)
            
            if running:
                if paused:
                    status_text = "Paused"
                    status_color = "#ffaa00"  # Orange for paused
                else:
                    status_text = "Running"
                    status_color = "#00ff00"  # Green for running
            else:
                status_text = "Stopped"
                status_color = "#ff5555"  # Red for stopped
                
            self.status_label.setText(f"System Status: {status_text}")
            self.status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            
            # Update model info if available
            if 'model_name' in status:
                self.model_label.setText(f"Ollama Model: {status.get('model_name', 'Unknown')}")
            
            # Update cycle counter for next test prediction
            cycle_count = status.get('cycle_count', 0)
            if running and not paused:
                self.next_test_label.setText(f"Current Cycle: {cycle_count}")
            elif paused:
                self.next_test_label.setText(f"Cycle {cycle_count} (Paused)")
            else:
                self.next_test_label.setText("Next Test: System Stopped")
        
    def update_memory_usage(self, percentage):
        self.memory_bar.setValue(int(percentage))
        
    def update_cpu_usage(self, percentage):
        self.cpu_bar.setValue(int(percentage))
        
    def update_gpu_usage(self, percentage):
        self.gpu_bar.setValue(int(percentage))
        
    def update_model_info(self, model_name):
        """Update the displayed model name"""
        self.model_label.setText(f"Ollama Model: {model_name}")
        
    def add_status_message(self, message):
        """Display a temporary status message"""
        current_status = self.status_label.text()
        self.status_label.setText(f"System Status: {message}")
        self.status_label.setStyleSheet("color: #00aaff; font-weight: bold;")  # Blue for notifications
        
        # Reset the status after 3 seconds
        QTimer.singleShot(3000, lambda: self.status_label.setText(current_status))
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")) 