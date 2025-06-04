import os
import json
import logging
from dotenv import load_dotenv

def load_config():
    """Load system configuration from multiple sources and provide defaults"""
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Default configuration
    default_config = {
        "app_name": "GrokSAI",
        "version": "0.1.0",
        "model_name": "deepcoder:1.5b",  # Default model name
        "cycle_delay": 5,  # Seconds between cycles
        "log_level": "INFO",
        "memory_dir": os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory"),
        "backup_frequency": 24,  # Hours between automatic backups
        "ui": {
            "theme": "dark",
            "refresh_rate": 1  # Seconds between UI updates
        },
        "agents": {
            "test_generator": {
                "tests_per_cycle": 3,
                "initial_complexity": "beginner"
            },
            "monitor": {
                "monitoring_interval": 60,
                "cpu_threshold": 90.0,
                "memory_threshold": 90.0,
                "disk_threshold": 90.0
            }
        },
        "memory": {
            "persistence_dir": "memory",
            "knowledge_file": "knowledge.json",
            "test_history_file": "test_history.json"
        }
    }
    
    # Try to load from config file
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    file_config = {}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                logging.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logging.error(f"Error loading config file: {e}")
    
    # Merge configurations (file config overrides defaults)
    config = {**default_config, **file_config}
    
    # Override with environment variables if set
    if os.environ.get("GROKSAI_MODEL_NAME"):
        config["model_name"] = os.environ.get("GROKSAI_MODEL_NAME")
        
    if os.environ.get("GROKSAI_CYCLE_DELAY"):
        try:
            config["cycle_delay"] = int(os.environ.get("GROKSAI_CYCLE_DELAY"))
        except ValueError:
            pass
            
    if os.environ.get("GROKSAI_LOG_LEVEL"):
        config["log_level"] = os.environ.get("GROKSAI_LOG_LEVEL")
        
    if os.environ.get("GROKSAI_MEMORY_DIR"):
        config["memory_dir"] = os.environ.get("GROKSAI_MEMORY_DIR")
    
    return config

def save_config(config):
    """Save the current configuration to the config file"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logging.info(f"Saved configuration to {config_path}")
        return True
    except Exception as e:
        logging.error(f"Error saving config file: {e}")
        return False 