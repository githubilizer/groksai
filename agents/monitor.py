import logging
import json
import time
import os
import psutil
import threading
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
import subprocess

class Monitor(BaseAgent):
    def __init__(self, system_manager, memory_manager, model_name):
        super().__init__(system_manager, memory_manager, model_name)
        
        # Monitoring metrics
        self.checks_performed = 0
        self.alerts_raised = 0
        self.system_uptime = 0
        
        # Thresholds
        self.cpu_threshold = 90.0  # Alert if CPU usage is above 90%
        self.memory_threshold = 90.0  # Alert if memory usage is above 90%
        self.disk_threshold = 90.0  # Alert if disk usage is above 90%
        
        # Performance tracking
        self.performance_metrics = {
            "cpu_usage": [],
            "memory_usage": [],
            "disk_usage": [],
            "agent_response_times": {},
            "cycle_durations": []
        }
        
        # Health status
        self.last_health_check = time.time()
        self.current_health = {
            "healthy": True,
            "issues": []
        }
        
        # Background monitoring
        self.monitoring_thread = None
        self.monitoring_interval = 60  # seconds
        self.monitoring_active = False
        
    def initialize(self):
        """Initialize the monitor agent"""
        super().initialize()
        
        # Load previous monitoring stats
        monitor_stats = self.memory.get_knowledge("monitor_stats")
        if monitor_stats:
            self.checks_performed = monitor_stats.get("checks_performed", 0)
            self.alerts_raised = monitor_stats.get("alerts_raised", 0)
            self.system_uptime = monitor_stats.get("system_uptime", 0)
            
        # Start background monitoring
        self._start_background_monitoring()
            
        self.logger.info(f"Monitor initialized. Previous stats: {self.checks_performed} checks, {self.alerts_raised} alerts")
        return True
    
    def execute(self, *args, **kwargs):
        """Execute a health check"""
        return self.check_health()
    
    def check_health(self):
        """Check the health of the system and return a report"""
        self.logger.info("Running health check")
        
        issues = []
        
        # Check system resources
        resource_issues = self._check_system_resources()
        issues.extend(resource_issues)
        
        # Check memory status
        memory_issues = self._check_memory_status()
        issues.extend(memory_issues)
        
        # Check agent statuses
        agent_issues = self._check_agent_statuses()
        issues.extend(agent_issues)
        
        # Check circuit breakers
        circuit_issues = self._check_circuit_breakers()
        issues.extend(circuit_issues)
        
        # Check for error patterns
        error_issues = self._check_error_patterns()
        issues.extend(error_issues)
        
        # Check model availability
        model_issues = self._check_model_availability()
        issues.extend(model_issues)
        
        # Update stats
        self.health_checks += 1
        if issues:
            self.health_alerts += 1
            
        # Log any issues found
        if issues:
            for issue in issues:
                severity = issue.get('severity', 'unknown')
                message = issue.get('message', 'Unknown issue')
                self.logger.warning(f"Health alert: {message} (Severity: {severity})")
                
        # Save the health check results
        self.memory.save_knowledge("health_checks", {
            "timestamp": time.time(),
            "check_count": self.health_checks,
            "alert_count": self.health_alerts,
            "issues": issues
        })
        
        # Update monitor stats
        self.memory.save_knowledge("monitor_stats", {
            "health_checks": self.health_checks,
            "health_alerts": self.health_alerts,
            "last_check": time.time()
        })
        
        self.logger.info(f"Health check completed. Healthy: {len(issues) == 0}, Issues: {len(issues)}")
        
        return {
            "healthy": len(issues) == 0,
            "issues": issues
        }
    
    def _check_system_resources(self):
        """Check system resources like CPU, memory, and disk"""
        issues = []
        
        try:
            # Check disk space
            disk_usage = self._get_disk_usage()
            if disk_usage > 90:
                issues.append({
                    "type": "disk_usage",
                    "message": f"Disk usage is high: {disk_usage}%",
                    "severity": "high" if disk_usage > 95 else "medium",
                    "details": {"usage_percent": disk_usage}
                })
                
            # Check memory usage
            memory_usage = self._get_memory_usage()
            if memory_usage > 85:
                issues.append({
                    "type": "memory_usage",
                    "message": f"Memory usage is high: {memory_usage}%",
                    "severity": "high" if memory_usage > 95 else "medium",
                    "details": {"usage_percent": memory_usage}
                })
                
            # Check CPU usage
            cpu_usage = self._get_cpu_usage()
            if cpu_usage > 90:
                issues.append({
                    "type": "cpu_usage",
                    "message": f"CPU usage is high: {cpu_usage}%",
                    "severity": "medium",
                    "details": {"usage_percent": cpu_usage}
                })
                
            # Check if Ollama process is running
            if not self._is_ollama_running():
                issues.append({
                    "type": "ollama_process",
                    "message": "Ollama process is not running",
                    "severity": "high",
                    "details": {"service": "ollama"}
                })
        except Exception as e:
            self.logger.error(f"Error checking system resources: {str(e)}")
            issues.append({
                "type": "resource_check_error",
                "message": f"Error checking system resources: {str(e)}",
                "severity": "medium",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _check_memory_status(self):
        """Check the memory manager status"""
        issues = []
        
        try:
            # Check if memory backups exist
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
            if not os.path.exists(backup_dir) or not os.listdir(backup_dir):
                issues.append({
                    "type": "no_backups",
                    "message": "No memory backups found",
                    "severity": "low",
                    "details": {"backup_dir": backup_dir}
                })
                
            # Check knowledge base size
            knowledge_items = len(self.memory.get_knowledge() or {})
            if knowledge_items < 5:
                issues.append({
                    "type": "limited_knowledge",
                    "message": f"Knowledge base has few items: {knowledge_items}",
                    "severity": "low",
                    "details": {"item_count": knowledge_items}
                })
        except Exception as e:
            self.logger.error(f"Error checking memory status: {str(e)}")
            issues.append({
                "type": "memory_check_error",
                "message": f"Error checking memory status: {str(e)}",
                "severity": "low",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _check_agent_statuses(self):
        """Check the status of all agents"""
        issues = []
        
        try:
            system_status = self.system_manager.get_system_status()
            agents_status = system_status.get('agents', {})
            
            for agent_name, status in agents_status.items():
                # Check if agent is in a problematic state
                agent_status = status.get('status', 'unknown')
                if agent_status not in ['ready', 'running', 'waiting', 'initialized']:
                    issues.append({
                        "type": "agent_status",
                        "message": f"Agent {agent_name} has status: {agent_status}",
                        "severity": "medium",
                        "details": {"agent": agent_name, "status": agent_status}
                    })
                    
                # Check if agent has model failures
                model_failures = status.get('model_failures', 0)
                if model_failures > 0:
                    issues.append({
                        "type": "model_failures",
                        "message": f"Agent {agent_name} has {model_failures} model failures",
                        "severity": "medium" if model_failures > 2 else "low",
                        "details": {"agent": agent_name, "failures": model_failures}
                    })
                    
                # Check last action time to see if agent is stalled
                last_action = status.get('last_action', 0)
                if last_action > 300:  # 5 minutes without action
                    issues.append({
                        "type": "stalled_agent",
                        "message": f"Agent {agent_name} has not acted in {int(last_action/60)} minutes",
                        "severity": "high" if last_action > 600 else "medium",  # Higher severity if >10 min
                        "details": {"agent": agent_name, "last_action_seconds": last_action}
                    })
        except Exception as e:
            self.logger.error(f"Error checking agent statuses: {str(e)}")
            issues.append({
                "type": "agent_check_error",
                "message": f"Error checking agent statuses: {str(e)}",
                "severity": "medium",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _check_circuit_breakers(self):
        """Check the status of circuit breakers"""
        issues = []
        
        try:
            # Check which circuit breakers are tripped
            tripped_breakers = []
            for agent_name, tripped in self.system_manager.circuit_breakers.items():
                if tripped:
                    tripped_breakers.append(agent_name)
                    
            if tripped_breakers:
                # If multiple breakers are tripped, this is more severe
                severity = "high" if len(tripped_breakers) > 1 else "medium"
                
                issues.append({
                    "type": "circuit_breakers_tripped",
                    "message": f"Circuit breakers tripped for: {', '.join(tripped_breakers)}",
                    "severity": severity,
                    "details": {"agents": tripped_breakers}
                })
                
            # Check if all circuit breakers are tripped
            if len(tripped_breakers) == len(self.system_manager.agents):
                issues.append({
                    "type": "all_circuit_breakers_tripped",
                    "message": "All circuit breakers are tripped, system is completely stalled",
                    "severity": "critical",
                    "details": {"agents": tripped_breakers}
                })
        except Exception as e:
            self.logger.error(f"Error checking circuit breakers: {str(e)}")
            issues.append({
                "type": "circuit_breaker_check_error",
                "message": f"Error checking circuit breakers: {str(e)}",
                "severity": "medium",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _check_error_patterns(self):
        """Check for recurring error patterns"""
        issues = []
        
        try:
            # Get error history from system manager
            error_history = self.system_manager.error_history if hasattr(self.system_manager, 'error_history') else {}
            
            # Check for high-frequency errors
            high_frequency_errors = []
            for error_type, error_data in error_history.items():
                count = error_data.get('count', 0)
                last_seen = error_data.get('last_seen', 0)
                current_time = time.time()
                
                # If error occurred many times recently
                if count > 10 and (current_time - last_seen) < 3600:  # More than 10 times in last hour
                    high_frequency_errors.append({
                        "type": error_type,
                        "count": count,
                        "details": error_data.get('details', '')[:100]
                    })
            
            if high_frequency_errors:
                issues.append({
                    "type": "recurring_errors",
                    "message": f"Detected {len(high_frequency_errors)} types of recurring errors",
                    "severity": "high" if len(high_frequency_errors) > 3 else "medium",
                    "details": {"errors": high_frequency_errors}
                })
                
            # Check for system exceptions
            if 'system_exception' in error_history:
                system_exc_data = error_history['system_exception']
                count = system_exc_data.get('count', 0)
                last_seen = system_exc_data.get('last_seen', 0)
                current_time = time.time()
                
                # If system exception happened recently
                if (current_time - last_seen) < 1800:  # Last 30 minutes
                    issues.append({
                        "type": "system_exceptions",
                        "message": f"System experienced {count} exceptions, most recent: {system_exc_data.get('details', '')[:100]}",
                        "severity": "high",
                        "details": {"count": count, "last_seen": last_seen}
                    })
                    
            # Check for unfixable tests
            unfixable_tests = error_history.get('unfixable_test', {}).get('count', 0)
            if unfixable_tests > 5:
                issues.append({
                    "type": "unfixable_tests",
                    "message": f"System has {unfixable_tests} tests that could not be fixed",
                    "severity": "medium",
                    "details": {"count": unfixable_tests}
                })
        except Exception as e:
            self.logger.error(f"Error checking error patterns: {str(e)}")
            issues.append({
                "type": "error_pattern_check_error",
                "message": f"Error checking error patterns: {str(e)}",
                "severity": "low",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _check_model_availability(self):
        """Check if the configured Ollama model is available"""
        issues = []
        
        try:
            model_name = self.system_manager.model_name
            
            # Check if Ollama is running first
            if not self._is_ollama_running():
                issues.append({
                    "type": "ollama_not_running",
                    "message": "Ollama service is not running",
                    "severity": "critical",
                    "details": {"model": model_name}
                })
                return issues
                
            # Check if the model is available
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                text=True,
                check=False,
                timeout=10
            )
            
            if model_name not in result.stdout:
                issues.append({
                    "type": "model_not_available",
                    "message": f"Model {model_name} is not available in Ollama",
                    "severity": "high",
                    "details": {"model": model_name, "available_models": result.stdout}
                })
        except subprocess.TimeoutExpired:
            issues.append({
                "type": "ollama_timeout",
                "message": "Timeout checking Ollama model availability",
                "severity": "high",
                "details": {"model": self.system_manager.model_name}
            })
        except Exception as e:
            self.logger.error(f"Error checking model availability: {str(e)}")
            issues.append({
                "type": "model_check_error",
                "message": f"Error checking model availability: {str(e)}",
                "severity": "medium",
                "details": {"error": str(e)}
            })
            
        return issues
    
    def _get_disk_usage(self):
        """Get disk usage percentage"""
        try:
            if os.name == 'posix':  # Linux/Unix
                result = subprocess.run(['df', '-h', '.'], capture_output=True, text=True)
                # Parse the output to get disk usage percentage
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    fields = lines[1].split()
                    if len(fields) >= 5:
                        # Remove the % character
                        return float(fields[4].replace('%', ''))
            
            # Fallback to os.statvfs
            statvfs = os.statvfs('.')
            total = statvfs.f_blocks * statvfs.f_frsize
            free = statvfs.f_bfree * statvfs.f_frsize
            used = total - free
            return round((used / total) * 100, 1)
        except Exception as e:
            self.logger.error(f"Error getting disk usage: {str(e)}")
            return 0  # Return 0 on error
    
    def _get_memory_usage(self):
        """Get memory usage percentage"""
        try:
            if os.name == 'posix':  # Linux/Unix
                result = subprocess.run(['free', '-m'], capture_output=True, text=True)
                # Parse the output to get memory usage percentage
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    fields = lines[1].split()
                    if len(fields) >= 3:
                        total = float(fields[1])
                        used = float(fields[2])
                        return round((used / total) * 100, 1)
            
            # Fallback
            return 50  # Return a default value
        except Exception as e:
            self.logger.error(f"Error getting memory usage: {str(e)}")
            return 0  # Return 0 on error
    
    def _get_cpu_usage(self):
        """Get CPU usage percentage"""
        try:
            # This is a simple method that works on most Unix systems
            result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if '%Cpu' in line:
                    # Extract the CPU usage percentage
                    parts = line.split(',')
                    for part in parts:
                        if 'id' in part:  # idle percentage
                            idle = float(part.split()[0])
                            return round(100 - idle, 1)
            
            # Fallback
            return 30  # Return a default value
        except Exception as e:
            self.logger.error(f"Error getting CPU usage: {str(e)}")
            return 0  # Return 0 on error
    
    def _is_ollama_running(self):
        """Check if the Ollama process is running"""
        try:
            # Check for the ollama process
            if os.name == 'posix':  # Linux/Unix
                result = subprocess.run(['pgrep', 'ollama'], capture_output=True, text=True)
                return result.returncode == 0
                
            # Try a basic connection test as fallback
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error checking if Ollama is running: {str(e)}")
            return False
    
    def _start_background_monitoring(self):
        """Start background monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return  # Already running
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._background_monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        self.logger.info("Started background monitoring thread")
    
    def _stop_background_monitoring(self):
        """Stop the background monitoring thread"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10.0)
            self.logger.info("Stopped background monitoring thread")
    
    def _background_monitoring_loop(self):
        """Background thread that periodically monitors system health"""
        while self.monitoring_active:
            try:
                # Sleep for the monitoring interval
                time.sleep(self.monitoring_interval)
                
                # Skip if the system is not running
                if not self.system_manager.running:
                    continue
                
                # Perform a quick system health check
                system_health = self._check_system_health()
                
                # If there are high severity issues, run a full health check
                high_severity_issues = [i for i in system_health.get("issues", []) if i.get("severity") == "high"]
                
                if high_severity_issues:
                    self.logger.warning("Background monitor detected high severity issues, running full health check")
                    self.check_health()
                    
            except Exception as e:
                self.logger.error(f"Error in background monitoring: {str(e)}")
                time.sleep(30)  # Sleep a bit longer if there was an error 