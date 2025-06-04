import os
import logging
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

from agents.test_generator import TestGenerator
from agents.tester import Tester
from agents.fixer import Fixer
from agents.learner import Learner
from agents.monitor import Monitor
from agents.user_interface import UserInterface

from memory.memory_manager import MemoryManager

class SystemManager(QObject):
    status_update = pyqtSignal(str)
    log_message = pyqtSignal(str)
    learning_update = pyqtSignal(dict)
    llm_output_update = pyqtSignal(str) 
    test_update = pyqtSignal(dict)
    test_fixed_update = pyqtSignal(dict)  # New signal for fixed tests
    
    def __init__(self, config):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.running = False
        self.paused = False
        self.thread = None
        self.model_name = 'qwen3:30b'
        
        # Track recent LLM outputs and test results
        self.recent_llm_outputs = []
        self.max_llm_outputs = 10
        self.last_test = None
        self.last_test_result = None
        
        # Error tracking and self-healing
        self.error_history = {}  # Track recurring errors
        self.recovery_strategies = {}  # Store successful recovery strategies
        self.last_error_time = time.time()
        self.consecutive_error_cycles = 0
        self.max_error_cycles = 10  # Max consecutive error cycles before taking action
        self.health_check_failures = 0  # Track consecutive health check failures
        
        # Initialize memory system
        self.memory = MemoryManager(config)
        
        # Initialize agents
        self.test_generator = TestGenerator(self, self.memory, self.model_name)
        self.tester = Tester(self, self.memory, self.model_name)
        self.fixer = Fixer(self, self.memory, self.model_name)
        self.learner = Learner(self, self.memory, self.model_name)
        self.monitor = Monitor(self, self.memory, self.model_name)
        self.user_interface = UserInterface(self, self.memory, self.model_name)
        
        self.agents = [
            self.test_generator,
            self.tester,
            self.fixer,
            self.learner,
            self.monitor,
            self.user_interface
        ]
        
        # Fault tolerance settings
        self.max_agent_failures = 3  # Maximum consecutive failures before circuit breaker trips
        self.agent_failure_counts = {agent.name: 0 for agent in self.agents}
        self.circuit_breakers = {agent.name: False for agent in self.agents}
        self.circuit_breaker_reset_time = 300  # 5 minutes to reset a circuit breaker
        self.last_failure_time = {agent.name: 0 for agent in self.agents}
        
        # Track fixed tests over time (persists between app restarts)
        self.fixed_tests_count = 0
        self._load_fixed_tests_stats()
        
        # Load previous error history and recovery strategies
        self._load_error_history()
        
        # Connect signal to increment fixed tests counter
        self.test_fixed_update.connect(self._on_test_fixed)
        
        # Intercept each agent's LLM calls to track outputs
        for agent in self.agents:
            agent.on_llm_response = self._on_llm_response
        
        # Testing configuration
        self.test_batch_size = 1  # Generate and test one test at a time
        
        self.logger.info("System manager initialized with all agents")
    
    def _on_llm_response(self, agent_name, prompt, response):
        """Callback for LLM responses"""
        llm_data = {
            'agent': agent_name,
            'timestamp': time.time(),
            'prompt': prompt,
            'response': response
        }
        
        # Add to recent outputs
        self.recent_llm_outputs.append(llm_data)
        
        # Keep only the most recent outputs
        if len(self.recent_llm_outputs) > self.max_llm_outputs:
            self.recent_llm_outputs = self.recent_llm_outputs[-self.max_llm_outputs:]
        
        # Emit signal with the response
        self.llm_output_update.emit(f"Agent: {agent_name}\nPrompt: {prompt[:100]}...\nResponse: {response[:300]}...")
    
    def start(self):
        """Start the system in a background thread"""
        if self.running:
            return
            
        self.running = True
        self.paused = False
        self.thread = threading.Thread(target=self._run_system)
        self.thread.daemon = True
        self.thread.start()
        self.status_update.emit("System started")
        self.logger.info("System started in background thread")
    
    def pause(self):
        """Pause the system execution"""
        if not self.running or self.paused:
            return
            
        self.paused = True
        self.status_update.emit("System paused")
        self.logger.info("System paused")
    
    def resume(self):
        """Resume the system execution"""
        if not self.running or not self.paused:
            return
            
        self.paused = False
        self.status_update.emit("System resumed")
        self.logger.info("System resumed")
    
    def stop(self):
        """Stop the system"""
        if not self.running:
            return
            
        self.running = False
        self.paused = False
        self.thread.join(timeout=5.0)
        self.status_update.emit("System stopped")
        self.logger.info("System stopped")
    
    def _run_system(self):
        """Main system loop running in background"""
        try:
            # Initialize all agents
            for agent in self.agents:
                self.safe_execute(agent, "initialize")
            
            # Add an initial artificial learning update for demonstration
            self._emit_sample_learning_update("system_started", "System initialization complete. Beginning first learning cycle.")
            
            cycle_count = 0
            while self.running:
                # Check if paused
                if self.paused:
                    time.sleep(0.5)  # Short sleep when paused to prevent CPU spinning
                    continue
                    
                cycle_count += 1
                self.status_update.emit(f"Cycle {cycle_count}")
                self.logger.info(f"Starting cycle {cycle_count}")
                
                # Self-healing: Check if we're stuck in error cycles
                if self.consecutive_error_cycles >= self.max_error_cycles:
                    self.logger.warning(f"Detected {self.consecutive_error_cycles} consecutive error cycles. Initiating self-healing.")
                    self._perform_self_healing()
                    self.consecutive_error_cycles = 0
                
                # Health check via monitor
                health_status = self.safe_execute(self.monitor, "check_health", fallback_result={"healthy": False, "issues": ["Monitor execution failed"]})
                if not health_status or not health_status.get('healthy', False):
                    health_issues = health_status.get('issues', []) if health_status else ["Unknown health issues"]
                    # Extract message from each health issue (which are dictionaries)
                    issues_messages = []
                    for issue in health_issues:
                        if isinstance(issue, dict):
                            # Extract the message or description from the issue dictionary
                            msg = issue.get('message', issue.get('description', str(issue)))
                            issues_messages.append(msg)
                        else:
                            # If it's already a string, just add it
                            issues_messages.append(str(issue))
                    
                    issues_message = "; ".join(issues_messages) if issues_messages else "Unknown issues"
                    self.log_message.emit(f"Health check failed: {issues_message}")
                    self.logger.warning(f"Health check failed: {issues_message}")
                    
                    # Track health check failures
                    self.health_check_failures += 1
                    if self.health_check_failures > 5:
                        # If too many health check failures, reset circuit breakers
                        self.logger.warning(f"Detected {self.health_check_failures} consecutive health check failures. Resetting circuit breakers.")
                        self.reset_circuit_breakers()
                        self.health_check_failures = 0
                    
                    # Record the health check error
                    self._record_error("health_check_failure", issues_message)
                    
                    # Add artificial learning update about system health
                    self._emit_sample_learning_update("health_monitoring", 
                                                    f"System identified health issues: {issues_message[:100]}...")
                else:
                    # Reset health check failures counter on success
                    self.health_check_failures = 0
                
                # Generate a single test incrementally
                self.log_message.emit(f"Generating incremental test batch (size: {self.test_batch_size})")
                try:
                    new_tests = self.safe_execute(self.test_generator, "generate_tests", count=self.test_batch_size, fallback_result=[])
                    
                    # Check if test generation was successful
                    if not new_tests or len(new_tests) == 0:
                        self.logger.warning("Test generation failed to produce any tests")
                        self._record_error("test_generation_failure", "No tests generated")
                        self.consecutive_error_cycles += 1
                    else:
                        # Test generation succeeded, reset error cycle counter
                        self.consecutive_error_cycles = 0
                except Exception as e:
                    self.logger.error(f"Error in test generation: {str(e)}")
                    self._record_error("test_generation_exception", str(e))
                    self.consecutive_error_cycles += 1
                    new_tests = []
                
                # Update last test information
                if new_tests and len(new_tests) > 0:
                    self.last_test = new_tests[0]
                    self.test_update.emit({
                        'cycle_count': cycle_count,
                        'last_test': self.last_test,
                        'result': None
                    })
                    
                    # Add artificial learning update about test generation
                    test_name = self.last_test.get('name', f"Test {self.last_test.get('id', 'unknown')}")
                    test_type = self.last_test.get('type', 'unknown')
                    self._emit_sample_learning_update("test_generation", 
                                                    f"Created new {test_type} test: {test_name}")
                
                # Brief pause after test generation for UI updates
                time.sleep(1)
                
                # Run tests if any were generated
                if new_tests and len(new_tests) > 0:
                    self.log_message.emit("Running incremental test batch")
                    try:
                        test_results = self.safe_execute(self.tester, "run_tests", new_tests, fallback_result=[])
                        
                        # Check if test execution was successful
                        if not test_results or len(test_results) == 0:
                            self.logger.warning("Test execution failed to produce any results")
                            self._record_error("test_execution_failure", "No test results generated")
                            self.consecutive_error_cycles += 1
                        else:
                            # Test execution succeeded, reset error cycle counter
                            self.consecutive_error_cycles = 0
                    except Exception as e:
                        self.logger.error(f"Error in test execution: {str(e)}")
                        self._record_error("test_execution_exception", str(e))
                        self.consecutive_error_cycles += 1
                        test_results = []
                    
                    # Update last test result
                    if test_results and len(test_results) > 0:
                        self.last_test_result = test_results[0]
                        self.test_update.emit({
                            'cycle_count': cycle_count,
                            'last_test': self.last_test,
                            'result': self.last_test_result
                        })
                        
                        # Add artificial learning update about test results
                        passed = self.last_test_result.get('passed', False)
                        if passed:
                            self._emit_sample_learning_update("test_success", 
                                                            f"Test passed successfully. Analyzing patterns for future tests.")
                        else:
                            failure = self.last_test_result.get('failure_reason', 'Unknown failure')
                            self._emit_sample_learning_update("test_failure", 
                                                            f"Test failed with reason: {failure[:100]}... Analyzing error patterns.")
                    
                    # Brief pause after test execution for UI updates
                    time.sleep(1)
                    
                    # Fix any failures
                    if test_results and not all(result.get('passed', False) for result in test_results):
                        self.log_message.emit("Fixing failed tests")
                        
                        # NEW: Keep trying to fix failed tests until they're all fixed or max attempts reached
                        max_fix_attempts = 5  # Maximum number of fix attempts per test
                        fix_attempt = 0
                        still_failing = test_results
                        fixes = []
                        
                        while fix_attempt < max_fix_attempts:
                            fix_attempt += 1
                            self.log_message.emit(f"Fix attempt {fix_attempt}/{max_fix_attempts}")
                            self.logger.info(f"Fix attempt {fix_attempt}/{max_fix_attempts} for {len(still_failing)} failed tests")
                            
                            # Try to fix the failing tests
                            try:
                                new_fixes = self.safe_execute(self.fixer, "fix_issues", still_failing, fallback_result=[])
                                if new_fixes:
                                    fixes.extend(new_fixes)
                                
                                # Check if any fixes were successful
                                successful_fixes = [f for f in new_fixes if f.get('success', False)] if new_fixes else []
                                
                                if successful_fixes:
                                    self.log_message.emit(f"Successfully fixed {len(successful_fixes)} tests on attempt {fix_attempt}")
                                    
                                    # Record successful fix strategies
                                    for fix in successful_fixes:
                                        test_id = fix.get('test_id')
                                        if test_id:
                                            # Find the original failure
                                            original_failure = next((r.get('failure_reason') for r in still_failing if r.get('test_id') == test_id), None)
                                            if original_failure:
                                                # Record the successful fix strategy
                                                self._record_successful_fix(original_failure, fix)
                                else:
                                    self.log_message.emit(f"No successful fixes on attempt {fix_attempt}")
                                    
                                    # Record the fix failure
                                    for failed_test in still_failing:
                                        self._record_error("fix_failure", f"Failed to fix test {failed_test.get('test_id')}: {failed_test.get('failure_reason')}")
                                
                                # If all tests were fixed or we've reached max attempts, break
                                if successful_fixes and len(successful_fixes) == len(still_failing):
                                    self.log_message.emit("All tests fixed successfully!")
                                    break
                                    
                                # Re-run the still-failing tests to see if they're fixed
                                fixed_test_ids = [f.get('test_id') for f in successful_fixes]
                                still_failing = [r for r in still_failing if r.get('test_id') not in fixed_test_ids]
                                
                                # If no more failing tests, we're done
                                if not still_failing:
                                    break
                                    
                                # If we've reached max attempts, log that we're giving up
                                if fix_attempt >= max_fix_attempts:
                                    self.log_message.emit(f"Giving up after {max_fix_attempts} attempts to fix {len(still_failing)} tests")
                                    self.logger.warning(f"Giving up after {max_fix_attempts} attempts to fix {len(still_failing)} tests")
                                    
                                    # Record remaining failures for analysis
                                    for failed_test in still_failing:
                                        self._record_error("unfixable_test", f"Gave up on test {failed_test.get('test_id')}: {failed_test.get('failure_reason')}")
                            except Exception as e:
                                self.logger.error(f"Error during fix attempt {fix_attempt}: {str(e)}")
                                self._record_error("fix_exception", str(e))
                                self.consecutive_error_cycles += 1
                        
                        # Learn from the fixes (successful or not)
                        self.log_message.emit("Learning from fixes")
                        try:
                            learning_result = self.safe_execute(self.learner, "learn_from_fixes", fixes)
                            if not learning_result or not learning_result.get('success', False):
                                self.logger.warning("Learning from fixes failed")
                                self._record_error("learning_failure", "Failed to learn from fixes")
                                self.consecutive_error_cycles += 1
                        except Exception as e:
                            self.logger.error(f"Error learning from fixes: {str(e)}")
                            self._record_error("learning_exception", str(e))
                            self.consecutive_error_cycles += 1
                    else:
                        # Learn from successes
                        self.log_message.emit("Learning from successful tests")
                        try:
                            learning_result = self.safe_execute(self.learner, "learn_from_success", test_results)
                            if not learning_result or not learning_result.get('success', False):
                                self.logger.warning("Learning from successes failed")
                                self._record_error("learning_failure", "Failed to learn from successes")
                                self.consecutive_error_cycles += 1
                        except Exception as e:
                            self.logger.error(f"Error learning from successes: {str(e)}")
                            self._record_error("learning_exception", str(e))
                            self.consecutive_error_cycles += 1
                else:
                    # No tests to execute, increase error counter
                    self.consecutive_error_cycles += 1
                
                # Process any user requests
                self.safe_execute(self.user_interface, "process_pending_requests")
                
                # Save progress
                self.memory.save_cycle_results(cycle_count, {
                    'tests': new_tests,
                    'results': test_results
                })
                
                # Proceed immediately to the next cycle instead of waiting
                self.log_message.emit(f"Cycle {cycle_count} completed. Starting next cycle...")
                
        except Exception as e:
            self.logger.error(f"System error: {str(e)}", exc_info=True)
            self.status_update.emit(f"System error: {str(e)}")
            
            # Record the system error
            self._record_error("system_exception", str(e))
        finally:
            self.running = False
            self.paused = False
            
    def _emit_sample_learning_update(self, concept_type, insight_text):
        """Emit a sample learning update for demonstration purposes"""
        import datetime
        
        # Create a learning update
        learning_item = {
            "type": f"{concept_type}_learning",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "concept": concept_type,
            "insight": insight_text
        }
        
        # Emit the update
        self.learning_update.emit(learning_item)
    
    def process_user_input(self, prompt):
        """Process user input from the GUI"""
        return self.user_interface.process_prompt(prompt)
    
    def get_system_status(self):
        """Get the current status of all system components"""
        status = {
            'running': self.running,
            'paused': self.paused,
            'cycle_count': self.memory.get_cycle_count(),
            'model_name': self.model_name,
            'agents': {},
            'test_stats': {
                'tests_run': self.tester.tests_run,
                'tests_passed': self.tester.tests_passed,
                'tests_failed': self.tester.tests_failed,
                'tests_fixed': self.fixer.tests_fixed_successfully,  # Current session fixes
                'total_tests_fixed': self.fixed_tests_count  # All-time fixes (persisted)
            },
            'last_test': self.last_test,
            'last_test_result': self.last_test_result,
            'recent_llm': self.recent_llm_outputs[-1]['response'] if self.recent_llm_outputs else None
        }
        
        for agent in self.agents:
            status['agents'][agent.name] = agent.get_status()
            
        return status 
    
    def reset_circuit_breakers(self):
        """Reset all circuit breakers and failure counts"""
        self.logger.info("Manually resetting all circuit breakers")
        for agent in self.agents:
            self.circuit_breakers[agent.name] = False
            self.agent_failure_counts[agent.name] = 0
        return True
    
    def _load_fixed_tests_stats(self):
        """Load fixed tests statistics from memory"""
        stats = self.memory.get_knowledge("fixed_tests_stats")
        if stats:
            self.fixed_tests_count = stats.get("count", 0)
            self.logger.info(f"Loaded fixed tests stats: {self.fixed_tests_count} tests fixed")
            
    def _save_fixed_tests_stats(self):
        """Save fixed tests statistics to memory"""
        self.memory.save_knowledge("fixed_tests_stats", {
            "count": self.fixed_tests_count,
            "last_updated": time.time()
        })
        self.logger.info(f"Saved fixed tests stats: {self.fixed_tests_count} tests fixed")
    
    def _on_test_fixed(self, test_event):
        """Called when a test is successfully fixed"""
        self.fixed_tests_count += 1
        self.logger.info(f"Test fixed event received. Total fixed tests: {self.fixed_tests_count}")
        self._save_fixed_tests_stats()
    
    def safe_execute(self, agent, method_name, *args, **kwargs):
        """Safely execute an agent method with fault tolerance and circuit breaker pattern"""
        agent_name = agent.name
        
        # Check if circuit breaker is tripped
        if self.circuit_breakers.get(agent_name, False):
            # Check if enough time has passed to reset circuit breaker
            current_time = time.time()
            if current_time - self.last_failure_time.get(agent_name, 0) > self.circuit_breaker_reset_time:
                # Reset circuit breaker
                self.circuit_breakers[agent_name] = False
                self.agent_failure_counts[agent_name] = 0
                self.logger.info(f"Circuit breaker reset for agent {agent_name}")
            else:
                # Circuit breaker still active, skip execution
                self.logger.warning(f"Circuit breaker active for agent {agent_name}, skipping execution")
                
                # If all agents have circuit breakers tripped for a long time, force reset them
                all_breakers_active = all(self.circuit_breakers.get(a.name, False) for a in self.agents)
                if all_breakers_active:
                    self.logger.warning("All circuit breakers active, forcing reset for all agents")
                    for a in self.agents:
                        self.circuit_breakers[a.name] = False
                        self.agent_failure_counts[a.name] = 0
                    return None
                
                # Force reset specific agents after much longer time (15 minutes)
                force_reset_time = 15 * 60  # 15 minutes in seconds
                if current_time - self.last_failure_time.get(agent_name, 0) > force_reset_time:
                    self.logger.warning(f"Force resetting circuit breaker for agent {agent_name} after extended period")
                    self.circuit_breakers[agent_name] = False
                    self.agent_failure_counts[agent_name] = 0
                    # Continue with execution
                else:
                    return None
        
        # Execute the method with fault tolerance
        try:
            # Get the method to execute
            method = getattr(agent, method_name, None)
            if not method:
                self.logger.error(f"Method {method_name} not found in agent {agent_name}")
                self._record_error("missing_method", f"{agent_name}.{method_name}")
                return None
                
            # Execute the method
            self.logger.info(f"Executing {method_name} on agent {agent_name}")
            result = method(*args, **kwargs)
            
            # Reset failure count on success
            self.agent_failure_counts[agent_name] = 0
            
            return result
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error executing {method_name} on agent {agent_name}: {str(e)}", exc_info=True)
            
            # Record the error
            self._record_error(f"{agent_name}_{method_name}_error", str(e))
            
            # Increment failure count
            self.agent_failure_counts[agent_name] = self.agent_failure_counts.get(agent_name, 0) + 1
            self.last_failure_time[agent_name] = time.time()
            
            # Check if circuit breaker should trip
            if self.agent_failure_counts.get(agent_name, 0) >= self.max_agent_failures:
                self.circuit_breakers[agent_name] = True
                self.logger.warning(f"Circuit breaker tripped for agent {agent_name} after {self.max_agent_failures} failures")
                
            # Return fallback result
            return kwargs.get("fallback_result", None)
    
    def _perform_self_healing(self):
        """Perform self-healing actions when system is stuck in error cycles"""
        self.logger.info("Performing self-healing actions")
        self.log_message.emit("Detected system issues. Initiating self-healing protocol.")
        
        # 1. Reset all circuit breakers
        self.reset_circuit_breakers()
        
        # 2. Check for recurring errors and apply specific fixes
        most_common_error = self._get_most_common_error()
        if most_common_error:
            error_type, error_details = most_common_error
            self.logger.info(f"Most common error: {error_type} - {error_details[:100]}...")
            
            # Apply known recovery strategies
            if error_type in self.recovery_strategies:
                strategy = self.recovery_strategies[error_type]
                self.logger.info(f"Applying recovery strategy for {error_type}: {strategy.get('description', 'No description')}")
                
                # Apply the strategy
                if strategy.get('action') == 'reset_agent':
                    agent_name = strategy.get('agent_name')
                    if agent_name and agent_name in [a.name for a in self.agents]:
                        agent = next((a for a in self.agents if a.name == agent_name), None)
                        if agent:
                            self.logger.info(f"Reinitializing agent: {agent_name}")
                            self.safe_execute(agent, "initialize")
                elif strategy.get('action') == 'change_model':
                    new_model = strategy.get('model_name', 'qwen3:30b')
                    self.logger.info(f"Changing model to: {new_model}")
                    self.model_name = new_model
                    for agent in self.agents:
                        agent.model_name = new_model
                elif strategy.get('action') == 'restart_system':
                    self.logger.info("Initiating system restart")
                    self.stop()
                    time.sleep(1)
                    self.start()
        
        # 3. Check for and fix JSON parsing issues in learner
        if "KeyError: 0" in str(self.error_history.get("learning_exception", {}).get("details", "")):
            self.logger.info("Applying fix for KeyError: 0 in learner")
            # This would be handled by the improved _extract_first_insight method in learner.py
        
        # 4. Check disk space and memory issues
        if "disk usage is high" in str(self.error_history.get("health_check_failure", {}).get("details", "")):
            # Log warning about disk space
            self.logger.warning("Detected high disk usage. Consider freeing disk space.")
            self.log_message.emit("WARNING: High disk usage detected. System performance may be affected.")
        
        # 5. Log the self-healing action
        self.memory.save_knowledge("self_healing_actions", {
            "timestamp": time.time(),
            "actions_taken": ["reset_circuit_breakers", "check_common_errors", "apply_recovery_strategies"],
            "most_common_error": most_common_error[0] if most_common_error else None
        })
        
        self.log_message.emit("Self-healing protocol completed.")
    
    def _record_error(self, error_type, details):
        """Record an error for future analysis and self-healing"""
        current_time = time.time()
        
        # Initialize error type if not exists
        if error_type not in self.error_history:
            self.error_history[error_type] = {
                "count": 0,
                "first_seen": current_time,
                "last_seen": current_time,
                "details": details,
                "occurrences": []
            }
        
        # Update error stats
        self.error_history[error_type]["count"] += 1
        self.error_history[error_type]["last_seen"] = current_time
        self.error_history[error_type]["details"] = details  # Update with latest details
        
        # Keep last 10 occurrences with timestamps
        self.error_history[error_type]["occurrences"].append({
            "timestamp": current_time,
            "details": details
        })
        if len(self.error_history[error_type]["occurrences"]) > 10:
            self.error_history[error_type]["occurrences"] = self.error_history[error_type]["occurrences"][-10:]
        
        # Save error history to memory
        self.memory.save_knowledge("error_history", self.error_history)
        
        # Log the error
        self.logger.warning(f"Recorded error: {error_type} - {details[:100]}...")
    
    def _record_successful_fix(self, failure, fix):
        """Record a successful fix strategy for future use"""
        failure_signature = self._get_error_signature(failure)
        fix_type = fix.get('fix_type', 'unknown')
        
        # Create or update the recovery strategy
        if failure_signature not in self.recovery_strategies:
            self.recovery_strategies[failure_signature] = {
                "description": f"Fix for: {failure[:100]}...",
                "action": "apply_fix",
                "fix_type": fix_type,
                "fix_template": fix.get('fixed_code', ''),
                "success_count": 1,
                "last_success": time.time()
            }
        else:
            # Update existing strategy
            self.recovery_strategies[failure_signature]["success_count"] += 1
            self.recovery_strategies[failure_signature]["last_success"] = time.time()
            # Update the fix template if this is a more recent success
            self.recovery_strategies[failure_signature]["fix_template"] = fix.get('fixed_code', 
                self.recovery_strategies[failure_signature].get("fix_template", ''))
        
        # Save recovery strategies to memory
        self.memory.save_knowledge("recovery_strategies", self.recovery_strategies)
        
        # Log the recovery strategy
        self.logger.info(f"Recorded successful fix strategy for: {failure_signature}")
    
    def _get_error_signature(self, error_message):
        """Extract a unique signature from an error message for matching"""
        # Strip variable parts like line numbers and object IDs
        import re
        
        # Remove line numbers
        signature = re.sub(r'line \d+', 'line XXX', str(error_message))
        
        # Remove specific file paths
        signature = re.sub(r'File ".*?"', 'File "XXX"', signature)
        
        # Remove hex object IDs
        signature = re.sub(r'0x[0-9a-fA-F]+', '0xXXX', signature)
        
        # Keep only the first 100 chars to make it manageable
        if len(signature) > 100:
            signature = signature[:100]
            
        return signature
    
    def _get_most_common_error(self):
        """Get the most common error type and its details"""
        if not self.error_history:
            return None
            
        # Find the error type with the highest count
        most_common = max(self.error_history.items(), key=lambda x: x[1]["count"])
        return (most_common[0], most_common[1]["details"])
    
    def _load_error_history(self):
        """Load error history and recovery strategies from memory"""
        error_history = self.memory.get_knowledge("error_history")
        if error_history:
            self.error_history = error_history
            self.logger.info(f"Loaded error history with {len(error_history)} error types")
        
        recovery_strategies = self.memory.get_knowledge("recovery_strategies")
        if recovery_strategies:
            self.recovery_strategies = recovery_strategies
            self.logger.info(f"Loaded {len(recovery_strategies)} recovery strategies") 