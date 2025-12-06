"""
Concurrent-safe console logger for economic debugging

This module provides buffered logging for concurrent execution,
ensuring logs are output in order despite parallel processing.
"""

import threading
from typing import List, Tuple
import sys

class ConcurrentConsoleLogger:
    """Thread-safe buffered console logger"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.enabled = False
        self.buffer = {}  # iteration -> list of messages
        self.last_printed_iteration = -1
        self._lock = threading.Lock()
    
    def initialize(self, enabled: bool):
        """Initialize the logger"""
        self.enabled = enabled
        self.buffer = {}
        self.last_printed_iteration = -1
    
    def log(self, iteration: int, message: str):
        """Add a log message to the buffer"""
        if not self.enabled:
            print(message)  # Direct print if not enabled
            return
            
        with self._lock:
            if iteration not in self.buffer:
                self.buffer[iteration] = []
            self.buffer[iteration].append(message)
            
            # Try to flush any complete iterations
            self._flush_ready_iterations()
    
    def _flush_ready_iterations(self):
        """Flush iterations that are ready (in order)"""
        while True:
            next_iter = self.last_printed_iteration + 1
            if next_iter in self.buffer:
                # Print all messages for this iteration
                for msg in self.buffer[next_iter]:
                    print(msg)
                del self.buffer[next_iter]
                self.last_printed_iteration = next_iter
            else:
                # No more consecutive iterations ready
                break
    
    def flush_all(self):
        """Force flush all buffered messages (at experiment end)"""
        if not self.enabled:
            return
            
        with self._lock:
            # Sort and print all remaining iterations
            for iteration in sorted(self.buffer.keys()):
                if iteration > self.last_printed_iteration:
                    for msg in self.buffer[iteration]:
                        print(msg)
            self.buffer.clear()

# Global instance
console_logger = ConcurrentConsoleLogger()
