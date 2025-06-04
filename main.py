#!/usr/bin/env python3
import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThreadPool

from ui.main_window import MainWindow
from core.system_manager import SystemManager
from utils.config import load_config
from utils.logger import setup_logger

def main():
    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)
    logger.info("Starting GrokSAI Multi-Agent System")
    
    # Load configuration
    config = load_config()
    
    # Set up environment
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    ollama_model = os.environ.get('OLLAMA_MODEL', 'deepcoder:1.5b')
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    logger.info(f"Using Ollama model: {ollama_model}")
    
    # Create system manager (will initialize all agents)
    system_manager = SystemManager(config)
    system_manager.model_name = ollama_model
    
    # Start the GUI
    app = QApplication(sys.argv)
    window = MainWindow(system_manager)
    window.show()
    
    # Start the background system in a separate thread
    system_manager.start()
    
    # Execute app
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 