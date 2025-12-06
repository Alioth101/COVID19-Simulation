"""
Decision buffer manager for concurrent LLM decision making
Implements double-buffering pattern for realistic concurrent decisions

Author: COVID19_LLMbasedMultiAgentSystem Team
Date: 2025-10-11
"""

import time
from threading import Lock
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from covid_abs.llm.message import Decision


class DecisionBufferManager:
    """
    Manages temporary decision buffer for one iteration
    
    Design Pattern: Double Buffering
    - statuspool: Committed decisions (readable by all agents)
    - temp_buffer: Pending decisions (invisible to agents)
    
    This ensures all agents in the same iteration see the same world state,
    simulating realistic concurrent decision-making.
    """
    
    def __init__(self, status_pool):
        """
        Args:
            status_pool: Reference to StatusPool instance
        """
        self.status_pool = status_pool
        self.temp_buffer = []  # Pending decisions for current iteration
        self.current_iteration = None
        self.buffer_metadata = {}  # Stats, timestamps, etc.
        self._lock = Lock()  # 🔒 线程锁：保护temp_buffer并发访问
    
    def start_iteration(self, iteration: int):
        """
        Start a new iteration, clear temp buffer
        
        Args:
            iteration: Current iteration number
            
        Raises:
            RuntimeError: If previous buffer not flushed
        """
        if self.temp_buffer:
            raise RuntimeError(
                f"Cannot start iteration {iteration}: "
                f"Previous iteration's buffer not flushed! "
                f"{len(self.temp_buffer)} pending decisions."
            )
        
        self.current_iteration = iteration
        self.temp_buffer = []
        self.buffer_metadata = {
            'iteration': iteration,
            'start_time': time.time(),
            'agent_count': 0
        }
    
    def add_decision(self, decision: Decision):
        """
        Add a decision to temporary buffer (thread-safe)
        
        Args:
            decision: Decision instance
            
        Raises:
            ValueError: If iteration mismatch
        """
        with self._lock:  # 🔒 保护并发写入
            if decision.iteration != self.current_iteration:
                raise ValueError(
                    f"Decision iteration {decision.iteration} does not match "
                    f"current iteration {self.current_iteration}"
                )
            
            self.temp_buffer.append(decision)
            self.buffer_metadata['agent_count'] += 1
    
    def flush_to_statuspool(self):
        """
        Commit all buffered decisions to statuspool
        
        This is called AFTER all agents in current iteration have decided.
        
        Returns:
            int: Number of decisions committed
        """
        if not self.temp_buffer:
            # No decisions this iteration (all agents skipped)
            return 0
        
        # Batch append to statuspool
        for decision in self.temp_buffer:
            self.status_pool.append_decision(decision)
        
        # Record timing
        elapsed = time.time() - self.buffer_metadata.get('start_time', time.time())
        
        # Clear buffer
        decision_count = len(self.temp_buffer)
        self.temp_buffer = []
        self.current_iteration = None
        
        return decision_count
    
    def has_pending_decisions(self) -> bool:
        """Check if there are uncommitted decisions"""
        return len(self.temp_buffer) > 0
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about current buffer"""
        return {
            'iteration': self.current_iteration,
            'pending_count': len(self.temp_buffer),
            'metadata': self.buffer_metadata.copy()
        }


class ConcurrentDecisionExecutor:
    """
    Executes LLM decisions concurrently for multiple agents using thread pool
    
    Thread-based concurrency is ideal for I/O-bound LLM API calls.
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Args:
            max_workers: Maximum concurrent LLM calls
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False
    
    def execute_concurrent_decisions(
        self,
        agents: List,
        status_pool,
        iteration: int,
        experiment_id: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Execute LLM decisions concurrently for multiple agents
        
        Args:
            agents: List of agents that need to decide
            status_pool: StatusPool instance (read-only!)
            iteration: Current iteration
            experiment_id: Current experiment ID (for logging)
            
        Returns:
            List of decision results (same order as agents)
        """
        if self._shutdown:
            raise RuntimeError("Executor has been shut down")
        
        return self._execute_threaded(agents, status_pool, iteration, experiment_id)
    
    def _execute_threaded(self, agents, status_pool, iteration, experiment_id):
        """
        Thread-based concurrent execution
        
        Uses ThreadPoolExecutor to call LLM in parallel.
        Good for I/O-bound operations (network calls to OpenAI API).
        """
        import time
        import traceback
        from covid_abs.agents import Status, InfectionSeverity, AgentType
        
        def get_default_decision(agent):
            """
            Get safe default decision for an agent when LLM fails
            
            Strategy:
            - Person: 
                - Dead → StayHome
                - Hospitalized → StayHome
                - Has employer → GoToWork
                - No employer → StayHome
            - Business:
                - Always → KeepOpen (maintain operations)
            - Government:
                - Always → NoAction (maintain stability)
            
            Returns:
                Decision dict with action and reasoning
            """
            from covid_abs.llm.message import Decision
            
            if agent.type == AgentType.Person:
                # Default decision for Person
                if agent.status == Status.Death:
                    action = "StayHome"
                    reasoning = "[Default] Agent deceased - staying at location"
                elif agent.infected_status == InfectionSeverity.Hospitalization:
                    action = "StayHome"
                    reasoning = "[Default] Hospitalized - unable to move"
                elif agent.employer is not None:
                    action = "GoToWork"
                    reasoning = "[Default] Has employment - going to work"
                else:
                    action = "StayHome"
                    reasoning = "[Default] Unemployed - staying home"
                
                return Decision(
                    agent_id=agent.id,
                    iteration=iteration,
                    action=action,
                    reasoning=reasoning,
                    params={}
                )
                
            elif agent.type == AgentType.Business:
                # Default decision for Business
                return Decision(
                    agent_id=agent.id,
                    iteration=iteration,
                    action="KeepOpen",
                    reasoning="[Default] Maintaining business operations",
                    params={"open": True}
                )
                
            elif agent.type == AgentType.Government:
                # Default decision for Government
                return Decision(
                    agent_id=agent.id,
                    iteration=iteration,
                    action="NoAction",
                    reasoning="[Default] Maintaining current policies",
                    params={}
                )
            
            else:
                # Generic fallback
                return Decision(
                    agent_id=agent.id,
                    iteration=iteration,
                    action="NoAction",
                    reasoning="[Default] Unknown agent type - no action",
                    params={}
                )
        
        def make_decision(agent):
            """
            Wrapper function for thread pool with enhanced error handling
            
            Features:
            - Detailed error logging with full traceback
            - Automatic fallback to default decision on failure
            - Logs all failure details for post-experiment analysis
            """
            try:
                decision = agent.decide(status_pool)
                return {
                    'agent_id': agent.id,
                    'agent_type': agent.type.name if hasattr(agent.type, 'name') else str(agent.type),
                    'success': True,
                    'decision': decision,
                    'error': None,
                    'used_fallback': False
                }
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                
                # 🔧 [ENHANCED] 更详细的错误日志
                print(f"\n{'='*80}")
                print(f"[LLM Decision Failure - DETAILED DIAGNOSTICS]")
                print(f"{'='*80}")
                print(f"Agent ID: {agent.id}")
                print(f"Agent Type: {agent.type.name if hasattr(agent.type, 'name') else str(agent.type)}")
                print(f"Iteration: {iteration}")
                print(f"Day: {iteration // 24}, Hour: {iteration % 24}")
                print(f"Error Type: {error_type}")
                print(f"Error Message: {error_msg}")
                
                # 🔧 [ENHANCED] 详细的Agent状态
                print(f"\n--- Agent State Details ---")
                if hasattr(agent, 'status'):
                    print(f"Status: {agent.status.name if hasattr(agent.status, 'name') else str(agent.status)}")
                if hasattr(agent, 'infected_status'):
                    print(f"Infection Status: {agent.infected_status.name if hasattr(agent.infected_status, 'name') else 'None'}")
                if hasattr(agent, 'age'):
                    print(f"Age: {agent.age}")
                if hasattr(agent, 'wealth'):
                    print(f"Wealth: {agent.wealth:.2f}")
                if hasattr(agent, 'incomes'):
                    print(f"Income: {agent.incomes:.2f}")
                if hasattr(agent, 'expenses'):
                    print(f"Expenses: {agent.expenses:.2f}")
                if hasattr(agent, 'social_stratum'):
                    print(f"Social Stratum: Q{agent.social_stratum + 1}")
                if hasattr(agent, 'economical_status'):
                    print(f"Economic Status: {agent.economical_status.name if hasattr(agent.economical_status, 'name') else str(agent.economical_status)}")
                
                print(f"\n--- Relationships ---")
                if hasattr(agent, 'employer'):
                    if agent.employer:
                        print(f"Employer: ID={agent.employer.id}, Open={agent.employer.open if hasattr(agent.employer, 'open') else 'Unknown'}")
                    else:
                        print(f"Employer: None")
                if hasattr(agent, 'house'):
                    if agent.house:
                        print(f"House: ID={agent.house.id}, Wealth={agent.house.wealth if hasattr(agent.house, 'wealth') else 'Unknown':.2f}")
                    else:
                        print(f"House: None")
                
                print(f"\n--- Position ---")
                if hasattr(agent, 'x') and hasattr(agent, 'y'):
                    print(f"Position: ({agent.x:.2f}, {agent.y:.2f})")
                else:
                    print(f"Position: x={hasattr(agent, 'x')}, y={hasattr(agent, 'y')}")
                
                # Full traceback
                print(f"\n--- Full Traceback ---")
                print(traceback.format_exc())
                print(f"{'='*80}\n")
                
                # ❌ [数据完整性] 不使用fallback决策，直接返回失败
                # 实验将在graph_abs.py/abs.py层被中止，确保数据不失真
                return {
                    'agent_id': agent.id,
                    'agent_type': agent.type.name if hasattr(agent.type, 'name') else str(agent.type),
                    'success': False,
                    'decision': None,  # ✅ 不生成fallback
                    'error': error_msg,
                    'error_type': error_type,
                    'used_fallback': False,  # ✅ 明确标记
                    'full_traceback': traceback.format_exc()
                }
        
        # Submit all agent decisions to thread pool
        futures = {
            self.executor.submit(make_decision, agent): agent
            for agent in agents
        }
        
        # Collect results as they complete with timeout
        results = []
        timeout_per_agent = 120  # 120 seconds per agent (generous for DeepSeek)
        total_timeout = timeout_per_agent * len(agents)
        
        start_time = time.time()
        completed_count = 0
        
        try:
            for future in as_completed(futures, timeout=total_timeout):
                result = future.result(timeout=timeout_per_agent)
                results.append(result)
                
                completed_count += 1
                elapsed = time.time() - start_time
                avg_time = elapsed / completed_count
                remaining = len(agents) - completed_count
                eta = avg_time * remaining
                
                # Progress indicator every 5 agents
                if completed_count % 5 == 0 or completed_count == len(agents):
                    print(f"[LLM Progress][Exp #{experiment_id}] {completed_count}/{len(agents)} agents decided "
                          f"(avg: {avg_time:.1f}s/agent, ETA: {eta:.0f}s)")
                
        except TimeoutError:
            print(f"\n⚠️ [LLM Timeout] Only {len(results)}/{len(agents)} agents completed within {total_timeout}s")
            print(f"   This may indicate network issues or API rate limiting.")
            print(f"   Consider reducing MAX_CONCURRENT_LLM or checking your API connection.")
            
            # Cancel pending futures
            for future in futures:
                if not future.done():
                    future.cancel()
            
            # Use results we got so far
            if len(results) == 0:
                raise RuntimeError("No LLM decisions completed - check API connectivity")
        
        # Sort results to match original agent order
        agent_id_to_index = {agent.id: i for i, agent in enumerate(agents)}
        results.sort(key=lambda r: agent_id_to_index[r['agent_id']])
        
        # Statistics and logging
        total_agents = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = sum(1 for r in results if not r['success'])
        fallback_used = sum(1 for r in results if r.get('used_fallback', False))
        
        # Only print summary if there are failures
        if failed > 0:
            print(f"\n{'='*80}")
            print(f"[Decision Summary - Failures Detected]")
            print(f"{'='*80}")
            print(f"Iteration: {iteration} (Day {iteration // 24}, Hour {iteration % 24})")
            print(f"  Total agents: {total_agents}")
            print(f"  Successful: {successful} ({successful/total_agents*100:.1f}%)")
            print(f"  Failed (used fallback): {failed} ({failed/total_agents*100:.1f}%)")
            print(f"{'='*80}")
        
        # If any failures, save detailed failure log
        if failed > 0:
            import json
            import os
            from datetime import datetime
            
            # Prepare failure report
            failure_report = {
                'iteration': iteration,
                'day': iteration // 24,
                'hour': iteration % 24,
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_agents': total_agents,
                    'successful': successful,
                    'failed': failed,
                    'fallback_used': fallback_used
                },
                'failures': []
            }
            
            for r in results:
                if not r['success']:
                    failure_report['failures'].append({
                        'agent_id': r['agent_id'],
                        'agent_type': r['agent_type'],
                        'error_type': r.get('error_type', 'Unknown'),
                        'error_message': r.get('error', 'Unknown error'),
                        'fallback_action': r['decision'].action if r['decision'] else None,
                        'fallback_reasoning': r['decision'].reasoning if r['decision'] else None
                    })
            
            # Save to log file
            log_dir = 'output/llm_failure_logs'
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f'failures_iter_{iteration:04d}.json')
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(failure_report, f, indent=2, ensure_ascii=False)
            
            print(f"  Failure log saved: {log_file}")
            print()  # Empty line for readability
        
        return results
    
    def shutdown(self, wait: bool = True):
        """
        Cleanup resources
        
        Args:
            wait: If True, wait for all pending tasks to complete
        """
        if not self._shutdown:
            self.executor.shutdown(wait=wait)
            self._shutdown = True
    
    def __del__(self):
        """Ensure cleanup on object destruction"""
        if not self._shutdown:
            self.shutdown(wait=False)
