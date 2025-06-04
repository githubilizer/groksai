import logging
import json
import time
import os
import datetime
from collections import defaultdict
from agents.base_agent import BaseAgent

class Learner(BaseAgent):
    def __init__(self, system_manager, memory_manager, model_name):
        super().__init__(system_manager, memory_manager, model_name)
        
        # Learning tracking
        self.learning_sessions = 0
        self.concepts_learned = 0
        self.rules_discovered = 0
        
        # Pattern recognition
        self.patterns = defaultdict(int)
        self.success_patterns = defaultdict(int)
        self.failure_patterns = defaultdict(int)
        
    def initialize(self):
        """Initialize the learner agent"""
        super().initialize()
        
        # Load previous learning stats
        learning_stats = self.memory.get_knowledge("learning_stats")
        if learning_stats:
            self.learning_sessions = learning_stats.get("learning_sessions", 0)
            self.concepts_learned = learning_stats.get("concepts_learned", 0)
            self.rules_discovered = learning_stats.get("rules_discovered", 0)
            
            # Load patterns
            self.patterns = defaultdict(int, learning_stats.get("patterns", {}))
            self.success_patterns = defaultdict(int, learning_stats.get("success_patterns", {}))
            self.failure_patterns = defaultdict(int, learning_stats.get("failure_patterns", {}))
            
        self.logger.info(f"Learner initialized. Previous stats: {self.learning_sessions} sessions, {self.concepts_learned} concepts")
        return True
    
    def execute(self, *args, **kwargs):
        """Execute learning process based on input type"""
        if "fixes" in kwargs:
            return self.learn_from_fixes(kwargs["fixes"])
        elif "test_results" in kwargs:
            return self.learn_from_success(kwargs["test_results"])
        elif args and isinstance(args[0], list):
            # Try to determine if the list contains fixes or test results
            if args[0] and "fix_type" in args[0][0]:
                return self.learn_from_fixes(args[0])
            else:
                return self.learn_from_success(args[0])
        else:
            self.logger.warning("No valid learning input provided")
            return {"success": False, "reason": "No valid input"}
    
    def learn_from_fixes(self, fixes):
        """Learn from fixes applied to failing tests"""
        if not fixes:
            self.logger.warning("No fixes provided to learn from")
            return {"success": False, "reason": "No fixes provided"}
            
        self.status = "learning"
        self.log_action("learn_from_fixes", {"count": len(fixes)})
        
        # Track this learning session
        self.learning_sessions += 1
        session_id = f"fix_learning_{int(time.time())}"
        
        # Extract patterns and insights from fixes
        learnings = []
        
        for fix in fixes:
            # Only learn from successful fixes
            if not fix.get("success", False):
                continue
                
            test_id = fix.get("test_id")
            fix_type = fix.get("fix_type", "unknown")
            analysis = fix.get("analysis", "")
            
            # Get the test and results
            test = self._get_test_by_id(test_id)
            if not test:
                continue
                
            # Extract patterns from the fix
            patterns = self._extract_patterns(fix, test)
            
            # Generate insights using LLM if the fix looks significant
            if self._is_significant_fix(fix):
                insights = self._generate_insights(fix, test)
                
                # Store the insights
                if insights:
                    concept_name = f"fix_pattern_{fix_type}_{len(self.patterns)}"
                    self.memory.save_knowledge(concept_name, {
                        "type": "fix_pattern",
                        "patterns": patterns,
                        "insights": insights,
                        "examples": [{"test_id": test_id, "fix": fix}],
                        "created_at": time.time()
                    })
                    self.concepts_learned += 1
                    
                    learning_item = {
                        "concept": concept_name,
                        "insights": insights,
                        "type": "fix_learning",
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                        "insight": self._extract_first_insight(insights, f"Learned a new {fix_type} fix pattern")
                    }
                    
                    learnings.append(learning_item)
                    
                    # Emit signal for real-time updates
                    self.system_manager.learning_update.emit(learning_item)
        
        # Update learning stats
        self._update_learning_stats()
        
        self.status = "ready"
        self.logger.info(f"Learned from {len(fixes)} fixes, extracted {len(learnings)} new concepts")
        
        return {
            "success": True,
            "session_id": session_id,
            "learnings": learnings
        }
    
    def learn_from_success(self, test_results):
        """Learn from successful test executions"""
        if not test_results:
            self.logger.warning("No test results provided to learn from")
            return {"success": False, "reason": "No test results provided"}
            
        # Filter for successful tests only
        successful_tests = [r for r in test_results if r.get("passed", True)]
        
        if not successful_tests:
            self.logger.info("No successful tests to learn from")
            return {"success": False, "reason": "No successful tests"}
            
        self.status = "learning"
        self.log_action("learn_from_success", {"count": len(successful_tests)})
        
        # Track this learning session
        self.learning_sessions += 1
        session_id = f"success_learning_{int(time.time())}"
        
        # Extract patterns and insights from successful tests
        learnings = []
        
        # Group tests by type to look for patterns
        tests_by_type = defaultdict(list)
        for result in successful_tests:
            test_id = result.get("test_id")
            test = self._get_test_by_id(test_id)
            if test:
                test_type = test.get("type", "unknown")
                tests_by_type[test_type].append((test, result))
        
        # For each test type with enough examples, try to learn patterns
        for test_type, test_results in tests_by_type.items():
            if len(test_results) >= 3:  # Need at least 3 examples to find patterns
                patterns = self._extract_success_patterns(test_results)
                
                if patterns:
                    # Generate insights from the patterns
                    insights = self._generate_success_insights(test_type, patterns, test_results)
                    
                    if insights:
                        concept_name = f"success_pattern_{test_type}_{len(self.success_patterns)}"
                        self.memory.save_knowledge(concept_name, {
                            "type": "success_pattern",
                            "test_type": test_type,
                            "patterns": patterns,
                            "insights": insights,
                            "examples": [{"test_id": t.get("id"), "result": r} for t, r in test_results[:3]],
                            "created_at": time.time()
                        })
                        self.concepts_learned += 1
                        
                        learning_item = {
                            "concept": concept_name,
                            "insights": insights,
                            "type": "success_learning",
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                            "insight": self._extract_first_insight(insights, f"Learned pattern from {test_type} tests")
                        }
                        
                        learnings.append(learning_item)
                        
                        # Emit signal for real-time updates
                        self.system_manager.learning_update.emit(learning_item)
        
        # Update learning stats
        self._update_learning_stats()
        
        self.status = "ready"
        self.logger.info(f"Learned from {len(successful_tests)} successful tests, extracted {len(learnings)} new concepts")
        
        return {
            "success": True,
            "session_id": session_id,
            "learnings": learnings
        }
    
    def _extract_patterns(self, fix, test):
        """Extract patterns from a fix and the related test"""
        patterns = {}
        
        # Basic patterns
        fix_type = fix.get("fix_type", "unknown")
        test_type = test.get("type", "unknown")
        
        # Track occurrence of this pattern
        pattern_key = f"{test_type}_{fix_type}"
        self.patterns[pattern_key] += 1
        self.failure_patterns[pattern_key] += 1
        
        # Extract code patterns if it's a code change
        if fix_type == "code_change" and "fixed_code" in fix and "code" in test:
            # Simple diff analysis (could be enhanced with actual diff algorithm)
            original_code = test.get("code", "").split("\n")
            fixed_code = fix.get("fixed_code", "").split("\n")
            
            # Very basic diff
            if len(original_code) == len(fixed_code):
                for i in range(len(original_code)):
                    if original_code[i] != fixed_code[i]:
                        patterns[f"line_change_{i}"] = {
                            "original": original_code[i],
                            "fixed": fixed_code[i]
                        }
        
        return patterns
    
    def _extract_success_patterns(self, test_results):
        """Extract patterns from successful test executions"""
        patterns = {}
        
        # Group tests by complexity
        by_complexity = defaultdict(list)
        for test, result in test_results:
            complexity = test.get("complexity", "unknown")
            by_complexity[complexity].append((test, result))
        
        # Look for common elements in tests of the same complexity
        for complexity, tests in by_complexity.items():
            if len(tests) < 2:
                continue
                
            # Find common elements in test code
            codes = [t.get("code", "") for t, _ in tests]
            common_substrings = self._find_common_substrings(codes, min_length=10)
            
            if common_substrings:
                patterns[f"common_code_{complexity}"] = common_substrings
                
            # Track success pattern
            pattern_key = f"{tests[0][0].get('type', 'unknown')}_{complexity}"
            self.patterns[pattern_key] += 1
            self.success_patterns[pattern_key] += 1
        
        return patterns
    
    def _find_common_substrings(self, strings, min_length=10):
        """Find common substrings across multiple strings"""
        if not strings:
            return []
            
        # Start with the first string's substrings
        candidates = []
        for i in range(len(strings[0])):
            for j in range(i + min_length, len(strings[0]) + 1):
                candidates.append(strings[0][i:j])
        
        # Filter candidates that appear in all strings
        common = []
        for candidate in candidates:
            if all(candidate in s for s in strings[1:]):
                common.append(candidate)
        
        # Remove substrings that are contained within others
        filtered = []
        for i, s1 in enumerate(common):
            if not any(s1 in s2 and s1 != s2 for s2 in common):
                filtered.append(s1)
        
        return filtered
    
    def _is_significant_fix(self, fix):
        """Determine if a fix is significant enough to generate insights"""
        # Fixes with substantial analysis are usually significant
        if len(fix.get("analysis", "")) > 100:
            return True
            
        # Fixes with substantial code changes
        if "fixed_code" in fix:
            # Simple heuristic: code length changed by more than 10%
            original_code = fix.get("original_code", "")
            fixed_code = fix.get("fixed_code", "")
            
            if original_code and fixed_code:
                change_ratio = abs(len(fixed_code) - len(original_code)) / len(original_code)
                if change_ratio > 0.1:
                    return True
        
        # By default, consider most fixes worth learning from
        return True
    
    def _generate_insights(self, fix, test):
        """Generate insights from a fix using the LLM"""
        fix_type = fix.get("fix_type", "unknown")
        test_type = test.get("type", "unknown")
        test_complexity = test.get("complexity", "unknown")
        
        # Create a prompt for the LLM
        system_prompt = """
        You are a learning agent for a self-improving system.
        Your task is to analyze fixes and extract insights that can be applied in future situations.
        Focus on generalizable patterns and principles.
        """
        
        prompt = f"""
        I need to extract learning insights from a successful fix to a failed test.
        
        Test type: {test_type}
        Test complexity: {test_complexity}
        Fix type: {fix_type}
        
        Original test:
        ```python
        {test.get('code', 'No code available')}
        ```
        
        Fix analysis: {fix.get('analysis', 'No analysis available')}
        
        Fixed code:
        ```python
        {fix.get('fixed_code', 'No fixed code available')}
        ```
        
        Fix explanation: {fix.get('explanation', 'No explanation available')}
        
        Please provide insights about:
        1. What general principles can be learned from this fix?
        2. What patterns should we recognize in future tests?
        3. How might this knowledge be applied to other test types?
        
        Return your analysis as a JSON object with these fields:
        {{
            "principles": ["List of general principles learned"],
            "patterns": ["Recognizable patterns for future reference"],
            "applications": ["Ways to apply this knowledge elsewhere"]
        }}
        """
        
        # Query the model for insights
        response = self.query_model(prompt, system_prompt=system_prompt)
        
        # Parse the JSON response
        try:
            # Extract JSON from the response
            json_str = self._extract_json(response)
            insights = json.loads(json_str)
            return insights
        except Exception as e:
            self.logger.error(f"Error parsing insights response: {e}")
            return None
    
    def _generate_success_insights(self, test_type, patterns, test_results):
        """Generate insights from successful test patterns using the LLM"""
        # Select a few representative tests
        sample_tests = test_results[:3]
        
        # Create a prompt for the LLM
        system_prompt = """
        You are a learning agent for a self-improving system.
        Your task is to analyze successful tests and extract insights about what makes them work.
        Focus on generalizable patterns and principles.
        """
        
        prompt = f"""
        I need to extract learning insights from successful {test_type} tests.
        
        Patterns discovered:
        {json.dumps(patterns, indent=2)}
        
        Sample successful tests:
        
        {chr(10).join([f"Test {i+1}:\n```python\n{test.get('code', 'No code available')}\n```\nDescription: {test.get('description', 'No description')}" 
                    for i, (test, _) in enumerate(sample_tests)])}
        
        Please provide insights about:
        1. What general principles can be learned from these successful tests?
        2. What patterns should we recognize and replicate in future tests?
        3. How might we apply these insights to more complex tests?
        
        Return your analysis as a JSON object with these fields:
        {{
            "principles": ["List of general principles learned"],
            "patterns": ["Recognizable patterns for future reference"],
            "recommendations": ["Recommendations for future test development"]
        }}
        """
        
        # Query the model for insights
        response = self.query_model(prompt, system_prompt=system_prompt)
        
        # Parse the JSON response
        try:
            # Extract JSON from the response
            json_str = self._extract_json(response)
            insights = json.loads(json_str)
            return insights
        except Exception as e:
            self.logger.error(f"Error parsing success insights response: {e}")
            return None
    
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
    
    def _get_test_by_id(self, test_id):
        """Get a test by its ID from memory"""
        all_tests = self.memory.test_history.get("tests", [])
        for test in all_tests:
            if test.get("id") == test_id:
                return test
        return None
    
    def _update_learning_stats(self):
        """Update knowledge about learning progress"""
        self.memory.save_knowledge("learning_stats", {
            "learning_sessions": self.learning_sessions,
            "concepts_learned": self.concepts_learned,
            "rules_discovered": self.rules_discovered,
            "patterns": dict(self.patterns),
            "success_patterns": dict(self.success_patterns),
            "failure_patterns": dict(self.failure_patterns),
            "last_updated": time.time()
        })
    
    def _extract_first_insight(self, insights, default_message="Learned a new pattern"):
        """Safely extract the first insight from an insights object, with fallback handling"""
        if not insights:
            return default_message
            
        try:
            # If insights is a dictionary with lists
            if isinstance(insights, dict):
                # Try to get the first principle, pattern, or application
                for key in ['principles', 'patterns', 'applications', 'recommendations']:
                    if key in insights and insights[key] and isinstance(insights[key], list) and len(insights[key]) > 0:
                        return insights[key][0]
                
                # If no list fields found, try any string value
                for key, value in insights.items():
                    if isinstance(value, str) and value:
                        return value
                    elif isinstance(value, list) and value and isinstance(value[0], str):
                        return value[0]
                    
            # If insights is a list
            elif isinstance(insights, list):
                # Check if list has items
                if len(insights) > 0:
                    # If first item is a string, return it
                    if isinstance(insights[0], str):
                        return insights[0]
                    # If first item is a dict, try to extract a meaningful value
                    elif isinstance(insights[0], dict):
                        for key, value in insights[0].items():
                            if isinstance(value, str) and value:
                                return value
                
            # If insights is a string
            elif isinstance(insights, str):
                return insights
                
        except Exception as e:
            self.logger.error(f"Error extracting insight: {str(e)}")
            # Continue to fallback
            
        # Default fallback
        return default_message 