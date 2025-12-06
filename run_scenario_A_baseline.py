"""
Scenario A: Baseline (Laissez-faire)

Description:
This is a "laissez-faire" control group scenario. In this scenario, the government agent 
takes no active non-pharmaceutical interventions (like lockdowns) or economic interventions 
(like fiscal stimulus). Individual agents make decisions based entirely on their own 
risk-reward assessments.

Purpose:
To establish a reference baseline to measure the relative effectiveness of other interventions.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario_runner_base import run_scenario_experiment

def main():
    # 🎬 SCENARIO CONFIGURATION
    SCENARIO_CONFIG = {
        'name': 'baseline',
        'description': 'Laissez-faire: No active government intervention',
        
        # Agent Decision Frequencies
        'person_decision_interval': 2,
        'business_decision_interval': 24,
        'government_decision_interval': 48,
        
        # Policy System - DISABLED for Baseline
        # (Though even if enabled, graph_message.py will filter actions for 'baseline' scenario)
        'enable_policy_recommendation': False,
        'policy_recommendation_mode': 'balanced', 
        
        'critical_threshold': 0.10,
        'high_threshold': 0.05,
        'moderate_threshold': 0.02,
        'economic_weight': 0.5,
    }
    
    run_scenario_experiment(
        scenario_name="Scenario A: Baseline",
        scenario_config=SCENARIO_CONFIG,
        output_subdir="scenario_a_baseline"
    )

if __name__ == "__main__":
    main()
