import logging
import json
import time
import threading
import queue
from datetime import datetime
from agents.base_agent import BaseAgent

class UserInterface(BaseAgent):
    def __init__(self, system_manager, memory_manager, model_name):
        super().__init__(system_manager, memory_manager, model_name)
        
        # User interaction tracking
        self.interactions = 0
        self.pending_requests = queue.Queue()
        self.processing_thread = None
        self.processing_active = False
        
        # Response history
        self.response_history = []
        
    def initialize(self):
        """Initialize the user interface agent"""
        super().initialize()
        
        # Load previous interaction stats
        ui_stats = self.memory.get_knowledge("ui_stats")
        if ui_stats:
            self.interactions = ui_stats.get("interactions", 0)
            self.response_history = ui_stats.get("recent_responses", [])
            
        # Start background processing thread
        self._start_processing_thread()
            
        self.logger.info(f"User interface initialized. Previous interactions: {self.interactions}")
        return True
    
    def execute(self, *args, **kwargs):
        """Execute based on the type of request"""
        if "prompt" in kwargs:
            return self.process_prompt(kwargs["prompt"])
        elif args and isinstance(args[0], str):
            return self.process_prompt(args[0])
        else:
            return self.process_pending_requests()
    
    def process_prompt(self, prompt):
        """Process a user prompt and generate a response"""
        self.status = "processing"
        self.interactions += 1
        self.log_action("process_prompt", {"prompt_length": len(prompt)})
        
        self.logger.info(f"Processing user prompt: {prompt[:50]}...")
        
        # Create a request ID
        request_id = f"request_{int(time.time())}_{self.interactions}"
        
        try:
            # Get system state for context
            system_status = self.system_manager.get_system_status()
            
            # Format system status for the prompt
            status_str = self._format_system_status(system_status)
            
            # Create the prompt for the LLM
            system_prompt = """
            You are an AI assistant interface for a self-improving multi-agent system.
            Your role is to interpret user requests, provide information about the system,
            and coordinate with other agents to fulfill complex requests.
            Respond in a helpful, concise, and informative manner.
            """
            
            full_prompt = f"""
            USER REQUEST: {prompt}
            
            SYSTEM STATUS:
            {status_str}
            
            Based on the user's request and the current system status, please provide:
            1. A direct response to the user
            2. Any actions that should be taken by the system
            
            Return your response as a JSON object with these fields:
            {{
                "user_response": "Your direct response to the user",
                "actions": [
                    {{
                        "type": "action_type",
                        "details": {{...}}
                    }}
                ],
                "priority": "high|medium|low"
            }}
            """
            
            # Query the model for a response
            response = self.query_model(full_prompt, system_prompt=system_prompt)
            
            # Parse the JSON response
            try:
                json_str = self._extract_json(response)
                response_data = json.loads(json_str)
                
                # Extract the user-facing response
                user_response = response_data.get("user_response", "I'm processing your request.")
                actions = response_data.get("actions", [])
                priority = response_data.get("priority", "medium")
                
                # Save the interaction to memory
                self._save_interaction(request_id, prompt, user_response, response_data)
                
                # If there are actions to take, queue them for processing
                if actions:
                    self._queue_actions(request_id, actions, priority)
                
                # Save the response to history
                self._add_to_response_history(request_id, prompt, user_response)
                
                # Update UI stats
                self._update_ui_stats()
                
                self.status = "ready"
                return {
                    "request_id": request_id,
                    "response": user_response,
                    "actions_queued": len(actions)
                }
                
            except Exception as e:
                self.logger.error(f"Error parsing response: {e}")
                
                # Return a fallback response
                fallback_response = "I'm having trouble processing that request right now. Could you try again?"
                
                self._save_interaction(request_id, prompt, fallback_response, {"error": str(e)})
                self.status = "ready"
                
                return {
                    "request_id": request_id,
                    "response": fallback_response,
                    "error": str(e)
                }
                
        except Exception as e:
            self.logger.error(f"Error processing prompt: {e}")
            self.status = "ready"
            
            return {
                "request_id": request_id,
                "response": "An error occurred while processing your request.",
                "error": str(e)
            }
    
    def process_pending_requests(self):
        """Process any pending requests in the queue"""
        processed = 0
        
        # Check if there are any pending requests
        if self.pending_requests.empty():
            return {"processed": 0}
            
        self.status = "processing"
        self.log_action("process_pending_requests")
        
        # Process up to 5 requests at a time
        for _ in range(5):
            try:
                if self.pending_requests.empty():
                    break
                    
                # Get the next request
                request = self.pending_requests.get_nowait()
                
                # Process the request
                self._process_action(request)
                processed += 1
                
                # Mark as done
                self.pending_requests.task_done()
                
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing pending request: {e}")
        
        self.status = "ready"
        self.logger.info(f"Processed {processed} pending requests")
        
        return {
            "processed": processed,
            "remaining": self.pending_requests.qsize()
        }
    
    def _queue_actions(self, request_id, actions, priority):
        """Queue actions for processing"""
        priority_value = {"high": 0, "medium": 1, "low": 2}.get(priority, 1)
        
        for action in actions:
            self.pending_requests.put({
                "request_id": request_id,
                "action": action,
                "priority": priority_value,
                "timestamp": time.time()
            })
            
        self.logger.info(f"Queued {len(actions)} actions for request {request_id} with priority {priority}")
    
    def _process_action(self, request):
        """Process a single action request"""
        request_id = request.get("request_id")
        action = request.get("action", {})
        action_type = action.get("type")
        details = action.get("details", {})
        
        self.logger.info(f"Processing action {action_type} for request {request_id}")
        
        try:
            # Handle different types of actions
            if action_type == "generate_tests":
                count = details.get("count", 3)
                self.logger.info(f"Requesting test generation: {count} tests")
                self.system_manager.test_generator.generate_tests(count=count)
                
            elif action_type == "run_specific_test":
                test_code = details.get("code")
                test_type = details.get("type", "function")
                inputs = details.get("inputs", {})
                success_criteria = details.get("success_criteria", "")
                
                if test_code:
                    # Create a test object
                    test = {
                        "name": details.get("name", f"User requested test {int(time.time())}"),
                        "type": test_type,
                        "complexity": details.get("complexity", "intermediate"),
                        "description": details.get("description", "User requested test"),
                        "code": test_code,
                        "inputs": inputs,
                        "success_criteria": success_criteria,
                        "timeout_seconds": details.get("timeout_seconds", 30),
                        "user_generated": True
                    }
                    
                    # Save the test
                    test_id = self.memory.save_test(test)
                    test["id"] = test_id
                    
                    # Run the test
                    self.logger.info(f"Running user-requested test {test_id}")
                    self.system_manager.tester.run_tests([test])
                
            elif action_type == "get_system_health":
                self.logger.info("Requesting system health check")
                self.system_manager.monitor.check_health()
                
            elif action_type == "get_learning_stats":
                stats = self.memory.get_knowledge("learning_stats") or {}
                self.logger.info(f"Retrieved learning stats: {len(stats)} entries")
                
            elif action_type == "custom_query":
                query = details.get("query")
                if query:
                    # This allows running custom queries against the knowledge base
                    self.logger.info(f"Running custom query: {query[:50]}...")
                    # Implementation would depend on what types of queries are supported
                
            else:
                self.logger.warning(f"Unknown action type: {action_type}")
                
            # Record that the action was processed
            self.memory.log_agent_action({
                "agent": self.name,
                "action": "process_action",
                "timestamp": time.time(),
                "details": {
                    "request_id": request_id,
                    "action_type": action_type,
                    "success": True
                }
            })
            
        except Exception as e:
            self.logger.error(f"Error processing action {action_type}: {e}")
            
            # Record the error
            self.memory.log_agent_action({
                "agent": self.name,
                "action": "process_action_error",
                "timestamp": time.time(),
                "details": {
                    "request_id": request_id,
                    "action_type": action_type,
                    "error": str(e)
                }
            })
    
    def _save_interaction(self, request_id, prompt, response, full_data):
        """Save an interaction to memory"""
        interaction = {
            "request_id": request_id,
            "timestamp": time.time(),
            "prompt": prompt,
            "response": response,
            "full_data": full_data
        }
        
        # Save to memory under a unique key
        self.memory.save_knowledge(f"interaction_{request_id}", interaction)
        
        # Also log the action
        self.memory.log_agent_action({
            "agent": self.name,
            "action": "user_interaction",
            "timestamp": time.time(),
            "details": {
                "request_id": request_id,
                "prompt_length": len(prompt),
                "response_length": len(response)
            }
        })
    
    def _add_to_response_history(self, request_id, prompt, response):
        """Add a response to the history"""
        self.response_history.append({
            "request_id": request_id,
            "timestamp": time.time(),
            "prompt": prompt[:100] + ("..." if len(prompt) > 100 else ""),
            "response": response[:100] + ("..." if len(response) > 100 else "")
        })
        
        # Keep only the last 20 responses
        if len(self.response_history) > 20:
            self.response_history = self.response_history[-20:]
    
    def _update_ui_stats(self):
        """Update UI statistics"""
        self.memory.save_knowledge("ui_stats", {
            "interactions": self.interactions,
            "last_interaction": time.time(),
            "recent_responses": self.response_history,
            "pending_requests": self.pending_requests.qsize(),
            "last_updated": time.time()
        })
    
    def _format_system_status(self, status):
        """Format system status for inclusion in prompts"""
        output = []
        
        # Basic status
        output.append(f"System running: {status.get('running', False)}")
        output.append(f"Current cycle: {status.get('cycle_count', 0)}")
        
        # Agent statuses
        output.append("\nAgent Statuses:")
        for name, agent_status in status.get('agents', {}).items():
            output.append(f"- {name}: {agent_status.get('status', 'unknown')}")
        
        return "\n".join(output)
    
    def _extract_json(self, text):
        """Extract JSON string from text that might contain other content"""
        try:
            # Try to parse the whole text as JSON first
            json.loads(text)
            return text
        except:
            # Try to find JSON between curly braces
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > 0:
                json_str = text[start:end]
                try:
                    # Validate it's parseable
                    json.loads(json_str)
                    return json_str
                except:
                    pass
                    
            # Another approach is to look for code blocks in markdown
            if "```json" in text and "```" in text[text.find("```json")+7:]:
                start = text.find("```json") + 7
                end = text.find("```", start)
                json_str = text[start:end].strip()
                return json_str
                
            # Fallback: just return the original text and let the caller handle the error
            return text
    
    def _start_processing_thread(self):
        """Start background thread for processing requests"""
        if self.processing_thread and self.processing_thread.is_alive():
            return  # Already running
            
        self.processing_active = True
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        self.logger.info("Started background processing thread")
    
    def _stop_processing_thread(self):
        """Stop the background processing thread"""
        self.processing_active = False
        if self.processing_thread:
            self.processing_thread.join(timeout=10.0)
            self.logger.info("Stopped background processing thread")
    
    def _processing_loop(self):
        """Background thread that periodically processes pending requests"""
        while self.processing_active:
            try:
                # Sleep briefly
                time.sleep(5)
                
                # Skip if the system is not running
                if not self.system_manager.running:
                    continue
                
                # Skip if there are no pending requests
                if self.pending_requests.empty():
                    continue
                
                # Process pending requests
                self.process_pending_requests()
                    
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
                time.sleep(30)  # Sleep longer if there was an error 