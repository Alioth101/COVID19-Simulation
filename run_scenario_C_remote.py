"""
Scenario C: Flexible Remote Work

Description:
In this scenario, we introduce a modern labor market flexibility by activating the 
"Work From Home" (WFH) capability for all eligible employees. Agents can autonomously 
choose to switch from "Go to Work" to "Work From Home".

Purpose:
To simulate a resilient modern digital economy with autonomous "soft" interventions.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario_runner_base import run_scenario_experiment

def main():
    # 🎬 SCENARIO CONFIGURATION
    SCENARIO_CONFIG = {
        'name': 'remote_work',
        'description': 'Flexible Work: Autonomous WFH adoption (No Govt Intervention)',
        
        # Agent Decision Frequencies
        'person_decision_interval': 2,
        'business_decision_interval': 24,
        'government_decision_interval': 48,
        
        # Policy System - DISABLED (Match Baseline)
        # We disable government intervention to isolate the effect of Remote Work
        'enable_policy_recommendation': False,
        'policy_recommendation_mode': 'balanced',
        
        'critical_threshold': 0.10,
        'high_threshold': 0.05,
        'moderate_threshold': 0.02,
        'economic_weight': 0.5,
        
        # 🌟 SPECIAL FEATURE: Enable Remote Work
        # This is the ONLY variable changed from Baseline
        'enable_remote_work': True,
    }
    
    run_scenario_experiment(
        scenario_name="Scenario C: Remote Work",
        scenario_config=SCENARIO_CONFIG,
        output_subdir="scenario_c_remote"
    )

if __name__ == "__main__":
    main()
