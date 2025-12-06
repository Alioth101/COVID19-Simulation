"""
Mock LLM Backend for testing without real API calls

This mock backend simulates LLM responses for testing purposes
"""

import json
import random
from covid_abs.llm.base import IntelligenceBackend


class MockLLMBackend(IntelligenceBackend):
    """Mock LLM backend that returns predefined responses"""
    
    def __init__(self, should_fail=False, fail_rate=0.0):
        """
        Initialize mock backend
        
        Args:
            should_fail: If True, always fails
            fail_rate: Probability of failure (0.0 to 1.0)
        """
        super().__init__(model_name="mock-model", temperature=0.0, max_tokens=100)
        self.should_fail = should_fail
        self.fail_rate = fail_rate
        self.call_count = 0
        
    def query(self, agent_name, role_desc, history_messages, global_prompt, request_msg):
        """
        Simulate LLM query with mock response
        
        Args:
            agent_name: Agent identifier
            role_desc: Role description
            history_messages: Previous messages
            global_prompt: Global instructions
            request_msg: Current request
            
        Returns:
            JSON-formatted decision string
        """
        self.call_count += 1
        
        # Simulate failures
        if self.should_fail or (self.fail_rate > 0 and random.random() < self.fail_rate):
            raise RuntimeError("Mock backend failure (simulated)")
        
        # Extract iteration number from request to vary responses
        iteration = self._extract_iteration(request_msg)
        
        # Return realistic decision
        actions = ['StayAction', 'MoveRandomAction', 'MoveToLocationAction']
        
        # Bias towards StayAction for simplicity
        if iteration % 2 == 0:
            action = 'StayAction'
            reasoning = f"Staying put to observe the situation (iteration {iteration})"
            params = {}
        else:
            action = random.choice(['MoveRandomAction', 'MoveToLocationAction'])
            if action == 'MoveRandomAction':
                reasoning = f"Moving randomly to explore (iteration {iteration})"
                params = {}
            else:
                reasoning = f"Moving to specific location (iteration {iteration})"
                params = {'x': random.randint(10, 90), 'y': random.randint(10, 90)}
        
        decision = {
            "action": action,
            "params": params,
            "reasoning": reasoning
        }
        
        return json.dumps(decision)
    
    def _extract_iteration(self, message):
        """Extract iteration number from message"""
        import re
        match = re.search(r'iteration[:\s]+(\d+)', message.lower())
        if match:
            return int(match.group(1))
        return 0
    
    def __str__(self):
        return f"MockLLMBackend(calls={self.call_count})"
    
    def __repr__(self):
        return self.__str__()
