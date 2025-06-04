from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QFrame, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QColor

class LearningFeedItem(QFrame):
    """A widget representing a single learning item in the feed"""
    def __init__(self, learning_data, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("background-color: #333; border-radius: 4px; margin: 2px;")
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Timestamp and type header
        header_layout = QHBoxLayout()
        
        # Learning type (success, fix, or general learning)
        learning_type = learning_data.get('type', 'learning')
        
        # Choose color based on learning type
        if learning_type == "success_learning":
            type_color = "#00aaff"  # Blue for success learning
        elif learning_type == "fix_learning":
            type_color = "#55ff55"  # Green for fix events
        elif learning_type == "test_failure":
            type_color = "#ff5555"  # Red for test failures
        else:
            type_color = "#ffaa00"  # Orange for other learning events
        
        # Format the type label text
        type_text = learning_type.replace('_', ' ').title()
        if learning_type == "fix_learning":
            type_text = "Test Fixed"
        
        type_label = QLabel(type_text)
        type_label.setStyleSheet(f"color: {type_color}; font-weight: bold;")
        type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(type_label)
        
        # Timestamp (right-aligned)
        timestamp = learning_data.get('timestamp', '')
        time_label = QLabel(timestamp)
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_label.setStyleSheet("color: #aaaaaa; font-style: italic;")
        time_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        # Insight content
        concept = learning_data.get('concept', '')
        if concept:
            concept_label = QLabel(f"Concept: {concept}")
            concept_label.setStyleSheet("font-weight: bold; color: #ffffff;")
            concept_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(concept_label)
        
        # Main insight text
        insight = learning_data.get('insight', '')
        if insight:
            insight_label = QLabel(insight)
            insight_label.setWordWrap(True)
            insight_label.setStyleSheet("color: #dddddd;")
            insight_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(insight_label)
        
        # Statistics or details if available
        if 'details' in learning_data:
            details = learning_data['details']
            details_label = QLabel(details)
            details_label.setStyleSheet("color: #bbbbbb; font-size: 9pt;")
            details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(details_label)

class LearningFeedPanel(QWidget):
    """Panel for displaying real-time learning feed"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.learning_items = []
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header label
        header_label = QLabel("Self-Learning Feed")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #ffffff;")
        header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(header_label)
        
        # Description
        description = QLabel("Real-time updates showing what the system is learning")
        description.setStyleSheet("color: #bbbbbb;")
        description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(description)
        
        # Scroll area for feed items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container for feed items
        self.feed_container = QWidget()
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.feed_layout.setSpacing(10)
        
        scroll_area.setWidget(self.feed_container)
        layout.addWidget(scroll_area)
        
        # Add empty state message
        self.empty_label = QLabel("No learning activities recorded yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; font-style: italic; padding: 20px;")
        self.empty_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.feed_layout.addWidget(self.empty_label)
    
    @pyqtSlot(dict)
    def add_learning_item(self, learning_data):
        """Add a new learning item to the feed"""
        # Hide empty state if this is the first item
        if self.empty_label.isVisible():
            self.empty_label.setVisible(False)
        
        # Create and add the item widget
        item = LearningFeedItem(learning_data)
        
        # Insert at the top of the feed (most recent first)
        self.feed_layout.insertWidget(0, item)
        self.learning_items.append(item)
        
        # Keep only the most recent 50 items to prevent the feed from getting too long
        if len(self.learning_items) > 50:
            old_item = self.learning_items.pop(0)
            self.feed_layout.removeWidget(old_item)
            old_item.deleteLater()
    
    def clear_feed(self):
        """Clear all items from the feed"""
        for item in self.learning_items:
            self.feed_layout.removeWidget(item)
            item.deleteLater()
        
        self.learning_items = []
        self.empty_label.setVisible(True) 