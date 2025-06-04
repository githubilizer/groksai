import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QComboBox, QLabel, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, QDateTime
from PyQt6.QtGui import QColor, QTextCursor, QFont, QTextCharFormat, QBrush

class ConsolePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.message_count = 0
        self.auto_scroll = True
        self.logger = logging.getLogger(__name__)
        
        # Message buffer for performance
        self.message_buffer = []
        self.max_buffer_size = 1000
        self.current_filter = "All"
        
        # Set up a timer to flush the buffer periodically
        self.buffer_timer = QTimer(self)
        self.buffer_timer.timeout.connect(self.flush_buffer)
        self.buffer_timer.start(100)  # Flush every 100ms
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Controls panel
        controls_layout = QHBoxLayout()
        
        # Log level filter
        level_label = QLabel("Log Level:")
        level_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls_layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["All", "Info", "Warning", "Error"])
        controls_layout.addWidget(self.level_combo)
        
        # Filter input
        filter_label = QLabel("Filter:")
        filter_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.setEditable(True)
        self.filter_combo.addItems(["", "Agent:", "Test:", "Memory:"])
        controls_layout.addWidget(self.filter_combo)
        
        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self.toggle_auto_scroll)
        controls_layout.addWidget(self.auto_scroll_check)
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_console)
        controls_layout.addWidget(self.clear_button)
        
        layout.addLayout(controls_layout)
        
        # Console output
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.console_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: monospace;
                font-size: 9pt;
            }
        """)
        layout.addWidget(self.console_text)
    
    def add_message(self, message, level="INFO"):
        """Add a message to the console with timestamp"""
        self.message_count += 1
        
        # Format based on level
        format = QTextCharFormat()
        
        if level == "ERROR":
            format.setForeground(QColor("#ff5555"))
        elif level == "WARNING":
            format.setForeground(QColor("#ffaa00"))
        elif level == "SUCCESS":
            format.setForeground(QColor("#55ff55"))
        else:  # INFO
            format.setForeground(QColor("#e0e0e0"))
            
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
        full_message = f"[{timestamp}] {message}\n"
        
        # Get cursor and add text with formatting
        cursor = self.console_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(full_message, format)
        
        # Auto-scroll to bottom if enabled
        if self.auto_scroll:
            self.console_text.setTextCursor(cursor)
            self.console_text.ensureCursorVisible()
        
        # Add to buffer for performance
        self.message_buffer.append((message, level))
        
        # If buffer gets too large, flush immediately
        if len(self.message_buffer) > 50:
            self.flush_buffer()
    
    def flush_buffer(self):
        """Flush the message buffer to the console"""
        if not self.message_buffer:
            return
        
        current_filter = self.current_filter
        for message, level in self.message_buffer:
            # Skip if filtered out
            if current_filter != "All" and level != current_filter:
                continue
                
            # Set color based on level
            char_format = QTextCharFormat()
            if level == "ERROR":
                char_format.setForeground(QBrush(QColor(255, 100, 100)))  # Red
                char_format.setFontWeight(QFont.Weight.Bold)
            elif level == "WARNING":
                char_format.setForeground(QBrush(QColor(255, 165, 0)))  # Orange
            elif level == "DEBUG":
                char_format.setForeground(QBrush(QColor(120, 120, 120)))  # Gray
            elif level == "SYSTEM":
                char_format.setForeground(QBrush(QColor(100, 200, 255)))  # Light blue
            elif level == "TESTING":
                char_format.setForeground(QBrush(QColor(100, 255, 150)))  # Green
                char_format.setFontWeight(QFont.Weight.Bold)
            else:
                char_format.setForeground(QBrush(QColor(220, 220, 220)))  # Default light gray
            
            # Format and add text
            cursor = self.console_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(f"[{level}] ")
            cursor.insertText(f"{message}\n", char_format)
            
            # Increment count
            self.message_count += 1
        
        # Clear the buffer
        self.message_buffer = []
        
        # Scroll to bottom
        self.console_text.verticalScrollBar().setValue(self.console_text.verticalScrollBar().maximum())
    
    def apply_filter(self, filter_text):
        """Apply a filter to the console output"""
        self.current_filter = filter_text
        
        # Clear and re-add all messages with the filter
        self.console_text.clear()
        
        # Flush current buffer first
        temp_buffer = self.message_buffer
        self.message_buffer = []
        self.flush_buffer()
        
        # Reset buffer
        self.message_buffer = temp_buffer
        self.flush_buffer()
    
    def clear_console(self):
        """Clear the console"""
        self.console_text.clear()
        self.message_count = 0
        self.logger.debug("Console cleared")
        self.message_buffer = []
    
    def toggle_auto_scroll(self, state):
        """Toggle auto-scroll feature"""
        self.auto_scroll = bool(state) 