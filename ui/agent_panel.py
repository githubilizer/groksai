import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QProgressBar, QPushButton, QGroupBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

class AgentPanel(QGroupBox):
    def __init__(self, agent):
        super().__init__(agent.name)
        
        self.agent = agent
        self.logger = logging.getLogger(__name__)
        
        # Set up the layout
        self.main_layout = QVBoxLayout(self)
        
        # Create the content
        self.create_content()
    
    def create_content(self):
        """Create the content of the agent panel"""
        # Status section
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        
        # Status label
        self.status_label = QLabel("Status: Initializing")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        status_layout.addWidget(self.status_label)
        
        # Last action time
        self.action_time_label = QLabel("Last action: Never")
        status_layout.addWidget(self.action_time_label)
        
        # Add to main layout
        self.main_layout.addWidget(status_frame)
        
        # Create a details section with additional info about the agent
        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)
        
        # Description
        self.description_label = QLabel(self.get_agent_description())
        self.description_label.setWordWrap(True)
        details_layout.addWidget(self.description_label)
        
        # Stats (specific to each agent type)
        self.stats_label = QLabel("No stats available yet")
        self.stats_label.setWordWrap(True)
        details_layout.addWidget(self.stats_label)
        
        # Add to main layout
        self.main_layout.addWidget(details_frame)
        
        # Controls section
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        
        # Details button
        details_btn = QPushButton("View Details")
        details_btn.clicked.connect(self.show_details)
        controls_layout.addWidget(details_btn)
        
        # Add to main layout
        self.main_layout.addWidget(controls_frame)
    
    def update_status(self, status):
        """Update the status display with current agent status"""
        try:
            agent_status = status.get("status", "unknown")
            self.status_label.setText(f"Status: {agent_status}")
            
            # Update last action time
            last_action = status.get("last_action", 0)
            if last_action > 0:
                self.action_time_label.setText(f"Last action: {last_action:.1f}s ago")
            else:
                self.action_time_label.setText("Last action: Never")
            
            # Update stats based on agent type
            self.update_agent_stats()
            
        except Exception as e:
            self.logger.error(f"Error updating agent panel: {e}")
    
    def update_agent_stats(self):
        """Update the agent-specific statistics"""
        try:
            agent_name = self.agent.name
            stats_text = ""
            
            if agent_name == "TestGenerator":
                stats_text = f"Tests Generated: {self.agent.tests_generated}\n"
                stats_text += f"Current Complexity: {self.agent.current_complexity}\n"
                stats_text += f"Success Rate: {self.agent.success_rate:.1%}"
                
            elif agent_name == "Tester":
                stats_text = f"Tests Run: {self.agent.tests_run}\n"
                stats_text += f"Tests Passed: {self.agent.tests_passed}\n"
                stats_text += f"Tests Failed: {self.agent.tests_failed}"
                
            elif agent_name == "Fixer":
                stats_text = f"Fixes Attempted: {self.agent.fixes_attempted}\n"
                stats_text += f"Fixes Successful: {self.agent.fixes_successful}\n"
                
                if self.agent.fixes_attempted > 0:
                    success_rate = self.agent.fixes_successful / self.agent.fixes_attempted
                    stats_text += f"Success Rate: {success_rate:.1%}"
                
            elif agent_name == "Learner":
                stats_text = f"Learning Sessions: {self.agent.learning_sessions}\n"
                stats_text += f"Concepts Learned: {self.agent.concepts_learned}\n"
                stats_text += f"Rules Discovered: {self.agent.rules_discovered}"
                
            elif agent_name == "Monitor":
                stats_text = f"Checks Performed: {self.agent.checks_performed}\n"
                stats_text += f"Alerts Raised: {self.agent.alerts_raised}\n"
                stats_text += f"System Uptime: {self.format_uptime(self.agent.system_uptime)}"
                
            elif agent_name == "UserInterface":
                stats_text = f"User Interactions: {self.agent.interactions}\n"
                stats_text += f"Pending Requests: {self.agent.pending_requests.qsize()}"
            
            if stats_text:
                self.stats_label.setText(stats_text)
            
        except Exception as e:
            self.logger.error(f"Error updating agent stats: {e}")
    
    def format_uptime(self, seconds):
        """Format uptime in seconds to a readable string"""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_agent_description(self):
        """Get a description of the agent based on its type"""
        agent_name = self.agent.name
        
        descriptions = {
            "TestGenerator": "Creates increasingly complex tests for the system to solve.",
            "Tester": "Runs tests and evaluates their results against success criteria.",
            "Fixer": "Autonomously resolves test failures by modifying code or configurations.",
            "Learner": "Updates the system's knowledge based on test outcomes and fixes.",
            "Monitor": "Ensures system health by continuously checking performance.",
            "UserInterface": "Handles user prompts and interactions with the system."
        }
        
        return descriptions.get(agent_name, "Agent with unknown function")
    
    def show_details(self):
        """Show detailed information about the agent"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self.agent.name} Details")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Create text area for details
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        
        # Get detailed information about the agent
        try:
            # Format agent details
            details = f"Agent: {self.agent.name}\n"
            details += f"Status: {self.agent.status}\n"
            details += f"Last Action Time: {self.agent.last_action_time}\n\n"
            
            # Add agent-specific details
            if hasattr(self.agent, 'get_detailed_status'):
                agent_details = self.agent.get_detailed_status()
                import json
                details += json.dumps(agent_details, indent=2)
            else:
                # Get all readable attributes
                details += "Attributes:\n"
                for attr in dir(self.agent):
                    if not attr.startswith('_') and not callable(getattr(self.agent, attr)):
                        try:
                            value = getattr(self.agent, attr)
                            if not isinstance(value, (dict, list)) or attr in ['patterns', 'known_patterns']:
                                details += f"  {attr}: {value}\n"
                        except:
                            pass
            
            details_text.setText(details)
            
        except Exception as e:
            details_text.setText(f"Error getting agent details: {str(e)}")
        
        layout.addWidget(details_text)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec() 