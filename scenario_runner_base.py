"""
Base configuration and runner for Scenario experiments.
This module extracts the common logic from run_graph_llm_batch.py to be reused by scenario scripts.
"""

import os
import sys
import numpy as np
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Also add script directory to path (for llm_config.py)
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from covid_abs.network.graph_abs import GraphSimulation
from covid_abs.experiments import batch_experiment
from covid_abs.llm.openai_backend import OpenAIBackend
from covid_abs.agents import Status
from covid_abs.economic_logger import economic_logger

# ============================================================================
# 🎛️ EXPERIMENT CONFIGURATION PANEL (GLOBAL DEFAULTS)
# ============================================================================

# 🔧 DEBUG OUTPUTS
ENABLE_LLM_LOGGING = True          # 📝 LLM decision logs
ENABLE_ECONOMIC_DEBUG = True       # 💰 Economic transaction logs (ENABLED)
ENABLE_CONSOLE_OUTPUT = True       # 📋 Console output logs (ENABLED)
ENABLE_CASHFLOW_DEBUG = True       # 💸 Cashflow debug logs (ENABLED)
ENABLE_HIRING_DEBUG = True         # 👥 Business hiring debug prints (ENABLED)
ENABLE_GOVERNMENT_DEBUG = True     # 🏛️ Government accounting debug prints (ENABLED)
ENABLE_WEALTH_SNAPSHOTS = True     # 📸 Wealth conservation snapshots (ENABLED)
ENABLE_LLM_PROGRESS = True         # 📊 Show LLM decision progress bar

# 🤖 LLM CONFIGURATION
MAX_TOKENS = 1200                  # 📏 Max LLM output length

# 🏗️ SIMULATION CONFIGURATION
EXPERIMENTS = 1                    # Number of runs per scenario
ITERATIONS = 1488                  # 62 days (24 hours * 62)
POPULATION_SIZE = 50              # Default population size
GRID_SIZE = 207                    # Grid dimensions (approx. 24/km^2)

def setup_llm_backend(max_tokens=MAX_TOKENS):
    """Setup LLM backend from config file or environment"""
    try:
        from llm_config import get_llm_config
        
        llm_config = get_llm_config()
        configs = llm_config["configs"]
        params = llm_config["parameters"]
        
        print(f"✅ Loaded configuration from llm_config.py")
        
        # Try to use MultiKeyOpenAIBackend
        try:
            from covid_abs.llm.multi_key_backend import MultiKeyOpenAIBackend
            
            backend = MultiKeyOpenAIBackend(
                api_keys=[cfg["api_key"] for cfg in configs],
                model_name=configs[0]["model"],
                temperature=params["temperature"],
                max_tokens=max_tokens,
                base_url=configs[0]["base_url"],
                proxies=[cfg.get("proxy") for cfg in configs]
            )
            max_concurrent = params.get("max_concurrent") or 3
            return backend, max_concurrent
            
        except ImportError:
            print("⚠️ MultiKeyOpenAIBackend not found, falling back to single key")
            backend = OpenAIBackend(
                model_name=configs[0]["model"],
                temperature=params["temperature"],
                max_tokens=max_tokens,
                api_key=configs[0]["api_key"],
                base_url=configs[0]["base_url"]
            )
            return backend, 3
            
    except Exception as e:
        print(f"⚠️ Failed to load llm_config.py: {e}")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
            
        backend = OpenAIBackend(
            model_name="deepseek-ai/DeepSeek-V3.2-Exp",
            temperature=0.6,
            max_tokens=max_tokens,
            api_key=api_key
        )
        return backend, 3

def run_scenario_experiment(scenario_name, scenario_config, output_subdir, random_seed=42):
    """
    Run a specific scenario experiment
    
    Args:
        scenario_name (str): Name of the scenario (e.g., "Baseline")
        scenario_config (dict): Scenario-specific configuration dictionary
        output_subdir (str): Subdirectory name for outputs (e.g., "scenario_a_baseline")
        random_seed (int): Random seed for reproducibility
    """
    
    # Set random seed
    np.random.seed(random_seed)
    random.seed(random_seed)
    print(f"Random seed set to: {random_seed}")
    
    print("\n" + "="*80)
    print(f"  RUNNING SCENARIO: {scenario_name}")
    print("="*80 + "\n")
    
    # Setup Backend
    backend, max_concurrent = setup_llm_backend()
    
    # Setup Output Directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output", output_subdir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup Logging
    tee = None
    if ENABLE_CONSOLE_OUTPUT:
        console_log_file = os.path.join(output_dir, f"console_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        # Simple tee implementation
        class TeeOutput:
            def __init__(self, file_path):
                self.terminal = sys.stdout
                self.log_file = open(file_path, 'w', encoding='utf-8')
            def write(self, message):
                self.terminal.write(message)
                self.log_file.write(message)
                self.log_file.flush()
            def flush(self):
                self.terminal.flush()
                self.log_file.flush()
            def close(self):
                self.log_file.close()
        
        tee = TeeOutput(console_log_file)
        sys.stdout = tee
        print(f"📝 Console output logging to: {console_log_file}")

    # Set Environment Variables for Debugging
    os.environ['ENABLE_HIRING_DEBUG'] = str(ENABLE_HIRING_DEBUG)
    os.environ['ENABLE_GOVERNMENT_DEBUG'] = str(ENABLE_GOVERNMENT_DEBUG)
    os.environ['ENABLE_WEALTH_SNAPSHOTS'] = str(ENABLE_WEALTH_SNAPSHOTS)
    os.environ['ENABLE_LLM_PROGRESS'] = str(ENABLE_LLM_PROGRESS)
    
    # Economic Config (Standardized)
    total_wealth = 1800000
    business_gdp_share = 0.4
    public_gdp_share = 0.1
    minimum_income = 900.0
    minimum_expense = 600.0
    
    # Economy Openness
    economy_openness = 0.3  # Moderate default
    
    # Business Costs
    business_base_cost = 30
    business_stratum_multipliers = [1.0, 1.7, 2.8, 4.2, 7.5]

    # Prepare Files
    csv_file = os.path.join(output_dir, f"results_{output_subdir}.csv")
    llm_log_file = os.path.join(output_dir, f"llm_decisions_{output_subdir}.json") if ENABLE_LLM_LOGGING else None

    # Print Scenario Config
    print(f"\n📋 Scenario Configuration:")
    print(f"  - Name: {scenario_config.get('name', 'Unknown')}")
    print(f"  - Policy Recommendation: {scenario_config.get('enable_policy_recommendation', False)}")
    if 'description' in scenario_config:
        print(f"  - Description: {scenario_config['description']}")
    print()

    # Run Experiment
    df = batch_experiment(
        experiments=EXPERIMENTS,
        iterations=ITERATIONS,
        file=csv_file,
        simulation_type=GraphSimulation,
        verbose='experiments',
        
        # Environment
        population_size=POPULATION_SIZE,
        length=GRID_SIZE,
        height=GRID_SIZE,
        
        # Social & Demographics
        homemates_avg=3,
        homemates_std=1,
        homeless_rate=0.0005,
        unemployment_rate=0.12,
        
        # Epidemiology
        initial_infected_perc=0.01,
        initial_immune_perc=0.01,
        contagion_distance=1.0,
        contagion_rate=0.9,
        incubation_time=5,
        contagion_time=10,
        recovering_time=20,
        critical_limit=0.05,
        hospitalization_capacity=0.05,
        
        # Mobility
        amplitudes={
            Status.Susceptible: 10,
            Status.Recovered_Immune: 10,
            Status.Infected: 10
        },
        
        # Business
        total_business=5,
        business_distance=20,
        
        # Economy
        total_wealth=total_wealth,
        business_gdp_share=business_gdp_share,
        public_gdp_share=public_gdp_share,
        minimum_income=minimum_income,
        minimum_expense=minimum_expense,
        economy_openness=economy_openness,
        business_base_cost=business_base_cost,
        business_stratum_multipliers=business_stratum_multipliers,
        
        # LLM & Scenario
        scenario_config=scenario_config,
        backend=backend,
        enable_llm_decision=True,
        max_concurrent_llm=max_concurrent,
        llm_log_file=llm_log_file
    )
    
    print("\n" + "="*80)
    print(f"  SCENARIO COMPLETE: {scenario_name}")
    print("="*80)
    print(f"✓ Results saved to: {csv_file}")
    if llm_log_file:
        print(f"✓ LLM Logs saved to: {llm_log_file}")
        
    # Cleanup
    if tee:
        sys.stdout = tee.terminal
        tee.close()
