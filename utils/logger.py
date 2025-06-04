import os
import logging
import sys
from datetime import datetime

def setup_logger(log_level=None, log_file=None):
    """Set up the logging system for the application"""
    # Get the root logger
    logger = logging.getLogger()
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Determine log level
    if log_level is None:
        log_level = os.environ.get("GROKSAI_LOG_LEVEL", "INFO")
        
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        
    logger.setLevel(numeric_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add console handler to logger
    logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file is None:
        # Default log file in logs directory with timestamp
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(logs_dir, f"groksai_{timestamp}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized at level {log_level}")
    logging.info(f"Log file: {log_file}")
    
    return logger 