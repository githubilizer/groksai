import sys
import os
import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QLabel, QPushButton, QTextEdit, 
                            QListWidget, QListWidgetItem, QSplitter, 
                            QLineEdit, QComboBox, QGroupBox, QProgressBar,
                            QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon

from ui.agent_panel import AgentPanel
from ui.console_panel import ConsolePanel
from ui.status_panel import StatusPanel
from ui.prompt_panel import PromptPanel
from ui.learning_feed_panel import LearningFeedPanel
from ui.test_stats_panel import TestStatsPanel

class MainWindow(QMainWindow):
    def __init__(self, system_manager):
        super().__init__()
        
        self.system_manager = system_manager
        self.logger = logging.getLogger(__name__)
        
        # Set up the UI
        self.setWindowTitle("GrokSAI - Self-Improving Multi-Agent System")
        self.setMinimumSize(1200, 800)
        
        # Set up dark mode
        self.setup_dark_theme()
        
        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create UI components
        self.create_menu_bar()
        self.create_main_interface()
        self.create_status_bar()
        
        # Connect signals from system manager
        self.system_manager.status_update.connect(self.update_status)
        self.system_manager.log_message.connect(self.add_log_message)
        
        # Set up update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(1000)  # Update UI every second
        
        # Add example learning feed item for better UX
        self._add_example_learning_item()
        
        self.logger.info("Main window initialized")
    
    def setup_dark_theme(self):
        """Set up dark theme for the application"""
        app = self.style().parent()
        
        # Set up dark palette
        dark_palette = QPalette()
        
        # Base colors
        dark_color = QColor(45, 45, 45)
        disabled_color = QColor(127, 127, 127)
        dark_text = QColor(220, 220, 220)
        
        # Window and background
        dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
        dark_palette.setColor(QPalette.ColorRole.WindowText, dark_text)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
        
        # Text
        dark_palette.setColor(QPalette.ColorRole.Text, dark_text)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ButtonText, dark_text)
        
        # Button
        dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
        
        # Highlight
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        # Disabled
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_color)
        
        # Apply the palette
        app.setPalette(dark_palette)
        
        # Set stylesheet for fine-tuning
        self.setStyleSheet("""
        QToolTip { 
            color: #ffffff; 
            background-color: #2a82da; 
            border: 1px solid white; 
        }
        QTabWidget::pane { 
            border: 1px solid #444;
        }
        QTabBar::tab {
            background: #333; 
            color: #b1b1b1; 
            padding: 8px 15px;
            border: 1px solid #444;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected { 
            background: #444; 
            color: white;
        }
        QTabBar::tab:!selected { 
            margin-top: 2px; 
        }
        QListWidget, QTextEdit, QLineEdit {
            background-color: #2d2d2d;
            border: 1px solid #444;
        }
        QPushButton {
            background-color: #444;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 5px 15px;
            color: white;
        }
        QPushButton:hover {
            background-color: #555;
        }
        QPushButton:pressed {
            background-color: #2a82da;
        }
        QProgressBar {
            border: 1px solid #444;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #2a82da;
        }
        """)
    
    def create_menu_bar(self):
        """Create the main menu bar"""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Save Configuration", self.save_configuration)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        
        # System menu
        system_menu = menu_bar.addMenu("System")
        system_menu.addAction("Start System", self.start_system)
        system_menu.addAction("Stop System", self.stop_system)
        system_menu.addSeparator()
        system_menu.addAction("Reset Circuit Breakers", self.reset_circuit_breakers)
        system_menu.addAction("Create Backup", self.create_backup)
        
        # View menu
        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("System Status", self.show_system_status)
        view_menu.addAction("Memory Explorer", self.show_memory_explorer)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("About", self.show_about)
    
    def create_main_interface(self):
        """Create the main interface with tabs and panels"""
        # Main splitter dividing the window into top and bottom sections
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_layout.addWidget(self.main_splitter)
        
        # Top section with tabs
        self.tab_widget = QTabWidget()
        self.main_splitter.addWidget(self.tab_widget)
        
        # Create the dashboard tab
        self.create_dashboard_tab()
        
        # Create the agents tab
        self.create_agents_tab()
        
        # Create the memory tab
        self.create_memory_tab()
        
        # Create the console tab
        self.create_console_tab()
        
        # Bottom section with prompt panel
        self.prompt_panel = PromptPanel(self)
        self.main_splitter.addWidget(self.prompt_panel)
        
        # Set initial splitter sizes
        self.main_splitter.setSizes([600, 200])
    
    def create_dashboard_tab(self):
        """Create the dashboard tab with system overview"""
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_widget)
        
        # Control buttons at the top
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_system)
        control_layout.addWidget(self.start_button)
        
        # Pause/Resume button
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)  # Disabled until system is started
        control_layout.addWidget(self.pause_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_system)
        self.stop_button.setEnabled(False)  # Disabled until system is started
        control_layout.addWidget(self.stop_button)
        
        # Add spacer to push buttons to the left
        control_layout.addStretch()
        
        # Add control panel to dashboard
        dashboard_layout.addWidget(control_panel)
        
        # Create top section with status and test stats
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        
        # Status panel
        self.status_panel = StatusPanel()
        top_layout.addWidget(self.status_panel, 1)
        
        # Test statistics panel
        self.test_stats_panel = TestStatsPanel()
        top_layout.addWidget(self.test_stats_panel, 1)
        
        # Add top section to main layout
        dashboard_layout.addWidget(top_section, 1)
        
        # Create bottom section with learning feed
        bottom_section = QWidget()
        bottom_layout = QHBoxLayout(bottom_section)
        
        # Learning feed panel
        self.learning_feed_panel = LearningFeedPanel()
        bottom_layout.addWidget(self.learning_feed_panel, 1)
        
        # Add bottom section to main layout
        dashboard_layout.addWidget(bottom_section, 1)
        
        # Connect signals
        self.system_manager.learning_update.connect(self.learning_feed_panel.add_learning_item)
        self.system_manager.llm_output_update.connect(self.test_stats_panel.update_llm_output)
        self.system_manager.test_update.connect(self.test_stats_panel.update_cycle_info)
        self.system_manager.test_fixed_update.connect(self._handle_test_fixed_update)
        
        # Add the tab
        self.tab_widget.addTab(dashboard_widget, "Dashboard")
    
    def create_agents_tab(self):
        """Create the agents tab with panels for each agent"""
        agents_widget = QWidget()
        agents_layout = QVBoxLayout(agents_widget)
        
        # Create a scroll area for the agents
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Create agent panels
        self.agent_panels = {}
        
        for agent in self.system_manager.agents:
            agent_panel = AgentPanel(agent)
            self.agent_panels[agent.name] = agent_panel
            scroll_layout.addWidget(agent_panel)
        
        # Add some spacing between agent panels
        scroll_layout.addStretch()
        
        # Set the scroll content and add to layout
        scroll_area.setWidget(scroll_content)
        agents_layout.addWidget(scroll_area)
        
        # Add the agents widget to the tab
        self.tab_widget.addTab(agents_widget, "Agents")
    
    def create_memory_tab(self):
        """Create the memory tab with knowledge base explorer"""
        memory_widget = QWidget()
        memory_layout = QHBoxLayout(memory_widget)
        
        # Left panel: Categories
        categories_group = QGroupBox("Knowledge Categories")
        categories_layout = QVBoxLayout(categories_group)
        
        self.categories_list = QListWidget()
        categories_layout.addWidget(self.categories_list)
        
        # Connect selection change
        self.categories_list.currentItemChanged.connect(self.on_category_selected)
        
        # Right panel: Content
        content_group = QGroupBox("Knowledge Content")
        content_layout = QVBoxLayout(content_group)
        
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        content_layout.addWidget(self.content_text)
        
        # Add panels to layout
        memory_layout.addWidget(categories_group, 1)
        memory_layout.addWidget(content_group, 2)
        
        # Add the memory widget to the tab
        self.tab_widget.addTab(memory_widget, "Memory")
    
    def create_console_tab(self):
        """Create the console tab with log output"""
        self.console_panel = ConsolePanel(self)
        self.tab_widget.addTab(self.console_panel, "Console")
    
    def create_status_bar(self):
        """Create the status bar at the bottom of the window"""
        self.status_bar = self.statusBar()
        
        # Status label
        self.status_label = QLabel("System: Initializing")
        self.status_bar.addPermanentWidget(self.status_label)
        
        # Cycle counter
        self.cycle_label = QLabel("Cycle: 0")
        self.status_bar.addPermanentWidget(self.cycle_label)
    
    @pyqtSlot(str)
    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_label.setText(message)
        self.console_panel.add_message(message)
    
    @pyqtSlot(str)
    def add_log_message(self, message):
        """Add a log message to the console"""
        self.console_panel.add_message(message)
    
    def update_ui(self):
        """Update UI components with latest system information"""
        try:
            # Get latest system status
            system_status = self.system_manager.get_system_status()
            
            # Update button states based on system status
            if hasattr(self, 'start_button') and hasattr(self, 'pause_button') and hasattr(self, 'stop_button'):
                is_running = system_status.get('running', False)
                is_paused = system_status.get('paused', False)
                
                self.start_button.setEnabled(not is_running)
                self.pause_button.setEnabled(is_running)
                self.stop_button.setEnabled(is_running)
                
                if is_paused:
                    self.pause_button.setText("Resume")
                else:
                    self.pause_button.setText("Pause")
            
            # Update status panel
            self.status_panel.update_status(system_status)
            
            # Update test stats panel
            if hasattr(self, 'test_stats_panel'):
                self.test_stats_panel.update_stats(system_status.get('test_stats', {}))
                
                # Update cycle info if available
                cycle_info = {
                    'cycle_count': system_status.get('cycle_count', 0),
                    'last_test': system_status.get('last_test'),
                    'result': system_status.get('last_test_result')
                }
                self.test_stats_panel.update_cycle_info(cycle_info)
                
                # Update LLM output if available
                if system_status.get('recent_llm'):
                    self.test_stats_panel.update_llm_output(system_status.get('recent_llm'))
            
            # Update CPU, memory, and GPU usage
            import random
            
            # In a real implementation, you would use a library like psutil and gputil
            # to get actual system usage metrics
            try:
                # Try to get GPU usage if available
                import gputil
                gpus = gputil.getGPUs()
                if gpus:
                    # Use the first GPU's utilization
                    gpu_usage = gpus[0].load * 100
                    self.status_panel.update_gpu_usage(gpu_usage)
                else:
                    # No GPU found or accessible
                    self.status_panel.update_gpu_usage(0)
            except (ImportError, Exception):
                # gputil not installed or other error, use mock data
                self.status_panel.update_gpu_usage(random.randint(10, 80))
            
            # CPU and memory usage (you should replace with actual metrics in production)
            self.status_panel.update_cpu_usage(random.randint(10, 60))
            self.status_panel.update_memory_usage(random.randint(20, 70))
            
            # Update agent panels if they exist
            if hasattr(self, 'agent_panels'):
                for agent_name, panel in self.agent_panels.items():
                    agent_status = system_status.get('agents', {}).get(agent_name, {})
                    panel.update_status(agent_status)
            
            # Update memory categories if in memory tab
            if self.tab_widget.currentIndex() == 2:  # Memory tab
                self.update_memory_categories()
                
        except Exception as e:
            self.logger.error(f"Error updating UI: {str(e)}", exc_info=True)
    
    def update_memory_categories(self):
        """Update the memory categories list"""
        try:
            # Get all knowledge categories
            knowledge = self.system_manager.memory.get_knowledge()
            
            # Only update if there's new information
            current_items = set()
            for i in range(self.categories_list.count()):
                current_items.add(self.categories_list.item(i).text())
            
            new_items = set(knowledge.get("concepts", {}).keys())
            
            # Add new items
            for item in new_items - current_items:
                self.categories_list.addItem(item)
            
            # Remove old items
            for i in reversed(range(self.categories_list.count())):
                if self.categories_list.item(i).text() not in new_items:
                    self.categories_list.takeItem(i)
        except Exception as e:
            self.logger.error(f"Error updating memory categories: {e}")
    
    def on_category_selected(self, current, previous):
        """Handle selection of a memory category"""
        if not current:
            return
            
        category = current.text()
        
        try:
            # Get the knowledge item
            knowledge_item = self.system_manager.memory.get_knowledge(category)
            
            if knowledge_item:
                # Format the content as pretty JSON
                import json
                content = json.dumps(knowledge_item, indent=2)
                self.content_text.setText(content)
            else:
                self.content_text.setText("No content available for this category.")
        except Exception as e:
            self.logger.error(f"Error displaying category content: {e}")
            self.content_text.setText(f"Error: {str(e)}")
    
    def save_configuration(self):
        """Save the current configuration"""
        from utils.config import save_config
        if save_config(self.system_manager.config):
            self.update_status("Configuration saved successfully")
        else:
            self.update_status("Error saving configuration")
    
    def start_system(self):
        """Start the system"""
        if not self.system_manager.running:
            self.system_manager.start()
            self.update_status("System started")
            
            # Update button states
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
    
    def toggle_pause(self):
        """Toggle between pause and resume"""
        if not self.system_manager.running:
            return
            
        if self.system_manager.paused:
            # System is paused, resume it
            self.system_manager.resume()
            self.pause_button.setText("Pause")
            self.update_status("System resumed")
        else:
            # System is running, pause it
            self.system_manager.pause()
            self.pause_button.setText("Resume")
            self.update_status("System paused")
    
    def stop_system(self):
        """Stop the system"""
        if self.system_manager.running:
            self.system_manager.stop()
            self.update_status("System stopped")
            
            # Update button states
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.pause_button.setText("Pause")  # Reset text
            self.stop_button.setEnabled(False)
    
    def create_backup(self):
        """Create a backup of the memory"""
        try:
            backup_dir = self.system_manager.memory.create_backup()
            if backup_dir:
                self.update_status(f"Backup created at {backup_dir}")
            else:
                self.update_status("Failed to create backup")
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            self.update_status(f"Error creating backup: {str(e)}")
    
    def show_system_status(self):
        """Show detailed system status"""
        self.tab_widget.setCurrentIndex(0)  # Switch to dashboard tab
    
    def show_memory_explorer(self):
        """Show memory explorer"""
        self.tab_widget.setCurrentIndex(2)  # Switch to memory tab
    
    def show_about(self):
        """Show about dialog"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About GrokSAI", 
                         "GrokSAI - Self-Improving Multi-Agent System\n\n"
                         "A system designed to autonomously generate tests, "
                         "learn from results, and improve over time.\n\n"
                         "Version: 1.0.0\n"
                         "Using model: " + self.system_manager.model_name)
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.system_manager.running:
            self.system_manager.stop()
            
        # Stop UI update timer
        self.update_timer.stop()
        
        event.accept()
    
    def _add_example_learning_item(self):
        """Add an example learning item to the feed to demonstrate functionality"""
        import datetime
        
        example_item = {
            "type": "welcome_learning",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "concept": "system_initialization",
            "insight": "Welcome to GrokSAI! This panel will show real-time learning updates as the system processes tests."
        }
        
        # Only add if we have a learning feed panel
        if hasattr(self, 'learning_feed_panel'):
            self.learning_feed_panel.add_learning_item(example_item)

    def _handle_test_fixed_update(self, test_event):
        """Handle a fixed test event"""
        import datetime
        
        # Extract information
        test_id = test_event.get("test_id", "unknown")
        test_name = test_event.get("test_name", f"Test {test_id}")
        test_type = test_event.get("test_type", "unknown")
        failure_reason = test_event.get("failure_reason", "Unknown failure")
        fix_type = test_event.get("fix_type", "unknown")
        
        # Format as a learning event
        learning_item = {
            "type": "fix_learning",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "concept": "test_fixing",
            "insight": f"Successfully fixed {test_type} test: {test_name}",
            "details": f"Fixed using {fix_type} approach. Original failure: {failure_reason[:100]}..."
        }
        
        # Add to learning feed
        self.learning_feed_panel.add_learning_item(learning_item)

    def reset_circuit_breakers(self):
        """Reset all circuit breakers in the system"""
        if self.system_manager:
            self.system_manager.reset_circuit_breakers()
            self.add_log_message("Circuit breakers manually reset. Agents will retry operations.")
            self.status_panel.add_status_message("Circuit breakers reset") 