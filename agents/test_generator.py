import logging
import json
import random
import time
from agents.base_agent import BaseAgent

class TestGenerator(BaseAgent):
    def __init__(self, system_manager, memory_manager, model_name):
        super().__init__(system_manager, memory_manager, model_name)
        
        # Test generation settings
        self.complexity_levels = ["beginner", "intermediate", "advanced", "expert"]
        self.current_complexity = "beginner"
        self.test_types = ["function", "integration", "system", "performance"]
        
        # Track performance for adaptive complexity
        self.success_rate = 0.5  # Initial 50% success rate assumption
        self.tests_generated = 0
        self.learned_patterns = {}
        
    def initialize(self):
        """Initialize the test generator"""
        super().initialize()
        
        # Load previous tests to understand current complexity level
        test_history = self.memory.get_knowledge("test_generation_history")
        if test_history:
            self.current_complexity = test_history.get("current_complexity", "beginner")
            self.success_rate = test_history.get("success_rate", 0.5)
            self.tests_generated = test_history.get("tests_generated", 0)

        learning_stats = self.memory.get_knowledge("learning_stats")
        if learning_stats:
            self.learned_patterns = learning_stats.get("patterns", {})
            
        self.logger.info(f"Test generator initialized at complexity level: {self.current_complexity}")
        return True
    
    def execute(self, *args, **kwargs):
        """Execute the test generation process"""
        return self.generate_tests(*args, **kwargs)
    
    def generate_tests(self, count=1):
        """Generate a specified number of tests"""
        if count <= 0:
            return []
            
        self.status = "generating"
        self.log_action("generate_tests", {"count": count})
        
        # For each test, generate a test of the appropriate complexity
        tests = []
        validation_failures = 0
        max_attempts = count * 3  # Try up to 3 times per test
        attempt = 0
        
        while len(tests) < count and attempt < max_attempts:
            attempt += 1
            self.logger.info(f"Generating test {len(tests)+1}/{count} (attempt {attempt})")
            
            try:
                # Generate a test
                test = self._generate_single_test()
                
                if test:
                    # Validate the test
                    is_valid, validation_message = self._validate_test(test)
                    
                    if is_valid:
                        # Save to database and get an ID
                        test_id = self.memory.save_test(test)
                        test["id"] = test_id
                        
                        # Add to the list of generated tests
                        tests.append(test)
                        self.tests_generated += 1
                    else:
                        self.logger.warning(f"Test validation failed: {validation_message}")
                        validation_failures += 1
                else:
                    self.logger.warning("Failed to generate test")
            except Exception as e:
                self.logger.error(f"Error generating test: {str(e)}")
                
        # Update metrics
        if validation_failures > 0:
            self.logger.info(f"{validation_failures} tests failed validation")
            
        # Update test generation history
        self._update_test_generation_knowledge()
        
        self.status = "ready"
        self.logger.info(f"Generated {len(tests)} tests at {self.current_complexity} complexity")
        
        return tests
    
    def _generate_single_test(self):
        """Generate a single test using the LLM"""
        # Select a test type
        test_type = random.choice(self.test_types)
        
        # Get previous knowledge to inform test generation
        previous_tests = self._get_recent_tests(5)
        previous_results = self._get_recent_results(5)
        
        # Create the prompt for the LLM
        system_prompt = """
        You are a test generator for a self-improving multi-agent system. 
        Your task is to create challenging but fair tests that will help the system learn and improve.
        Generate a single test case as a JSON object.
        """
        
        prompt = f"""
        Please generate a {self.current_complexity} level {test_type} test for our self-improving agent system.
        
        The test should:
        - Be appropriately challenging for the {self.current_complexity} complexity level
        - Have clear success criteria
        - Include necessary code or inputs
        - Be self-contained and executable
        
        Previous tests the system has seen:
        {json.dumps(previous_tests, indent=2)}
        
        Recent test results:
        {json.dumps(previous_results, indent=2)}

        Learned patterns to guide generation:
        {json.dumps(self.learned_patterns, indent=2)}
        
        Return ONLY a JSON object with these fields:
        {{
            "name": "Name of the test",
            "type": "{test_type}",
            "complexity": "{self.current_complexity}",
            "description": "Description of what the test evaluates",
            "inputs": {{...}},
            "code": "Code to execute (if needed)",
            "success_criteria": "Clear conditions for passing",
            "timeout_seconds": 30
        }}
        """
        
        # Query the model for test generation
        response = self.query_model(prompt, system_prompt=system_prompt)
        
        # Parse the JSON response
        try:
            # Extract JSON from the response if needed
            json_str = self._extract_json(response)
            test_data = json.loads(json_str)
            
            # Add metadata
            test_data["generated_at"] = time.time()
            test_data["generator_version"] = "1.0"
            
            return test_data
        except Exception as e:
            self.logger.error(f"Error parsing test response: {e}")
            # Return a fallback test
            return self._generate_fallback_test(test_type)
    
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
    
    def _generate_fallback_test(self, test_type):
        """Generate a fallback test when LLM parsing fails"""
        # Ensure parameter names in function match input keys
        return {
            "name": f"Fallback {test_type.capitalize()} Test",
            "type": test_type,
            "complexity": self.current_complexity,
            "description": "A basic test generated as fallback",
            "inputs": {"value": 10},
            "code": "def test_function(value):\n    return value * 2",  # Parameter name matches input key
            "success_criteria": "Result should be twice the input value",
            "timeout_seconds": 30,
            "generated_at": time.time(),
            "generator_version": "1.0",
            "is_fallback": True
        }
    
    def _get_recent_tests(self, count=5):
        """Get the most recent tests from memory"""
        all_tests = self.memory.test_history.get("tests", [])
        return all_tests[-count:] if all_tests else []
    
    def _get_recent_results(self, count=5):
        """Get the most recent test results from memory"""
        results = self.memory.test_history.get("results", {})
        recent_results = []
        
        # Flatten results from all tests
        for test_id, test_results in results.items():
            for result in test_results:
                result["test_id"] = test_id
                recent_results.append(result)
        
        # Sort by timestamp and take most recent
        recent_results.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return recent_results[:count]
    
    def _update_test_generation_knowledge(self):
        """Update knowledge about test generation history and adapt complexity"""
        # Calculate success rate from recent test results
        recent_results = self._get_recent_results(10)
        if recent_results:
            success_count = sum(1 for r in recent_results if r.get("passed", False))
            self.success_rate = success_count / len(recent_results)
        
        # Adapt complexity based on success rate
        self._adapt_complexity()
        
        # Save knowledge
        self.memory.save_knowledge("test_generation_history", {
            "current_complexity": self.current_complexity,
            "success_rate": self.success_rate,
            "tests_generated": self.tests_generated,
            "last_updated": time.time()
        })
    
    def _adapt_complexity(self):
        """Adapt the complexity level based on success rate"""
        current_index = self.complexity_levels.index(self.current_complexity)
        
        # If success rate is high, increase complexity (more conservative)
        if self.success_rate > 0.9 and current_index < len(self.complexity_levels) - 1:
            self.current_complexity = self.complexity_levels[current_index + 1]
            self.logger.info(f"Increased complexity to {self.current_complexity} (success rate: {self.success_rate:.2f})")
            self.log_action("increase_complexity", {"new_level": self.current_complexity, "success_rate": self.success_rate})
        
        # If success rate is low, decrease complexity
        elif self.success_rate < 0.5 and current_index > 0:
            self.current_complexity = self.complexity_levels[current_index - 1]
            self.logger.info(f"Decreased complexity to {self.current_complexity} (success rate: {self.success_rate:.2f})")
            self.log_action("decrease_complexity", {"new_level": self.current_complexity, "success_rate": self.success_rate})
    
    def _validate_test(self, test):
        """Validate that a test has valid Python syntax and required fields"""
        if not test:
            return False, "Test is empty"
            
        # Check required fields
        required_fields = ["code", "type", "name", "inputs", "success_criteria"]
        for field in required_fields:
            if field not in test:
                return False, f"Missing required field: {field}"
        
        # Validate code syntax
        code = test.get("code", "")
        try:
            # Try to compile the code to check syntax
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            # Fix common syntax issues
            fixed_code = self._fix_syntax(code, str(e))
            if fixed_code:
                test["code"] = fixed_code
                # Try to compile again with fixed code
                try:
                    compile(fixed_code, "<string>", "exec")
                except SyntaxError as e:
                    return False, f"Invalid syntax after fixing: {str(e)}"
            else:
                return False, f"Invalid syntax: {str(e)}"
        except Exception as e:
            return False, f"Code validation error: {str(e)}"
            
        # Validate inputs
        inputs = test.get("inputs", {})
        if not isinstance(inputs, dict):
            test["inputs"] = {"value": inputs}  # Convert to dict with single key
        
        # Validate success criteria
        success_criteria = test.get("success_criteria", "")
        if not success_criteria:
            test["success_criteria"] = "output == value * 2"  # Default criteria
        
        return True, "Test is valid"
        
    def _fix_syntax(self, code, error_message):
        """Fix common syntax errors in test code"""
        self.logger.info(f"Attempting to fix syntax: {error_message}")
        
        # Convert tabs to spaces
        code = code.replace("\t", "    ")
        
        # Fix missing colons in function definitions
        if "expected ':'" in error_message:
            lines = code.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("def ") and ":" not in line:
                    lines[i] = line + ":"
            return "\n".join(lines)
            
        # Fix unclosed quotes
        if "EOL while scanning string literal" in error_message:
            lines = code.split("\n")
            for i, line in enumerate(lines):
                # Check for unclosed quotes
                if (line.count("'") % 2 == 1) or (line.count('"') % 2 == 1):
                    # Add closing quote of the same type
                    if line.count("'") % 2 == 1:
                        lines[i] = line + "'"
                    if line.count('"') % 2 == 1:
                        lines[i] = line + '"'
            return "\n".join(lines)
            
        # Fix missing parentheses
        if "unexpected EOF" in error_message and "parenthesis" in error_message:
            open_parens = code.count('(')
            close_parens = code.count(')')
            if open_parens > close_parens:
                return code + ')' * (open_parens - close_parens)
                
        # Fix unexpected characters in code
        if "\\n" in code:
            return code.replace("\\n", "\n")
            
        # Couldn't fix automatically
        return None 