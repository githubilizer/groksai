import logging
import json
import time
import traceback
import importlib.util
import sys
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from agents.base_agent import BaseAgent

class Tester(BaseAgent):
    def __init__(self, system_manager, memory_manager, model_name):
        super().__init__(system_manager, memory_manager, model_name)
        
        # Testing metrics
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        
        # Execution environment setup
        self.test_env = {}
        self.max_workers = 3  # Max parallel test executions
        
    def initialize(self):
        """Initialize the tester"""
        super().initialize()
        
        # Create test execution environment
        self._setup_test_environment()
        
        # Load previous testing stats if available
        test_stats = self.memory.get_knowledge("test_execution_stats")
        if test_stats:
            self.tests_run = test_stats.get("tests_run", 0)
            self.tests_passed = test_stats.get("tests_passed", 0)
            self.tests_failed = test_stats.get("tests_failed", 0)
            
        self.logger.info(f"Tester initialized. Previous stats: {self.tests_run} run, {self.tests_passed} passed, {self.tests_failed} failed")
        return True
    
    def execute(self, *args, **kwargs):
        """Execute the test running process"""
        tests = kwargs.get("tests", [])
        if not tests and args and isinstance(args[0], list):
            tests = args[0]
        return self.run_tests(tests)
    
    def run_tests(self, tests):
        """Run a batch of tests and return results"""
        if not tests:
            self.logger.warning("No tests provided to run")
            return []
            
        self.status = "testing"
        self.log_action("run_tests", {"count": len(tests)})
        
        # Run tests in parallel with timeout protection
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_test = {executor.submit(self._run_single_test, test): test for test in tests}
            for future in future_to_test:
                test = future_to_test[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Save result to memory
                    self.memory.save_test_result(test["id"], result)
                    
                    # Update stats
                    self.tests_run += 1
                    if result["passed"]:
                        self.tests_passed += 1
                    else:
                        self.tests_failed += 1
                        
                except Exception as e:
                    self.logger.error(f"Error running test {test.get('id')}: {str(e)}")
                    error_result = {
                        "test_id": test.get("id"),
                        "passed": False,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "timestamp": time.time(),
                        "execution_time": 0
                    }
                    results.append(error_result)
                    self.memory.save_test_result(test["id"], error_result)
                    self.tests_run += 1
                    self.tests_failed += 1
        
        # Update knowledge about test execution
        self._update_test_execution_knowledge()
        
        self.status = "ready"
        self.logger.info(f"Completed running {len(tests)} tests. Passed: {sum(1 for r in results if r['passed'])}, Failed: {sum(1 for r in results if not r['passed'])}")
        return results
    
    def _run_single_test(self, test):
        """Run a single test with timeout protection"""
        test_id = test.get("id", "unknown")
        test_name = test.get("name", f"Test {test_id}")
        test_type = test.get("type", "unknown")
        timeout = test.get("timeout_seconds", 30)
        
        self.logger.info(f"Running test {test_id}: {test_name} (type: {test_type})")
        
        start_time = time.time()
        result = {
            "test_id": test_id,
            "passed": False,
            "timestamp": start_time,
            "execution_time": 0
        }
        
        try:
            # Execute the test based on its type
            if test_type == "function":
                test_result = self._run_function_test(test)
            elif test_type == "integration":
                test_result = self._run_integration_test(test)
            elif test_type == "system":
                test_result = self._run_system_test(test)
            elif test_type == "performance":
                test_result = self._run_performance_test(test)
            else:
                test_result = self._run_generic_test(test)
            
            execution_time = time.time() - start_time
            
            # Update result
            result.update({
                "passed": test_result.get("passed", False),
                "output": test_result.get("output", None),
                "details": test_result.get("details", {}),
                "execution_time": execution_time
            })
            
            if not test_result.get("passed", False):
                result["failure_reason"] = test_result.get("failure_reason", "Unknown failure")
                
        except TimeoutError:
            execution_time = time.time() - start_time
            result.update({
                "passed": False,
                "failure_reason": f"Test timed out after {timeout} seconds",
                "execution_time": execution_time
            })
        except Exception as e:
            execution_time = time.time() - start_time
            result.update({
                "passed": False,
                "failure_reason": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            })
        
        self.logger.info(f"Test {test_id} completed in {result['execution_time']:.2f}s. Passed: {result['passed']}")
        return result
    
    def _setup_test_environment(self):
        """Set up the test execution environment"""
        # Add test directory to import path if needed
        test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
        
        if test_dir not in sys.path:
            sys.path.append(test_dir)
        
        self.test_env = {
            "test_dir": test_dir
        }
        
        return self.test_env
    
    def _run_function_test(self, test):
        """Run a function test by executing code"""
        code = test.get("code", "")
        inputs = test.get("inputs", {})
        success_criteria = test.get("success_criteria", "")
        
        # Create a temporary module to execute the code
        spec = importlib.util.spec_from_loader("test_module", loader=None)
        test_module = importlib.util.module_from_spec(spec)
        
        try:
            # Execute the code in the module
            exec(code, test_module.__dict__)
            
            # Try to identify the main function to call
            main_function = None
            for name, obj in test_module.__dict__.items():
                if callable(obj) and (name.startswith("test_") or name == "main"):
                    main_function = obj
                    break
            
            # If we found a main function, call it with inputs
            if main_function:
                # Log function parameters for debugging
                import inspect
                sig = inspect.signature(main_function)
                param_names = list(sig.parameters.keys())
                self.logger.info(f"Function '{main_function.__name__}' expects parameters: {param_names}")
                self.logger.info(f"Test inputs: {inputs}")
                
                # Check for parameter mismatch
                if isinstance(inputs, dict) and param_names:
                    if set(inputs.keys()) != set(param_names):
                        self.logger.warning(f"Parameter name mismatch in test {test.get('id')}: function expects {param_names}, but inputs has {list(inputs.keys())}")
                
                # Execute the function
                try:
                    if isinstance(inputs, dict):
                        output = main_function(**inputs)
                    else:
                        output = main_function(inputs)
                        
                    # Evaluate if the output meets success criteria
                    result = {
                        "output": output,
                        "details": {"type": "function_test"}
                    }
                    
                    # Check success criteria
                    success = self._evaluate_success(output, success_criteria, test_module.__dict__)
                    result["passed"] = success
                    
                    if not success:
                        result["failure_reason"] = f"Output did not meet success criteria: {success_criteria}"
                    
                    return result
                except TypeError as e:
                    # Detailed error for parameter mismatch
                    self.logger.error(f"Parameter error in test {test.get('id')}: {str(e)}")
                    return {
                        "passed": False,
                        "failure_reason": str(e),
                        "details": {
                            "type": "parameter_mismatch",
                            "function_params": param_names,
                            "input_keys": list(inputs.keys()) if isinstance(inputs, dict) else "non-dict input"
                        }
                    }
            else:
                return {
                    "passed": False,
                    "failure_reason": "No test function found in code",
                    "details": {"type": "missing_function"}
                }
        except Exception as e:
            self.logger.error(f"Error in test execution: {str(e)}")
            return {
                "passed": False,
                "failure_reason": str(e),
                "traceback": traceback.format_exc(),
                "details": {"type": "execution_error"}
            }
    
    def _run_integration_test(self, test):
        """Run an integration test involving multiple components"""
        # Integration tests are similar to function tests but involve multiple components
        return self._run_function_test(test)
    
    def _run_system_test(self, test):
        """Run a system test involving the entire system"""
        # For system tests, we might need to use the system manager
        code = test.get("code", "")
        inputs = test.get("inputs", {})
        
        try:
            # Create a local context with access to the system manager
            local_context = {
                "system_manager": self.system_manager,
                "inputs": inputs
            }
            
            # Execute the test code with access to the system
            exec(code, globals(), local_context)
            
            # Check if the test explicitly set a result
            if "result" in local_context:
                result = local_context["result"]
                passed = result.get("passed", False)
                return result
            
            # Otherwise evaluate based on success criteria
            success_criteria = test.get("success_criteria", "")
            success = self._evaluate_success(local_context, success_criteria, local_context)
            
            return {
                "passed": success,
                "output": str(local_context),
                "details": {},
                "failure_reason": "" if success else f"System test did not meet criteria: {success_criteria}"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "output": None,
                "failure_reason": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _run_performance_test(self, test):
        """Run a performance test measuring execution time or resources"""
        code = test.get("code", "")
        inputs = test.get("inputs", {})
        success_criteria = test.get("success_criteria", "")
        iterations = inputs.get("iterations", 1)
        
        try:
            # Create a test module
            spec = importlib.util.spec_from_loader("perf_test", loader=None)
            test_module = importlib.util.module_from_spec(spec)
            
            # Execute the setup code
            exec(code, test_module.__dict__)
            
            # Find the main function to benchmark
            main_function = None
            for name, obj in test_module.__dict__.items():
                if callable(obj) and (name.startswith("test_") or name == "main" or name == "benchmark"):
                    main_function = obj
                    break
            
            if not main_function:
                return {
                    "passed": False,
                    "output": None,
                    "failure_reason": "No benchmark function found in performance test"
                }
            
            # Run the benchmark
            start_time = time.time()
            results = []
            
            for i in range(iterations):
                iteration_start = time.time()
                
                if isinstance(inputs, dict) and "args" in inputs:
                    output = main_function(*inputs["args"])
                elif isinstance(inputs, dict):
                    # Filter out special keys like 'iterations'
                    function_inputs = {k: v for k, v in inputs.items() if k != "iterations"}
                    output = main_function(**function_inputs)
                else:
                    output = main_function(inputs)
                
                iteration_time = time.time() - iteration_start
                results.append({
                    "iteration": i,
                    "time": iteration_time,
                    "output": str(output)
                })
            
            total_time = time.time() - start_time
            avg_time = total_time / iterations if iterations > 0 else 0
            
            # Evaluate success based on criteria and performance data
            performance_data = {
                "total_time": total_time,
                "average_time": avg_time,
                "iterations": iterations,
                "results": results
            }
            
            # Check if it meets performance criteria
            success = self._evaluate_performance(performance_data, success_criteria)
            
            return {
                "passed": success,
                "output": performance_data,
                "details": {"average_time": avg_time, "total_time": total_time},
                "failure_reason": "" if success else f"Performance did not meet criteria: {success_criteria}"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "output": None,
                "failure_reason": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _run_generic_test(self, test):
        """Run a generic test when the type is unknown"""
        # Default to function test behavior
        return self._run_function_test(test)
    
    def _evaluate_success(self, output, criteria, context=None):
        """Evaluate if the test output meets the success criteria"""
        if not criteria:
            return True  # No criteria means success
            
        context = context or {}
        context["output"] = output
        
        try:
            # First try to evaluate as a Python expression
            result = eval(criteria, {"__builtins__": {}}, context)
            if isinstance(result, bool):
                return result
        except:
            # If that fails, use a more general approach
            if isinstance(output, (str, int, float, bool)):
                # Simple string contains check
                if isinstance(criteria, str) and isinstance(output, str):
                    return criteria in output or output == criteria
                # Numeric comparison
                elif isinstance(output, (int, float)) and isinstance(criteria, (int, float)):
                    return output == criteria
            
            # Check if criteria appears in string representation
            return str(criteria) in str(output)
    
    def _evaluate_performance(self, perf_data, criteria):
        """Evaluate if performance data meets criteria"""
        if not criteria:
            return True
            
        # Try to evaluate criteria as an expression
        try:
            # Create a context with performance data
            context = {
                "total_time": perf_data["total_time"],
                "average_time": perf_data["average_time"],
                "iterations": perf_data["iterations"]
            }
            
            # Evaluate the criteria
            return eval(criteria, {"__builtins__": {}}, context)
        except:
            # Fallback to simple string comparison
            return str(criteria) in str(perf_data)
    
    def _update_test_execution_knowledge(self):
        """Update knowledge about test execution stats"""
        self.memory.save_knowledge("test_execution_stats", {
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "pass_rate": self.tests_passed / self.tests_run if self.tests_run > 0 else 0,
            "last_updated": time.time()
        }) 