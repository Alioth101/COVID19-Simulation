"""
Base class for LLM backend abstraction
Adapted from AgentReview project's backend design
"""

from typing import List, Dict, Any
from abc import ABC, abstractmethod


class IntelligenceBackend(ABC):
    """
    Abstract base class for LLM backends.
    Provides unified interface for different LLM providers (OpenAI, Anthropic, etc.)
    """
    
    def __init__(self, model_name: str, temperature: float = 0.7, max_tokens: int = 2000):
        """
        Initialize the backend
        
        Args:
            model_name: Name of the model to use (e.g., "gpt-4o-mini")
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum tokens in response
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    def query(
        self,
        agent_name: str,
        role_desc: str,
        history_messages: List[Dict[str, str]],
        global_prompt: str,
        request_msg: str
    ) -> str:
        """
        Query the LLM backend
        
        Args:
            agent_name: Identifier of the agent making the query
            role_desc: Role description (system prompt component)
            history_messages: Previous decisions/messages for context
            global_prompt: Global instructions for all agents
            request_msg: Specific decision request
            
        Returns:
            str: LLM response (typically JSON-formatted decision)
        """
        raise NotImplementedError("Subclass must implement query()")
    
    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model_name}, temp={self.temperature})"
