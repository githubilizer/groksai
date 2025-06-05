import os
import json
import logging
import time
import shutil
from datetime import datetime

class MemoryManager:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.memory_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
        
        # Create memory directories if they don't exist
        self.ensure_memory_dirs()
        
        # Initialize memory caches
        self.action_logs = []
        self.knowledge_base = self._load_knowledge_base()
        self.test_history = self._load_test_history()
        
        self.logger.info("Memory manager initialized")
    
    def ensure_memory_dirs(self):
        """Ensure all required memory directories exist"""
        dirs = [
            self.memory_dir,
            os.path.join(self.memory_dir, "actions"),
            os.path.join(self.memory_dir, "knowledge"),
            os.path.join(self.memory_dir, "tests"),
            os.path.join(self.memory_dir, "cycles"),
            os.path.join(self.memory_dir, "backups")
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                self.logger.info(f"Created memory directory: {dir_path}")
    
    def _load_knowledge_base(self):
        """Load the knowledge base from disk"""
        kb_path = os.path.join(self.memory_dir, "knowledge", "knowledge_base.json")
        if os.path.exists(kb_path):
            try:
                with open(kb_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading knowledge base: {e}")
                return {"concepts": {}, "rules": [], "examples": []}
        else:
            return {"concepts": {}, "rules": [], "examples": []}
    
    def _load_test_history(self):
        """Load the test history from disk"""
        history_path = os.path.join(self.memory_dir, "tests", "test_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    data = json.load(f)
                    if "fixed_tests" not in data:
                        data["fixed_tests"] = {}
                    return data
            except Exception as e:
                self.logger.error(f"Error loading test history: {e}")
                return {"tests": [], "results": {}, "fixed_tests": {}}
        else:
            return {"tests": [], "results": {}, "fixed_tests": {}}
    
    def log_agent_action(self, action_log):
        """Log an agent action"""
        self.action_logs.append(action_log)
        
        # Save to disk periodically (every 10 actions)
        if len(self.action_logs) >= 10:
            self._save_action_logs()
    
    def _save_action_logs(self):
        """Save accumulated action logs to disk"""
        if not self.action_logs:
            return
            
        timestamp = int(time.time())
        log_path = os.path.join(self.memory_dir, "actions", f"actions_{timestamp}.json")
        
        try:
            with open(log_path, 'w') as f:
                json.dump(self.action_logs, f, indent=2)
            self.logger.debug(f"Saved {len(self.action_logs)} action logs to {log_path}")
            self.action_logs = []
        except Exception as e:
            self.logger.error(f"Error saving action logs: {e}")
    
    def save_knowledge(self, concept, data):
        """Save a piece of knowledge to the knowledge base"""
        self.knowledge_base["concepts"][concept] = data
        self._save_knowledge_base()
        
        self.logger.info(f"Saved knowledge: {concept}")
        return True
    
    def get_knowledge(self, concept=None):
        """Retrieve knowledge from the knowledge base"""
        if concept:
            return self.knowledge_base["concepts"].get(concept, None)
        return self.knowledge_base
    
    def _save_knowledge_base(self):
        """Save the knowledge base to disk"""
        kb_path = os.path.join(self.memory_dir, "knowledge", "knowledge_base.json")
        try:
            with open(kb_path, 'w') as f:
                json.dump(self.knowledge_base, f, indent=2)
            self.logger.debug("Saved knowledge base")
            return True
        except Exception as e:
            self.logger.error(f"Error saving knowledge base: {e}")
            return False
    
    def save_test(self, test_data):
        """Save a test to the test history"""
        test_id = len(self.test_history["tests"])
        test_data["id"] = test_id
        test_data["created"] = time.time()
        
        self.test_history["tests"].append(test_data)
        self._save_test_history()
        
        return test_id
    
    def save_test_result(self, test_id, result):
        """Save a test result to the test history"""
        if str(test_id) not in self.test_history["results"]:
            self.test_history["results"][str(test_id)] = []
            
        result["timestamp"] = time.time()
        self.test_history["results"][str(test_id)].append(result)
        self._save_test_history()

        return True

    def update_test(self, test_id, updates):
        """Update an existing test entry with new data"""
        try:
            if test_id < len(self.test_history["tests"]):
                self.test_history["tests"][test_id].update(updates)
                self._save_test_history()
                return True
        except Exception as e:
            self.logger.error(f"Error updating test {test_id}: {e}")
        return False

    def record_fixed_test(self, old_id, new_id):
        """Record that a test has been replaced by a fixed version"""
        try:
            if "fixed_tests" not in self.test_history:
                self.test_history["fixed_tests"] = {}
            self.test_history["fixed_tests"][str(old_id)] = new_id
            self._save_test_history()
            return True
        except Exception as e:
            self.logger.error(f"Error recording fixed test mapping: {e}")
        return False
    
    def _save_test_history(self):
        """Save the test history to disk"""
        history_path = os.path.join(self.memory_dir, "tests", "test_history.json")
        try:
            if "fixed_tests" not in self.test_history:
                self.test_history["fixed_tests"] = {}
            with open(history_path, 'w') as f:
                json.dump(self.test_history, f, indent=2)
            self.logger.debug("Saved test history")
            return True
        except Exception as e:
            self.logger.error(f"Error saving test history: {e}")
            return False
    
    def save_cycle_results(self, cycle_number, results):
        """Save results from a complete system cycle"""
        cycle_path = os.path.join(self.memory_dir, "cycles", f"cycle_{cycle_number}.json")
        
        results["timestamp"] = time.time()
        results["cycle"] = cycle_number
        
        try:
            with open(cycle_path, 'w') as f:
                json.dump(results, f, indent=2)
            self.logger.info(f"Saved results for cycle {cycle_number}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving cycle results: {e}")
            return False
    
    def get_cycle_count(self):
        """Get the current cycle count based on files in the cycles directory"""
        cycles_dir = os.path.join(self.memory_dir, "cycles")
        if not os.path.exists(cycles_dir):
            return 0
            
        cycle_files = [f for f in os.listdir(cycles_dir) if f.startswith("cycle_") and f.endswith(".json")]
        if not cycle_files:
            return 0
            
        try:
            cycle_numbers = [int(f.split("_")[1].split(".")[0]) for f in cycle_files]
            return max(cycle_numbers)
        except Exception:
            return len(cycle_files)
    
    def create_backup(self):
        """Create a backup of the entire memory directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.memory_dir, "backups", f"backup_{timestamp}")
        
        try:
            # Ensure all logs are saved
            self._save_action_logs()
            self._save_knowledge_base()
            self._save_test_history()
            
            # Create the backup directory
            os.makedirs(backup_dir, exist_ok=True)
            
            # Copy all files except backups
            for item in os.listdir(self.memory_dir):
                if item != "backups":
                    src = os.path.join(self.memory_dir, item)
                    dst = os.path.join(backup_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            
            self.logger.info(f"Created memory backup at {backup_dir}")
            return backup_dir
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return None

    def reset_training_data(self):
        """Wipe all learned knowledge and test history"""
        try:
            # Reset in-memory structures
            self.knowledge_base = {"concepts": {}, "rules": [], "examples": []}
            self.test_history = {"tests": [], "results": {}, "fixed_tests": {}}

            # Remove action logs
            actions_dir = os.path.join(self.memory_dir, "actions")
            for f in os.listdir(actions_dir):
                try:
                    os.remove(os.path.join(actions_dir, f))
                except Exception:
                    pass

            # Remove cycle result files
            cycles_dir = os.path.join(self.memory_dir, "cycles")
            for f in os.listdir(cycles_dir):
                if f.startswith("cycle_") and f.endswith(".json"):
                    try:
                        os.remove(os.path.join(cycles_dir, f))
                    except Exception:
                        pass

            # Save cleared structures
            self._save_knowledge_base()
            self._save_test_history()

            # Reset system state counters
            state_path = os.path.join(self.memory_dir, "system_state.json")
            state = {
                "last_run": None,
                "current_complexity_level": 1,
                "total_tests_generated": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "total_fixes_attempted": 0,
                "total_fixes_succeeded": 0,
            }
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)

            self.logger.info("Training data reset")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting training data: {e}")
            return False
