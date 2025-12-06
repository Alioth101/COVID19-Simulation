"""
LLM-based Graph Simulation Batch Experiment

This script runs batch experiments for graph-based network simulations with LLM decision-making.
It uses the standard batch_experiment function and generates ABS-compatible CSV output.

Key features:
- Graph-based network simulation (GraphSimulation class)
- LLM-powered agent decision making
- Network structure with Business, House, and Person agents
- Standard CSV output format
- Optional LLM decision logging
"""

# ============================================================================
# 🎛️ EXPERIMENT CONFIGURATION PANEL
# ============================================================================
# Easily toggle different logging and debugging features for your experiments
# ============================================================================

# 📊 ESSENTIAL OUTPUTS (Always Generated)
# ----------------------------------------
# ✅ resultsP500.csv         - Main experiment results (ALWAYS GENERATED)
# ✅ llm_decisionsP500.json  - LLM decision logs (if ENABLE_LLM_LOGGING=True)

# 🔧 DEBUG OUTPUTS (Optional)
# ----------------------------------------
ENABLE_LLM_LOGGING = True          # 📝 LLM decision logs (llm_decisionsP500.json)
ENABLE_ECONOMIC_DEBUG = False      # 💰 Economic transaction logs (economic_debug_*.json)
ENABLE_CONSOLE_OUTPUT = False      # 📋 Console output logs (console_output_*.log)
ENABLE_CASHFLOW_DEBUG = False      # 💸 Cashflow debug logs (debug_cashflow.log)
ENABLE_HIRING_DEBUG = False        # 👥 Business hiring debug prints
ENABLE_GOVERNMENT_DEBUG = False    # 🏛️ Government accounting debug prints
ENABLE_WEALTH_SNAPSHOTS = False    # 📸 Wealth conservation snapshots

# 🤖 LLM CONFIGURATION
# ----------------------------------------
MAX_TOKENS = 1200                  # 📏 Max LLM output length (1200-1500 recommended)
ENABLE_LLM_PROGRESS = True         # 📊 Show LLM decision progress bar

# 🎯 QUICK PRESETS
# ----------------------------------------
# Uncomment one of these presets for common configurations:

# # 🏃 PRODUCTION MODE (Minimal logs, fast execution)
# ENABLE_LLM_LOGGING = True
# ENABLE_ECONOMIC_DEBUG = False
# ENABLE_CONSOLE_OUTPUT = False
# ENABLE_CASHFLOW_DEBUG = False
# ENABLE_HIRING_DEBUG = False
# ENABLE_GOVERNMENT_DEBUG = False
# ENABLE_WEALTH_SNAPSHOTS = False
# ENABLE_LLM_PROGRESS = True

# # 🐛 DEBUG MODE (All logs enabled)
# ENABLE_LLM_LOGGING = True
# ENABLE_ECONOMIC_DEBUG = True
# ENABLE_CONSOLE_OUTPUT = True
# ENABLE_CASHFLOW_DEBUG = True
# ENABLE_HIRING_DEBUG = True
# ENABLE_GOVERNMENT_DEBUG = True
# ENABLE_WEALTH_SNAPSHOTS = True
# ENABLE_LLM_PROGRESS = True

# # 🔍 ECONOMIC DEBUG (Focus on economic issues)
# ENABLE_LLM_LOGGING = True
# ENABLE_ECONOMIC_DEBUG = True
# ENABLE_CONSOLE_OUTPUT = False
# ENABLE_CASHFLOW_DEBUG = True
# ENABLE_HIRING_DEBUG = False
# ENABLE_GOVERNMENT_DEBUG = True
# ENABLE_WEALTH_SNAPSHOTS = True
# ENABLE_LLM_PROGRESS = False

# ============================================================================

import os
import sys
import numpy as np
import random

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


def main():
    """
    Run batch experiments for graph-based LLM simulation
    """
    
    # 
    RANDOM_SEED = 42
    np.random.seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)
    print(f"Random seed set to: {RANDOM_SEED} (for reproducibility)\n")
    
    # ============================================================================
    # [CONFIG] 
    # ============================================================================
    print("\n" + "="*80)
    print("  Graph-Based Network LLM Batch Simulation")
    print("  (llm_config.py)")
    print("="*80 + "\n")
    
    # 
    backend = None
    max_concurrent_llm = 3  # ,llm_config.py
    
    try:
        from llm_config import get_llm_config
        
        llm_config = get_llm_config()
        configs = llm_config["configs"]
        params = llm_config["parameters"]
        
        print(f"✅ 从 llm_config.py 加载配置成功")
        print(f"   有效API配置: {len(configs)}组")
        for i, cfg in enumerate(configs, 1):
            print(f"   {i}. {cfg['name']}: {cfg['api_key'][:10]}...{cfg['api_key'][-4:]}")
        print()
        
        # 使用MultiKeyOpenAIBackend(支持自动负载均衡)
        try:
            from covid_abs.llm.multi_key_backend import MultiKeyOpenAIBackend
            
            backend = MultiKeyOpenAIBackend(
                api_keys=[cfg["api_key"] for cfg in configs],
                model_name=configs[0]["model"],  # 使用第1组的model
                temperature=params["temperature"],
                max_tokens=MAX_TOKENS,  # ✅ 使用实验配置的max_tokens
                base_url=configs[0]["base_url"],  # 使用第1组的base_url
                proxies=[cfg.get("proxy") for cfg in configs]  # ✅ 为每个密钥配置代理
            )
            
            # 使用配置文件中的并发数(覆盖默认值)
            max_concurrent_llm = params.get("max_concurrent") or max_concurrent_llm
            
            print(f"[CONFIG] LLM Decision Logging: {'ENABLED ✓' if ENABLE_LLM_LOGGING else 'DISABLED'}")
            print(f"[CONFIG] Max Tokens: {MAX_TOKENS} (用于控制LLM响应长度)")
            print(f"[CONFIG] 并发数: {max_concurrent_llm} (推荐: {len(configs)}×8 = {len(configs)*8})")
            print(f"[CONFIG] 预期速度提升: {len(configs)}x")
            print()
            
        except ImportError as e:
            print(f"❌ 导入MultiKeyOpenAIBackend失败: {e}")
            print("   正在回退到单密钥模式...")
            print()
            
            # 使用第一个配置创建单密钥backend
            backend = OpenAIBackend(
                model_name=configs[0]["model"],
                temperature=params["temperature"],
                max_tokens=MAX_TOKENS,
                api_key=configs[0]["api_key"],
                base_url=configs[0]["base_url"]
            )
            
            print(f"✅ 使用单密钥模式 (API Key: {configs[0]['name']})")
            print(f"[CONFIG] LLM Decision Logging: {'ENABLED ✓' if ENABLE_LLM_LOGGING else 'DISABLED'}")
            print(f"[CONFIG] Max Tokens: {MAX_TOKENS}")
            print(f"[CONFIG] Max Concurrent LLM Calls: {max_concurrent_llm}")
            print()
        
    except ImportError as ie:
        print(f"⚠️  警告: 未找到 llm_config.py ({str(ie)})")
        print("   使用环境变量配置")
        print()
        
        # 回退到环境变量模式
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OPENAI_API_KEY environment variable not set!")
            print("请配置 llm_config.py 或设置环境变量 OPENAI_API_KEY")
            return
        
        backend = OpenAIBackend(
            model_name="deepseek-ai/DeepSeek-V3.2-Exp",
            temperature=0.6,
            max_tokens=MAX_TOKENS,  # ✅ 使用实验配置的max_tokens
            api_key=api_key
        )
        # max_concurrent_llm 使用已设置的默认值3
        print(f"✅ 使用单密钥模式 (从环境变量)")
        print(f"[CONFIG] Max Concurrent LLM Calls: {max_concurrent_llm}")
        print()
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        import traceback
        print(f"   详细错误:\n{traceback.format_exc()}")
        print()
        print("请检查 llm_config.py 配置:")
        print("  python llm_config.py")
        return
    
    # Ensure backend is created
    if backend is None:
        print("ERROR: Unable to create LLM backend!")
        return
    
    # Experiment parameters
    experiments = 3
    iterations = 1488  # 62 days (2 months)
    population_size = 50
    
    print("Configuration:")
    print(f"  - Experiments: {experiments}")
    print(f"  - Iterations: {iterations} ({iterations//24} days)")
    print(f"  - Population Size: {population_size} agents")
    print(f"  - Initial Infected: 10%")
    print(f"  - Network Type: Graph-based (Business-House-Person)")
    print()
    
    # Create output directory (use absolute path based on script location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output", "graph_batch")
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup console output logging (if enabled)
    import sys
    from datetime import datetime
    
    tee = None
    if ENABLE_CONSOLE_OUTPUT:
        console_log_file = os.path.join(output_dir, f"console_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        class TeeOutput:
            """Tee output to both console and file"""
            def __init__(self, file_path):
                self.terminal = sys.stdout
                self.log_file = open(file_path, 'w', encoding='utf-8')
            
            def write(self, message):
                self.terminal.write(message)
                self.log_file.write(message)
                self.log_file.flush()  # Ensure immediate write
            
            def flush(self):
                self.terminal.flush()
                self.log_file.flush()
            
            def close(self):
                self.log_file.close()
        
        # Redirect stdout to both console and file
        tee = TeeOutput(console_log_file)
        sys.stdout = tee
        
        print(f"📝 Console output will be saved to: {console_log_file}")
    
    # Apply debug configurations
    from covid_abs.network import log_config
    log_config.DEBUG_CASHFLOW = ENABLE_CASHFLOW_DEBUG
    
    # Set debug flags in environment for agents.py to read
    os.environ['ENABLE_HIRING_DEBUG'] = str(ENABLE_HIRING_DEBUG)
    os.environ['ENABLE_GOVERNMENT_DEBUG'] = str(ENABLE_GOVERNMENT_DEBUG)
    os.environ['ENABLE_WEALTH_SNAPSHOTS'] = str(ENABLE_WEALTH_SNAPSHOTS)
    os.environ['ENABLE_LLM_PROGRESS'] = str(ENABLE_LLM_PROGRESS)
    
    # Prepare output files
    csv_file = os.path.join(output_dir, "resultsP500.csv")
    llm_log_file = os.path.join(output_dir, "llm_decisionsP500.json") if ENABLE_LLM_LOGGING else None
    
    # ============================================================================
    # 🎬 SCENARIO CONFIGURATION - Government Policy System
    # ============================================================================
    # Control how Government makes policy decisions
    # ============================================================================
    
    SCENARIO_CONFIG = {
        # ============================================================================
        # [CONFIG] AGENT DECISION FREQUENCIES (hours between decisions)
        # ============================================================================
        'person_decision_interval': 2,      # Person决策频率 （default: 6）
        'business_decision_interval': 24,   # Business决策频率 （default: 12）
        'government_decision_interval':48,  # Government决策频率 （default: 24）
        
        # ============================================================================
        # [CONFIG] POLICY RECOMMENDATION SYSTEM (Dynamic prompt based on epidemic situation)
        # ============================================================================
        'enable_policy_recommendation': True,  # 👈 Set False to disable dynamic prompts
        'policy_recommendation_mode': 'balanced',  # Options: 'aggressive', 'balanced', 'conservative'
        
        # [CONFIG] Infection Rate Thresholds (for policy recommendations)
        'critical_threshold': 0.10,    # >10% = Critical situation
        'high_threshold': 0.05,        # >5% = High risk
        'moderate_threshold': 0.02,    # >2% = Moderate risk
        
        # [CONFIG] Economic Weight (how much to emphasize economic factors in recommendations)
        'economic_weight': 0.5,  # 0.0=health only, 1.0=economy only, 0.5=balanced
    }
    
    print("\n" + "="*80)
    print("  🎬 SCENARIO CONFIGURATION")
    print("="*80)
    print(f"\n  📅 Agent Decision Frequencies:")
    print(f"    Person:     {SCENARIO_CONFIG['person_decision_interval']} hours ({SCENARIO_CONFIG['person_decision_interval']/24:.2f} days)")
    print(f"    Business:   {SCENARIO_CONFIG['business_decision_interval']} hours ({SCENARIO_CONFIG['business_decision_interval']/24:.2f} days)")
    print(f"    Government: {SCENARIO_CONFIG['government_decision_interval']} hours ({SCENARIO_CONFIG['government_decision_interval']/24:.2f} days)")
    
    print(f"\n  🏛️ Policy Recommendation: {'ENABLED ✓' if SCENARIO_CONFIG['enable_policy_recommendation'] else 'DISABLED'}")
    if SCENARIO_CONFIG['enable_policy_recommendation']:
        print(f"    - Mode: {SCENARIO_CONFIG['policy_recommendation_mode']}")
        print(f"    - Critical Threshold: {SCENARIO_CONFIG['critical_threshold']*100}%")
        print(f"    - High Threshold: {SCENARIO_CONFIG['high_threshold']*100}%")
        print(f"    - Economic Weight: {SCENARIO_CONFIG['economic_weight']}")
    print()
    
    # Economic configuration
    total_wealth = 1800000      # [CONFIG] 基础经济总量 (默认: 10000)
    business_gdp_share = 0.4     # [CONFIG] Business财富占比 (默认: 0.5)
    public_gdp_share = 0.1       # [CONFIG] Government财富占比 (默认: 0.1)
    minimum_income = 900.0        # [CONFIG] 最低收入
    minimum_expense = 600.0       # [CONFIG] 最低支出
    
    # [CONFIG] 经济开放度配置 (0.0=完全封闭, 1.0=完全开放)
    ECONOMY_PRESETS = {
        'closed': 0.0,      # 完全封闭经济
        'moderate': 0.3,    # 适度开放
        'balanced': 0.5,    # 平衡开放
        'open': 1.0         # 完全开放
    }
    economy_openness = ECONOMY_PRESETS['moderate']  # [CONFIG] 或直接设置数值 如 0.3
    
    # [CONFIG] Business运营成本系数配置
    # ========================================
    # 说明：Business运营成本 = 员工数量 × 阶层系数
    # - 基础成本：所有阶层的基准值（元/员工/月）
    # - 阶层倍数：Q1-Q5各阶层相对于基础成本的倍数
    # ========================================
    business_base_cost = 30   # [CONFIG] 基础成本（元/员工/月）
    business_stratum_multipliers = [1.0, 1.7, 2.8, 4.2, 7.5]  # [CONFIG] Q1-Q5阶层倍数
    
    # 预设方案（可选）
    BUSINESS_COST_PRESETS = {
        'default': {  # 默认：基于Lorenz曲线
            'base_cost': 200,
            'multipliers': [1.0, 2.0, 3.25, 5.0, 13.75]
        },
        'moderate': {  # 适度差异：Q5是Q1的6倍
            'base_cost': 200, 
        },
        'uniform': {  # 统一成本：所有阶层相同
            'base_cost': 200,
            'multipliers': [1.0, 1.0, 1.0, 1.0, 1.0]
        },
        'extreme': {  # 极端差异：Q5是Q1的20倍
            'base_cost': 200,
            'multipliers': [1.0, 2.5, 5.0, 10.0, 20.0]
        }
    }
    
    # [CONFIG] 快速切换预设（注释掉下面两行可使用上面的手动配置）
    # preset = BUSINESS_COST_PRESETS['default']
    # business_base_cost, business_stratum_multipliers = preset['base_cost'], preset['multipliers']
    
    print(f"💰 Economic Configuration:")
    print(f"  - Total Wealth: {total_wealth:,}")
    print(f"  - Business Share: {business_gdp_share*100}% = {total_wealth*business_gdp_share:,.0f}")
    print(f"  - Government Share: {public_gdp_share*100}% = {total_wealth*public_gdp_share:,.0f}")
    print(f"  - Person Share: {(1-business_gdp_share-public_gdp_share)*100}% = {total_wealth*(1-business_gdp_share-public_gdp_share):,.0f}")
    print(f"  - Economy Openness: {economy_openness} ({'Closed' if economy_openness == 0.0 else 'Open' if economy_openness == 1.0 else 'Moderate'})")
    print(f"    * Capital outflow: House {economy_openness*90:.1f}%, Business {economy_openness*67:.1f}%")
    print(f"    * Local circulation: House {(1-economy_openness)*90:.1f}%, Business {(1-economy_openness)*67:.1f}%")
    print(f"\n💼 Business Operating Cost Configuration:")
    print(f"  - Base Cost: ${business_base_cost}/employee/month")
    print(f"  - Stratum Multipliers: {business_stratum_multipliers}")
    print(f"  - Q1 (street shop): ${business_base_cost * business_stratum_multipliers[0]:.0f}/employee/month")
    print(f"  - Q3 (chain store): ${business_base_cost * business_stratum_multipliers[2]:.0f}/employee/month")
    print(f"  - Q5 (luxury store): ${business_base_cost * business_stratum_multipliers[4]:.0f}/employee/month")
    print(f"  - Cost Ratio (Q5/Q1): {business_stratum_multipliers[4]/business_stratum_multipliers[0]:.2f}×")
    print()
    
    # Initialize economic logger if enabled
    if ENABLE_ECONOMIC_DEBUG:
        print("\n" + "="*80)
        print("  💰 ECONOMIC DEBUG LOGGING ENABLED")
        print("="*80)
        economic_logger.initialize(enabled=True, output_dir=output_dir)
        print(f"  Economic transactions will be logged for detailed analysis")
        print(f"  This will help identify wealth conservation issues")
        print()
    else:
        economic_logger.initialize(enabled=False)

    # Clear debug log file at the start of each experiment
    if ENABLE_ECONOMIC_DEBUG:
        from covid_abs.network.log_config import clear_debug_log
        clear_debug_log()
        print(f"📝 Debug log cleared: debug_cashflow.log")
    
    # Note: Detailed logs are written to debug_cashflow.log
    # Use sort_debug_logs.py to sort them after experiment completion
    print(f"📝 Detailed logs: debug_cashflow.log (use sort_debug_logs.py to sort)")
    
    # Run batch experiment
    df = batch_experiment(
        experiments=experiments,
        iterations=iterations,
        file=csv_file,
        simulation_type=GraphSimulation,
        verbose='experiments',
        
        # ========================================
        # 环境参数
        # ========================================
        population_size=population_size,
        length=207,                         # ✅ 保持24人/km²密度
        height=207,                         # ✅ 保持24人/km²密度
        
        # ========================================
        # 社会人口参数（📚 真实数据）
        # ========================================
        homemates_avg=3,                    # ✅ [44] 家庭规模
        homemates_std=1,                    # ✅ 家庭规模标准差
        homeless_rate=0.0005,               # ✅ [45] 0.05%无家可归率
        unemployment_rate=0.12,             # ✅ [54] 12%失业率
        
        # ========================================
        # 流行病学参数（📚 真实数据）
        # ========================================
        # 初始状态
        initial_infected_perc=0.01,         # ✅ 1%初始感染
        initial_immune_perc=0.01,           # ✅ 1%初始免疫
        
        # 传染参数
        contagion_distance=1.0,             # ✅ [46] 社交距离
        contagion_rate=0.9,                 # ✅ [46] 90%传染率
        
        # 疾病时间参数（天）
        incubation_time=5,                  # ✅ [47,48] 5天潜伏期
        contagion_time=10,                  # ✅ [49] 10天传染期
        recovering_time=20,                 # ✅ [50] 20天康复期
        
        # 医疗系统
        critical_limit=0.05,                # ✅ 5% ICU容量
        hospitalization_capacity=0.05,      # ✅ 5%住院容量
        
        # 移动参数
        amplitudes={                        # ✅ [Table 2] α6=10单位移动幅度
            Status.Susceptible: 10,
            Status.Recovered_Immune: 10,
            Status.Infected: 10
        },
        
        # 企业参数
        total_business=5,                  # ✅ [53] 15家企业
        business_distance=20,               # ✅ 企业距离
        
        # ========================================
        # 经济参数
        # ========================================
        total_wealth=total_wealth,
        business_gdp_share=business_gdp_share,
        public_gdp_share=public_gdp_share,
        minimum_income=minimum_income,
        minimum_expense=minimum_expense,
        economy_openness=economy_openness,
        business_base_cost=business_base_cost,
        business_stratum_multipliers=business_stratum_multipliers,
        
        # ========================================
        # LLM & Scenario配置
        # ========================================
        scenario_config=SCENARIO_CONFIG,
        backend=backend,
        enable_llm_decision=True,
        max_concurrent_llm=max_concurrent_llm,
        llm_log_file=llm_log_file
    )
    
    print("\n" + "="*80)
    print("  Experiment Complete!")
    print("="*80)
    print(f"\n✓ Standard CSV output: {csv_file}")
    print(f"  Format: [Iteration, Metric, Min, Avg, Std, Max]")
    print(f"  Compatible with original ABS analysis tools")
    
    if ENABLE_LLM_LOGGING:
        print(f"\n✓ LLM decision logs: {llm_log_file}")
        print(f"  Contains all agent decisions with:")
        print(f"  - iteration, day, hour")
        print(f"  - agent_id, agent_type (Person/Business/Government)")
        print(f"  - action, reasoning, parameters")
        print(f"  - experiment number")
    else:
        print(f"\n  (LLM logging disabled - set ENABLE_LLM_LOGGING=True to enable)")
    
    # 🔧 [ENHANCED] 显示API密钥使用统计
    if backend and hasattr(backend, 'print_key_stats'):
        backend.print_key_stats()
    
    print("\n" + "="*80)
    
    # Close console logging
    try:
        sys.stdout.close()
        sys.stdout = tee.terminal  # Restore original stdout
        print(f"📝 Console output saved to: {console_log_file}")
    except:
        pass
    
    # Save economic debug log if enabled
    if ENABLE_ECONOMIC_DEBUG:
        print("\n💾 Saving Economic Debug Log...")
        economic_logger.save()
        print("✓ Economic debug log saved successfully!")
        print("  Use the analysis script to diagnose wealth conservation issues")
        print()
    
    # Provide log sorting instructions
    print("\n📋 Debug Log Processing:")
    print("  1. Sort detailed logs: python sort_debug_logs.py")
    print("  2. Analyze economics: python analyze_economic_debug.py")
    print("  3. View sorted logs: debug_cashflow_sorted.log")
    
    # Display sample results
    if df is not None:
        print("\n📊 Sample Results (first 15 rows):")
        print(df.head(15).to_string())
        print(f"\n   ... ({len(df)} total rows)\n")
    
    # Summary of generated files
    print("\n" + "="*80)
    print("  📁 GENERATED FILES SUMMARY")
    print("="*80)
    print(f"\n✅ Essential outputs:")
    print(f"  • Results CSV: {csv_file}")
    
    if ENABLE_LLM_LOGGING and llm_log_file:
        print(f"  • LLM Decision Log: {llm_log_file}")
    
    if ENABLE_CONSOLE_OUTPUT and tee:
        print(f"\n✅ Debug outputs:")
        print(f"  • Console Output: Saved to log file")
    
    if ENABLE_ECONOMIC_DEBUG:
        economic_files = [f for f in os.listdir(output_dir) if f.startswith('economic_debug_')]
        if economic_files:
            print(f"  • Economic Debug: {len(economic_files)} JSON files")
    
    if ENABLE_CASHFLOW_DEBUG:
        cashflow_file = os.path.join(output_dir, "debug_cashflow.log")
        if os.path.exists(cashflow_file):
            print(f"  • Cashflow Debug: debug_cashflow.log")
    
    # Summary of disabled outputs
    disabled = []
    if not ENABLE_LLM_LOGGING:
        disabled.append("LLM logs")
    if not ENABLE_CONSOLE_OUTPUT:
        disabled.append("Console output")
    if not ENABLE_ECONOMIC_DEBUG:
        disabled.append("Economic debug")
    if not ENABLE_CASHFLOW_DEBUG:
        disabled.append("Cashflow debug")
    if not ENABLE_HIRING_DEBUG:
        disabled.append("Hiring prints")
    if not ENABLE_GOVERNMENT_DEBUG:
        disabled.append("Government prints")
    
    if disabled:
        print(f"\n⚠️ Disabled outputs: {', '.join(disabled)}")
        print(f"   (To enable, modify flags at top of script)")
    
    print("\n✓ Done! You can now:")
    print("  1. Visualize results: python visualize_graph_batch.py")
    if ENABLE_LLM_LOGGING:
        print(f"  2. Analyze LLM decisions: python analyze_llm_logs.py --log_file {llm_log_file}")
    print("  3. Compare with other experiments")
    print("  4. Adjust configuration flags for next run")
    print()


if __name__ == "__main__":
    # Try to import lock mechanism (optional)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools', 'experiment_management'))
        from experiment_lock import experiment_lock
        
        # Acquire lock before starting experiment
        if not experiment_lock.acquire():
            print("❌ Failed to acquire experiment lock. Exiting...")
            sys.exit(1)
        
        lock_acquired = True
    except ImportError:
        # Lock mechanism not available, proceed without it
        print("⚠️ Experiment lock not available, proceeding without lock protection")
        print("   (To enable, ensure experiment_lock.py is in tools/experiment_management/)")
        lock_acquired = False
        experiment_lock = None
    
    try:
        main()
    finally:
        # Ensure lock is released if it was acquired
        if lock_acquired and experiment_lock:
            experiment_lock.release()
