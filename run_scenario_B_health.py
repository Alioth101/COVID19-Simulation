"""
Scenario B: Dynamic Health-Priority

Description:
In this scenario, the government agent's primary goal is to control the epidemic. 
It will implement a dynamic lockdown strategy based on a "circuit breaker" mechanism: 
when the total infection rate exceeds a preset health crisis threshold (e.g., 10%), 
the government will enforce a strict stay-at-home order.

Purpose:
To simulate a reactive crisis management strategy that gives absolute priority to public health.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario_runner_base import run_scenario_experiment

def main():
    # 🎬 SCENARIO CONFIGURATION
    SCENARIO_CONFIG = {
        'name': 'health_priority',
        'description': 'Health First: Aggressive lockdowns to control infection',
        
        # Agent Decision Frequencies
        'person_decision_interval': 2,
        'business_decision_interval': 24,
        'government_decision_interval': 48,
        
        # Policy System - AGGRESSIVE
        'enable_policy_recommendation': True,
        'policy_recommendation_mode': 'aggressive',  # 👈 Key difference
        
        # Thresholds (Lower thresholds for quicker reaction)
        'critical_threshold': 0.05,    # >5% = Lockdown (Ultra Strict)
        'high_threshold': 0.03,        # >3% = High alert

        
        'moderate_threshold': 0.01,
        'economic_weight': 0.1,        # 10% economy, 90% health
    }
    
    run_scenario_experiment(
        scenario_name="Scenario B: Health Priority",
        scenario_config=SCENARIO_CONFIG,
        output_subdir="scenario_b_health"
    )

if __name__ == "__main__":
    main()
