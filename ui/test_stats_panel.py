from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QProgressBar, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QColor

class TestStatsPanel(QWidget):
    """Panel for displaying test statistics and current test information"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header_label = QLabel("Test Statistics")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #ffffff;")
        header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(header_label)
        
        # Test counters frame
        counters_frame = QFrame()
        counters_frame.setFrameShape(QFrame.Shape.StyledPanel)
        counters_layout = QVBoxLayout(counters_frame)
        
        # Tests Run
        self.tests_run_label = QLabel("Tests Run: 0")
        self.tests_run_label.setFont(QFont("Arial", 10))
        self.tests_run_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tests_run_label.setToolTip("Total number of tests executed by the system")
        counters_layout.addWidget(self.tests_run_label)
        
        # Tests Passed
        self.tests_passed_label = QLabel("Tests Passed: 0")
        self.tests_passed_label.setStyleSheet("color: #55ff55;")
        self.tests_passed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tests_passed_label.setToolTip("Number of tests that passed successfully on their first attempt")
        counters_layout.addWidget(self.tests_passed_label)
        
        # Tests Failed
        self.tests_failed_label = QLabel("Tests Failed: 0")
        self.tests_failed_label.setStyleSheet("color: #ff5555;")
        self.tests_failed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tests_failed_label.setToolTip("Number of tests that failed execution")
        counters_layout.addWidget(self.tests_failed_label)
        
        # Tests Fixed
        self.tests_fixed_label = QLabel("Tests Failed then Later Fixed: 0")
        self.tests_fixed_label.setStyleSheet("color: #5599ff;") # Blue color for fixed tests
        self.tests_fixed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tests_fixed_label.setToolTip("Number of tests that initially failed but were successfully fixed by the system")
        counters_layout.addWidget(self.tests_fixed_label)
        
        # Pass Rate
        pass_rate_layout = QHBoxLayout()
        pass_rate_label = QLabel("Pass Rate:")
        pass_rate_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pass_rate_layout.addWidget(pass_rate_label)
        
        self.pass_rate_bar = QProgressBar()
        self.pass_rate_bar.setRange(0, 100)
        self.pass_rate_bar.setValue(0)
        self.pass_rate_bar.setTextVisible(True)
        self.pass_rate_bar.setFormat("%p%")
        pass_rate_layout.addWidget(self.pass_rate_bar)
        
        counters_layout.addLayout(pass_rate_layout)
        layout.addWidget(counters_frame)
        
        # Current Cycle Information
        cycle_frame = QFrame()
        cycle_frame.setFrameShape(QFrame.Shape.StyledPanel)
        cycle_layout = QVBoxLayout(cycle_frame)
        
        self.current_cycle_label = QLabel("Current Cycle: 0")
        self.current_cycle_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.current_cycle_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cycle_layout.addWidget(self.current_cycle_label)
        
        self.current_test_label = QLabel("Last Test: None")
        self.current_test_label.setWordWrap(True)
        self.current_test_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cycle_layout.addWidget(self.current_test_label)
        
        self.test_result_label = QLabel("Result: N/A")
        self.test_result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cycle_layout.addWidget(self.test_result_label)
        
        layout.addWidget(cycle_frame)
        
        # Recent LLM Output
        llm_frame = QFrame()
        llm_frame.setFrameShape(QFrame.Shape.StyledPanel)
        llm_layout = QVBoxLayout(llm_frame)
        
        llm_header = QLabel("Recent LLM Output")
        llm_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        llm_header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        llm_layout.addWidget(llm_header)
        
        # Scroll area for LLM output
        llm_scroll = QScrollArea()
        llm_scroll.setWidgetResizable(True)
        llm_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.llm_output = QLabel("No recent LLM output")
        self.llm_output.setWordWrap(True)
        self.llm_output.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.llm_output.setStyleSheet("background-color: #2d2d2d; padding: 5px; border-radius: 3px;")
        llm_scroll.setWidget(self.llm_output)
        llm_layout.addWidget(llm_scroll)
        
        layout.addWidget(llm_frame)
        
        # Add stretch to push everything up
        layout.addStretch()
    
    def update_stats(self, stats):
        """Update test statistics"""
        if 'tests_run' in stats:
            self.tests_run_label.setText(f"Tests Run: {stats['tests_run']}")
        
        if 'tests_passed' in stats:
            self.tests_passed_label.setText(f"Tests Passed: {stats['tests_passed']}")
        
        if 'tests_failed' in stats:
            self.tests_failed_label.setText(f"Tests Failed: {stats['tests_failed']}")
            
        if 'tests_fixed' in stats:
            session_fixes = stats['tests_fixed']
            total_fixes = stats.get('total_tests_fixed', session_fixes)
            
            if total_fixes > session_fixes:
                self.tests_fixed_label.setText(f"Tests Failed then Later Fixed: {session_fixes} (Total: {total_fixes})")
            else:
                self.tests_fixed_label.setText(f"Tests Failed then Later Fixed: {session_fixes}")
        
        # Calculate pass rate
        tests_run = stats.get('tests_run', 0)
        tests_passed = stats.get('tests_passed', 0)
        
        if tests_run > 0:
            pass_rate = int((tests_passed / tests_run) * 100)
            self.pass_rate_bar.setValue(pass_rate)
            
            # Set color based on pass rate
            if pass_rate >= 80:
                self.pass_rate_bar.setStyleSheet("QProgressBar::chunk { background-color: #55ff55; }")
            elif pass_rate >= 50:
                self.pass_rate_bar.setStyleSheet("QProgressBar::chunk { background-color: #ffaa00; }")
            else:
                self.pass_rate_bar.setStyleSheet("QProgressBar::chunk { background-color: #ff5555; }")
    
    def update_cycle_info(self, cycle_info):
        """Update current cycle information"""
        if 'cycle_count' in cycle_info:
            self.current_cycle_label.setText(f"Current Cycle: {cycle_info['cycle_count']}")
        
        if 'last_test' in cycle_info and cycle_info['last_test']:
            test = cycle_info['last_test']
            test_id = test.get('id', 'unknown')
            test_name = test.get('name', f'Test {test_id}')
            test_type = test.get('type', 'unknown')
            
            self.current_test_label.setText(f"Last Test: {test_name} (ID: {test_id}, Type: {test_type})")
            
            if 'result' in cycle_info and cycle_info['result']:
                result = cycle_info['result']
                passed = result.get('passed', False)
                
                if passed:
                    self.test_result_label.setText("Result: Passed")
                    self.test_result_label.setStyleSheet("color: #55ff55;")
                else:
                    failure = result.get('failure_reason', 'Unknown failure')
                    self.test_result_label.setText(f"Result: Failed - {failure}")
                    self.test_result_label.setStyleSheet("color: #ff5555;")
    
    def update_llm_output(self, output):
        """Update the LLM output display"""
        if output:
            # Truncate if too long
            if len(output) > 500:
                output = output[:497] + "..."
            
            self.llm_output.setText(output)
        else:
            self.llm_output.setText("No recent LLM output") 