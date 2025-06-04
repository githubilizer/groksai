import logging
import os
import json
import time
import subprocess
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self, system_manager, memory_manager, model_name):
        self.logger = logging.getLogger(f"agent.{self.__class__.__name__}")
        self.system_manager = system_manager
        self.memory = memory_manager
        self.model_name = model_name
        self.name = self.__class__.__name__
        self.status = "initialized"
        self.last_action_time = time.time()
        self.model_failure_count = 0  # Track consecutive model failures
        self.max_model_failures = 3   # Max failures before using fallback
        
        # Callback for LLM responses - can be set by SystemManager
        self.on_llm_response = None
    
    def initialize(self):
        """Initialize the agent"""
        self.logger.info(f"Initializing {self.name}")
        self.status = "ready"
        return True
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """Main execution method to be implemented by each agent"""
        pass
    
    def get_status(self):
        """Get the current status of this agent"""
        return {
            "status": self.status,
            "last_action": time.time() - self.last_action_time,
            "model_failures": self.model_failure_count
        }
    
    def query_model(self, prompt, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Query the Ollama model with the given prompt"""
        self.logger.debug(f"Querying model with prompt: {prompt[:100]}...")
        
        # Check if we've had too many consecutive failures
        if self.model_failure_count >= self.max_model_failures:
            self.logger.warning(f"Using fallback response due to {self.model_failure_count} consecutive model failures")
            fallback_response = self._generate_fallback_response(prompt, system_prompt)
            
            # Call the callback if it exists
            if self.on_llm_response:
                try:
                    self.on_llm_response(self.name, prompt, f"[FALLBACK] {fallback_response}")
                except Exception as callback_error:
                    self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
            
            return fallback_response
            
        # Max retry attempts for transient errors
        max_retries = 2
        retry_count = 0
        retry_delay = 1  # Start with 1 second delay
        
        while retry_count <= max_retries:
            try:
                # First check if the model exists
                model_check = subprocess.run(
                    ["ollama", "list"], 
                    capture_output=True, 
                    text=True,
                    check=False,
                    timeout=10  # 10 second timeout for model list
                )
                
                if self.model_name not in model_check.stdout:
                    self.logger.error(f"Model {self.model_name} is not available in Ollama")
                    
                    # Try to download the model if it doesn't exist
                    if retry_count == 0:  # Only try to pull on first attempt
                        self.logger.info(f"Attempting to pull model {self.model_name}")
                        try:
                            pull_result = subprocess.run(
                                ["ollama", "pull", self.model_name],
                                capture_output=True,
                                text=True,
                                check=False,
                                timeout=60  # Allow up to 60 seconds for pull
                            )
                            
                            if pull_result.returncode == 0:
                                self.logger.info(f"Successfully pulled model {self.model_name}")
                                # Continue with query now that model is available
                            else:
                                self.logger.error(f"Failed to pull model {self.model_name}: {pull_result.stderr}")
                                self.model_failure_count += 1
                                retry_count += 1
                                continue
                        except Exception as pull_error:
                            self.logger.error(f"Error pulling model {self.model_name}: {str(pull_error)}")
                            self.model_failure_count += 1
                            retry_count += 1
                            continue
                    else:
                        self.model_failure_count += 1
                        
                        error_msg = f"Model {self.model_name} is not available in Ollama. Available models: {model_check.stdout}"
                        
                        # Call the callback with error info
                        if self.on_llm_response:
                            try:
                                self.on_llm_response(self.name, prompt, f"Error: {error_msg}")
                            except Exception as callback_error:
                                self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                                
                        # If we've exhausted retries, return the error
                        if retry_count >= max_retries:
                            return f"Error: {error_msg}"
                            
                        # Otherwise, increment retry count and try again after delay
                        retry_count += 1
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                # Prepare command and modify prompt with system prompt if provided
                cmd = ["ollama", "run", self.model_name]
                
                if system_prompt:
                    # Format the prompt with the appropriate system prompt template
                    # Qwen models use a different format than other models
                    if "qwen" in self.model_name.lower():
                        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>"
                    else:
                        # Generic format for other models
                        prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"
                
                # Set a timeout to prevent hanging
                result = subprocess.run(
                    cmd, 
                    input=prompt, 
                    capture_output=True, 
                    text=True,
                    check=True,
                    timeout=45  # 45 second timeout
                )
                
                response = result.stdout.strip()
                self.logger.debug(f"Model response: {response[:100]}...")
                
                # Reset failure count on success
                self.model_failure_count = 0
                
                # Call the callback if it exists
                if self.on_llm_response:
                    try:
                        self.on_llm_response(self.name, prompt, response)
                    except Exception as callback_error:
                        self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                
                # Validate the response - check if it's empty or too short
                if not response or len(response) < 5:
                    self.logger.warning(f"Model returned empty or very short response: '{response}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                
                return response
                
            except subprocess.TimeoutExpired:
                self.logger.error(f"Timeout while querying model {self.model_name}")
                self.model_failure_count += 1
                
                # If we've exhausted retries, return the error
                if retry_count >= max_retries:
                    error_msg = f"Model query timed out after 45 seconds"
                    
                    # Call the callback with error info
                    if self.on_llm_response:
                        try:
                            self.on_llm_response(self.name, prompt, f"Error: {error_msg}")
                        except Exception as callback_error:
                            self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                            
                    return f"Error: {error_msg}"
                
                # Otherwise, increment retry count and try again after delay
                retry_count += 1
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error querying model: {e}")
                self.logger.error(f"Stderr: {e.stderr}")
                self.model_failure_count += 1
                
                # Check if it's a connection issue that might be temporary
                if "connection refused" in e.stderr.lower() or "no route to host" in e.stderr.lower():
                    self.logger.warning("Connection issue detected, might be temporary")
                    # If we've exhausted retries, return the error
                    if retry_count >= max_retries:
                        error_msg = f"Connection error: {e.stderr}"
                        
                        # Call the callback with error info
                        if self.on_llm_response:
                            try:
                                self.on_llm_response(self.name, prompt, f"Error: {error_msg}")
                            except Exception as callback_error:
                                self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                                
                        return f"Error: {error_msg}"
                    
                    # Otherwise, increment retry count and try again after delay
                    retry_count += 1
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                
                # Call the callback with error info
                if self.on_llm_response:
                    try:
                        self.on_llm_response(self.name, prompt, f"Error: {e.stderr}")
                    except Exception as callback_error:
                        self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                        
                return f"Error: {e.stderr}"
                
            except Exception as e:
                self.logger.error(f"Unexpected error querying model: {str(e)}")
                self.model_failure_count += 1
                
                # Call the callback with error info
                if self.on_llm_response:
                    try:
                        self.on_llm_response(self.name, prompt, f"Error: {str(e)}")
                    except Exception as callback_error:
                        self.logger.error(f"Error in LLM response callback: {str(callback_error)}")
                
                # If it's a likely transient error, retry
                if "connection" in str(e).lower() or "timeout" in str(e).lower() or "temporary" in str(e).lower():
                    if retry_count < max_retries:
                        retry_count += 1
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                        
                return f"Error: {str(e)}"
    
    def _generate_fallback_response(self, prompt, system_prompt=None):
        """Generate a fallback response when the model is unavailable"""
        self.logger.info("Generating fallback response")
        
        # For test generation
        if "generate" in prompt.lower() and "test" in prompt.lower():
            return json.dumps({
                "name": "Fallback Test",
                "type": "function",
                "complexity": "beginner",
                "description": "A simple test generated when the model is unavailable",
                "inputs": {"value": 10},
                "code": "def test_function(value):\n    return value * 2",
                "success_criteria": "output == value * 2",
                "timeout_seconds": 30
            })
        
        # For fix generation
        elif "fix" in prompt.lower() and ("error" in prompt.lower() or "fail" in prompt.lower()):
            return json.dumps({
                "analysis": "Fallback fix due to model unavailability",
                "fix_type": "code_change",
                "fixed_code": "def test_function(value):\n    return value * 2",
                "explanation": "Generic working function as fallback"
            })
        
        # For insights or learning
        elif "insights" in prompt.lower() or "learn" in prompt.lower():
            return json.dumps({
                "principles": ["Ensure robust error handling", "Validate inputs carefully"],
                "patterns": ["Proper function signatures", "Clear success criteria"],
                "applications": ["Apply to all test types", "Ensure consistent parameter naming"]
            })
        
        # Generic fallback
        else:
            return json.dumps({
                "status": "fallback",
                "message": "Model temporarily unavailable",
                "fallback_response": "This is a fallback response due to model unavailability"
            })
    
    def log_action(self, action, details=None):
        """Log an action taken by this agent"""
        self.last_action_time = time.time()
        
        action_log = {
            "agent": self.name,
            "action": action,
            "timestamp": self.last_action_time,
            "details": details or {}
        }
        
        self.memory.log_agent_action(action_log)
        return action_log 