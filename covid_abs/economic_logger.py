"""
Economic Debug Logger for COVID-19 Multi-Agent System

This module provides comprehensive logging of all economic transactions
to help diagnose wealth conservation issues and Government accounting problems.
"""

import json
import os
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading
from collections import OrderedDict

class EconomicLogger:
    """Singleton logger for economic transactions"""
    
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
        self.logs = []
        self.wealth_snapshots = []
        self.accounting_details = []
        self.transaction_id = 0
        self.output_file = None
        self._lock = threading.Lock()
    
    def initialize(self, enabled: bool, output_dir: str = "output"):
        """Initialize the logger with settings"""
        self.enabled = enabled
        if enabled:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = os.path.join(output_dir, f"economic_debug_{timestamp}.json")
            print(f"💰 Economic Debug Logger initialized: {self.output_file}")
            self.logs = []
            self.wealth_snapshots = []
            self.accounting_details = []
            self.transaction_id = 0
    
    def log_transaction(self, 
                        iteration: int,
                        source_type: str,
                        source_id: str,
                        target_type: str,
                        target_id: str,
                        amount: float,
                        transaction_type: str,
                        details: Optional[Dict] = None):
        """Log a single economic transaction"""
        if not self.enabled:
            return
            
        with self._lock:
            self.transaction_id += 1
            
            log_entry = {
                "id": self.transaction_id,
                "iteration": iteration,
                "day": iteration // 24,
                "hour": iteration % 24,
                "source": {
                    "type": source_type,
                    "id": str(source_id)[:8] if source_id else "N/A"
                },
                "target": {
                    "type": target_type,
                    "id": str(target_id)[:8] if target_id else "N/A"
                },
                "amount": amount,
                "type": transaction_type,
                "details": details or {}
            }
            
            self.logs.append(log_entry)
    
    def log_wealth_snapshot(self, 
                           iteration: int,
                           wealth_data: Dict[str, float],
                           event: str = ""):
        """Log a snapshot of system wealth distribution"""
        if not self.enabled:
            return
            
        with self._lock:
            snapshot = {
                "iteration": iteration,
                "day": iteration // 24,
                "hour": iteration % 24,
                "event": event,
                "wealth": wealth_data,
                "total": sum(wealth_data.values())
            }
            
            self.wealth_snapshots.append(snapshot)
    
    def log_accounting(self,
                      iteration: int,
                      agent_type: str,
                      agent_id: str,
                      details: Dict[str, Any]):
        """Log detailed accounting information"""
        if not self.enabled:
            return
            
        with self._lock:
            accounting_entry = {
                "iteration": iteration,
                "day": iteration // 24,
                "hour": iteration % 24,
                "agent": {
                    "type": agent_type,
                    "id": str(agent_id)[:8] if agent_id else "N/A"
                },
                "details": details
            }
            
            self.accounting_details.append(accounting_entry)
    
    def log_government_accounting(self,
                                 iteration: int,
                                 gov_id: str,
                                 wealth_before: float,
                                 wealth_after: float,
                                 healthcare_expense: float,
                                 healthcare_paid: float,
                                 unemployed_count: int,
                                 unemployed_expenses: List[float],
                                 unemployed_paid: float,
                                 homeless_count: int,
                                 homeless_expenses: List[float],
                                 homeless_paid: float):
        """Log detailed Government accounting"""
        if not self.enabled:
            return
            
        details = {
            "wealth_before": wealth_before,
            "wealth_after": wealth_after,
            "total_spent": wealth_before - wealth_after,
            "healthcare": {
                "expense_recorded": healthcare_expense,
                "amount_paid": healthcare_paid,
                "discrepancy": healthcare_expense - healthcare_paid
            },
            "unemployed": {
                "count": unemployed_count,
                "expenses": {
                    "min": min(unemployed_expenses) if unemployed_expenses else 0,
                    "max": max(unemployed_expenses) if unemployed_expenses else 0,
                    "avg": sum(unemployed_expenses) / len(unemployed_expenses) if unemployed_expenses else 0,
                    "total": sum(unemployed_expenses)
                },
                "amount_paid": unemployed_paid,
                "discrepancy": sum(unemployed_expenses) - unemployed_paid if unemployed_expenses else 0
            },
            "homeless": {
                "count": homeless_count,
                "expenses": {
                    "min": min(homeless_expenses) if homeless_expenses else 0,
                    "max": max(homeless_expenses) if homeless_expenses else 0,
                    "avg": sum(homeless_expenses) / len(homeless_expenses) if homeless_expenses else 0,
                    "total": sum(homeless_expenses)
                },
                "amount_paid": homeless_paid,
                "discrepancy": sum(homeless_expenses) - homeless_paid if homeless_expenses else 0
            },
            "wealth_conservation": {
                "expected_spent": healthcare_paid + unemployed_paid + homeless_paid,
                "actual_spent": wealth_before - wealth_after,
                "discrepancy": (wealth_before - wealth_after) - (healthcare_paid + unemployed_paid + homeless_paid)
            }
        }
        
        self.log_accounting(iteration, "Government", gov_id, details)
    
    def log_person_expenses(self,
                           iteration: int,
                           person_id: str,
                           expenses: float,
                           social_stratum: int,
                           employed: bool,
                           has_house: bool,
                           context: str = ""):
        """Log Person expenses values for tracking"""
        if not self.enabled:
            return
            
        with self._lock:
            log_entry = {
                "id": self.transaction_id,
                "iteration": iteration,
                "day": iteration // 24,
                "hour": iteration % 24,
                "type": "PERSON_EXPENSES",
                "person_id": str(person_id)[:8],
                "expenses": expenses,
                "social_stratum": social_stratum,
                "employed": employed,
                "has_house": has_house,
                "context": context
            }
            
            self.logs.append(log_entry)
    
    def _convert_numpy(self, obj):
        """Recursively convert NumPy types to native Python types"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy(val) for key, val in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_numpy(item) for item in obj]
        else:
            return obj
    
    def save(self):
        """Save all logs to file (sorted by iteration for concurrent compatibility)"""
        if not self.enabled or not self.output_file:
            return
            
        with self._lock:
            # Sort logs by iteration to ensure order despite concurrent execution
            sorted_logs = sorted(self.logs, key=lambda x: (x.get('iteration', 0), x.get('id', 0)))
            sorted_snapshots = sorted(self.wealth_snapshots, key=lambda x: x.get('iteration', 0))
            sorted_accounting = sorted(self.accounting_details, key=lambda x: x.get('iteration', 0))
            
            # Convert all NumPy types to native Python types
            sorted_logs = self._convert_numpy(sorted_logs)
            sorted_snapshots = self._convert_numpy(sorted_snapshots)
            sorted_accounting = self._convert_numpy(sorted_accounting)
            
            output = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_transactions": len(sorted_logs),
                    "total_snapshots": len(sorted_snapshots),
                    "total_accounting": len(sorted_accounting)
                },
                "transactions": sorted_logs,
                "wealth_snapshots": sorted_snapshots,
                "accounting_details": sorted_accounting
            }
            
            # Convert the entire output to ensure all values are JSON serializable
            output = self._convert_numpy(output)
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Economic debug log saved: {self.output_file}")
            print(f"   - Transactions: {len(self.logs)}")
            print(f"   - Wealth snapshots: {len(self.wealth_snapshots)}")
            print(f"   - Accounting details: {len(self.accounting_details)}")

# Global singleton instance
economic_logger = EconomicLogger()
