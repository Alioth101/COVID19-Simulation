"""
Common code for simulation experiments in batch
Enhanced to support LLM-based simulations
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
from datetime import datetime

from covid_abs.common import *
from covid_abs.agents import *
from covid_abs.abs import *
from covid_abs.graphics import color1, color3, legend_ecom


def plot_mean_std(ax, mean, std, legend, color=None):
    l = len(mean)
    lb = [mean[k] - std[k] for k in range(l)]
    ub = [mean[k] + std[k] for k in range(l)]

    ax.fill_between(range(l), ub, lb,
                    color=color, alpha=.5)
    # plot the mean on top
    ax.plot(mean, color, label=legend)


def plot_batch_results(df, health_metrics=('Susceptible', 'Infected', 'Hospitalization', 'Severe', 'Recovered_Immune', 'Death'),
                       ecom_metrics=('Q1', 'Q2', 'Q3', 'Q4', 'Q5')):
    """
    Plot the results of a batch executions contained in the given DataFrame
    :param ecom_metrics:
    :param health_metrics:
    :param df: Pandas DataFrame returned by batch_experiment method
    """

    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=[20, 5])

    ax[0].set_title('Average Contagion Evolution')
    ax[0].set_xlabel("Nº of Days")
    ax[0].set_ylabel("% of Population")

    for col in health_metrics:
        means = df[(df["Metric"] == col)]['Avg'].values
        std = df[(df["Metric"] == col)]['Std'].values
        plot_mean_std(ax[0], means, std, legend=col, color=color1(col))

    handles, labels = ax[0].get_legend_handles_labels()
    lgd = ax[0].legend(handles, labels, loc='upper right')

    mmax = 0.0
    mmin = np.inf
    smax = 0
    smin = np.inf

    for col in ecom_metrics:
        val = df[(df["Metric"] == col)]['Avg'].values
        tmp = int(np.max(val))
        mmax = np.max([mmax, tmp])
        tmp = np.min(val)
        mmin = np.min([mmin, tmp])
        val = df[(df["Metric"] == col)]['Std'].values
        tmp = np.max(val)
        smax = np.max([smax, tmp])
        tmp = np.min(val)
        smin = np.min([smin, tmp])

    ax[1].set_title('Average Economical Impact')
    ax[1].set_xlabel("Nº of Days")
    ax[1].set_ylabel("Wealth")

    for col in ecom_metrics:
        means = df[(df["Metric"] == col)]['Avg'].values
        n_mean = np.interp(means, (mmin, mmax), (0, 1))
        std = df[(df["Metric"] == col)]['Std'].values
        n_std = np.interp(std, (smin, smax), (0, 1))
        ax[1].plot(n_mean, label=legend_ecom[col])
        # std = np.log10(df[(df["Metric"] == col)]['Std'].values)
        # plot_mean_std(ax[1], n_mean, n_std, color=color3(col))

    handles, labels = ax[1].get_legend_handles_labels()
    lgd = ax[1].legend(handles, labels, loc='upper left')


def plot_graph_batch_results(df, **kwargs):
    """
    Plot the results of a batch executions contained in the given DataFrame
    with publication-quality styling.
    """
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator
    
    # Set academic style
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'Liberation Serif', 'serif'],
        'font.size': 17,
        'axes.labelsize': 19,
        'axes.titlesize': 21,
        'xtick.labelsize': 17,
        'ytick.labelsize': 17,
        'legend.fontsize': 16,
        'lines.linewidth': 2.8,
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '--'
    })

    health_metrics = ('Susceptible', 'Infected', 'Hospitalization', 'Severe', 'Recovered_Immune', 'Death')
    
    # Improved Latex-style labels
    health_legend = {
        'Susceptible': 'Susceptible ($S$)', 
        'Infected': 'Infected ($I$)', 
        'Hospitalization': 'Hospitalized ($H$)', 
        'Severe': 'Severe ($Sev$)', 
        'Recovered_Immune': 'Recovered ($R$)', 
        'Death': 'Deceased ($D$)'
    }
    
    # Refined academic color palette (High Contrast)
    health_colors = {
        'Susceptible': '#1f77b4',      # Blue
        'Infected': '#ff7f0e',         # Orange (Distinct from Red)
        'Hospitalization': '#d62728',  # Red
        'Severe': '#9467bd',           # Purple
        'Recovered_Immune': '#2ca02c', # Green
        'Death': '#000000'             # Black
    }

    ecom_legend = {
        'A1': 'Households (Wealth Share)',
        'Business': 'Business (Wealth Share)',
        'Government': 'Government (Wealth Share)'
    }

    # Economic colors (Distinct from Health colors)
    ecom_colors = {
        'A1': '#8c564b',       # Brown
        'Business': '#e377c2', # Pink
        'Government': '#17becf' # Cyan
    }

    epidem = kwargs.get('epidem', True)
    tick_unit = kwargs.get('tick_unit', 72) # Default 3 days
    
    # Calculate time properties
    if df.empty:
        print("⚠️  Warning: DataFrame is empty, cannot plot.")
        return

    max_iteration = int(df['Iteration'].max())
    # Create tick positions every `tick_unit` hours
    tick_positions = list(range(0, max_iteration + 1, tick_unit))
    tick_labels = [str(pos // 24) for pos in tick_positions]

    # Create figure
    fig, ax = plt.subplots(nrows=1, ncols=1 if not epidem else 2, figsize=[16, 6], constrained_layout=True)
    
    axes = [ax] if not isinstance(ax, (list, np.ndarray)) else ax
    
    # --- Plot 1: Epidemiological Evolution ---
    if epidem:
        ep_ax = axes[0]
        ep_ax.set_title('Epidemiological Dynamics')
        ep_ax.set_xlabel('Time (Days)')
        ep_ax.set_ylabel('Population Ratio')
        ep_ax.set_xlim((0, max_iteration))
        ep_ax.set_ylim((0, 1.0))  # Fixed Y-axis to 1.0
        
        # Set ticks
        ep_ax.set_xticks(tick_positions)
        ep_ax.set_xticklabels(tick_labels)
        
        # Keep spines visible (academic standard often prefers full box)
        ep_ax.spines['top'].set_visible(True)
        ep_ax.spines['right'].set_visible(True)

        for col in health_metrics:
            sub_df = df[df["Metric"] == col]
            if sub_df.empty: continue
            
            means = sub_df['Avg'].values
            std = sub_df['Std'].values
            iterations = sub_df['Iteration'].values
            
            # Plot mean line
            ep_ax.plot(iterations, means, label=health_legend.get(col, col), 
                      color=health_colors.get(col, 'black'))
            
            # Plot confidence interval (std dev) - Subtle Fill + Dashed Borders
            ep_ax.fill_between(iterations, 
                              means - std, 
                              means + std, 
                              color=health_colors.get(col, 'black'), 
                              alpha=0.1, linewidth=0)
            ep_ax.plot(iterations, means - std, color=health_colors.get(col, 'black'), 
                      linestyle=':', linewidth=0.5, alpha=0.5)
            ep_ax.plot(iterations, means + std, color=health_colors.get(col, 'black'), 
                      linestyle=':', linewidth=0.5, alpha=0.5)

        ep_ax.legend(loc='upper right', ncol=2, frameon=True, framealpha=0.95, fancybox=False, edgecolor='#dddddd')

    # --- Plot 2: Economic Impact ---
    ec_ax = axes[1] if epidem else axes[0]
    ec_ax.set_title('Economic Trajectories')
    ec_ax.set_xlabel('Time (Days)')
    ec_ax.set_ylabel('Wealth')
    ec_ax.set_xlim((0, max_iteration))
    # Auto-scale Y-axis for economic metrics
    
    # Set ticks
    ec_ax.set_xticks(tick_positions)
    ec_ax.set_xticklabels(tick_labels)

    ec_ax.spines['top'].set_visible(True)
    ec_ax.spines['right'].set_visible(True)
    
    # Prepare Data
    metrics_to_plot = ['Government', 'Business', 'A1']
    
    for col in metrics_to_plot:
        if col == 'A1':
            # Aggregating Q1-Q5 for Households
            q_metrics = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
            means = np.zeros(max_iteration + 1)
            std = np.zeros(max_iteration + 1)
            has_data = False
            
            for q in q_metrics:
                sub_df = df[df["Metric"] == q]
                if not sub_df.empty:
                    # Ensure alignment
                    vals = sub_df['Avg'].values
                    stds = sub_df['Std'].values
                    # Handle potential length mismatch if some iterations are missing
                    # Assuming aligned for now as it comes from batch
                    length = min(len(vals), len(means))
                    means[:length] += vals[:length]
                    std[:length] += stds[:length]
                    has_data = True
            
            if not has_data: continue
            iterations = range(len(means))
            
        else:
            sub_df = df[df["Metric"] == col]
            if sub_df.empty: continue
            means = sub_df['Avg'].values
            std = sub_df['Std'].values
            iterations = sub_df['Iteration'].values

        # Plot
        ec_ax.plot(iterations, means, label=ecom_legend.get(col, col), 
                  color=ecom_colors.get(col, 'black'), linestyle='-')
        
        ec_ax.fill_between(iterations, means - std, means + std, 
                          color=ecom_colors.get(col, 'black'), alpha=0.1, linewidth=0)
        ec_ax.plot(iterations, means - std, color=ecom_colors.get(col, 'black'), 
                  linestyle=':', linewidth=0.5, alpha=0.5)
        ec_ax.plot(iterations, means + std, color=ecom_colors.get(col, 'black'), 
                  linestyle=':', linewidth=0.5, alpha=0.5)

    ec_ax.legend(loc='best', frameon=True, framealpha=0.95, fancybox=False, edgecolor='#dddddd')
    
    # Ensure grid is behind
    if epidem:
        axes[0].set_axisbelow(True)
    axes[1 if epidem else 0].set_axisbelow(True)


def batch_experiment(experiments, iterations, file, simulation_type=Simulation, **kwargs):
    """
    Execute several simulations with the same parameters and store the average statistics by iteration
    
    Supports both rule-based and LLM-based simulations through polymorphism.
    Works seamlessly with Simulation and MultiPopulationSimulation.
    
    :param experiments: number of simulations to be performed
    :param iterations: number of iterations on each simulation
    :param file: filename to store the consolidated statistics
    :param simulation_type: Simulation or MultiPopulationSimulation
    :param kwargs: the parameters of the simulation, including:
        - backend: IntelligenceBackend instance for LLM-based decisions (optional)
        - enable_llm_decision: bool to enable/disable LLM decisions (default: False)
        - decision_interval: int for LLM decision frequency (default: 6)
        - verbose: 'experiments' or 'iterations' for progress output
        - llm_log_file: filename to save LLM decision logs (optional)
        - All other standard simulation parameters
    :return: a Pandas Dataframe with the consolidated statistics by iteration
    
    Output formats:
        - Standard CSV: [Iteration, Metric, Min, Avg, Std, Max] - Compatible with original ABS
        - LLM logs JSON: (optional) Detailed LLM decision logs
    
    Example usage:
        # LLM-based simulation with decision logs
        from covid_abs.llm import OpenAIBackend
        backend = OpenAIBackend(model_name="gpt-4o-mini")
        df = batch_experiment(
            experiments=5, 
            iterations=72, 
            file="results.csv",
            backend=backend,
            enable_llm_decision=True,
            llm_log_file="llm_decisions.json",  # Optional: save LLM logs
            population_size=50,
            ...
        )
    """
    verbose = kwargs.get('verbose', None)
    enable_llm = kwargs.get('enable_llm_decision', False)
    llm_log_file = kwargs.get('llm_log_file', None)
    
    # Display experiment configuration
    if verbose == 'experiments':
        print("\n" + "="*80)
        print("  Batch Experiment Configuration")
        print("="*80)
        print(f"  Simulation Type: {simulation_type.__name__}")
        print(f"  Experiments: {experiments}")
        print(f"  Iterations per experiment: {iterations} ({iterations//24:.1f} days)")
        print(f"  LLM Decision: {'Enabled' if enable_llm else 'Disabled (Rule-based)'}")
        if enable_llm:
            backend = kwargs.get('backend', None)
            print(f"  Backend: {backend}")
        print(f"  Output: {file}")
        if llm_log_file:
            print(f"  LLM Logs: {llm_log_file}")
        print("="*80 + "\n")
    
    rows = []
    columns = None
    failed_experiments = []
    all_llm_logs = []  # Collect LLM logs from all experiments
    
    # 诊断信息收集器 - 用于错误分析
    diagnostics = {
        'experiment_config': {
            'simulation_type': simulation_type.__name__,
            'experiments': experiments,
            'iterations': iterations,
            'population_size': kwargs.get('population_size', 'N/A'),
            'enable_llm': enable_llm,
            'start_time': datetime.now().isoformat(),
        },
        'empty_data_warnings': [],  # 记录所有空数组警告
        'iteration_snapshots': {},  # 记录关键迭代的数据快照
        'errors': [],  # 记录所有错误
    }
    
    for experiment in range(experiments):
        try:
            if verbose == 'experiments':
                print('Experiment {}/{}'.format(experiment + 1, experiments))
                if enable_llm:
                    print('  Running {} iterations with LLM decisions...'.format(iterations))
            sim = simulation_type(**kwargs)
            sim.experiment_id = experiment + 1  # 🔧 Inject experiment ID for logging
            sim.initialize()
            if columns is None:
                statistics = sim.get_statistics(kind='all')
                columns = [k for k in statistics.keys()]
            for it in range(iterations):
                # Log iteration start for debugging
                try:
                    from covid_abs.network.log_config import DEBUG_CASHFLOW, DEBUG_LOG_FILE
                    if DEBUG_CASHFLOW and it < 30:  # Only log first 30 iterations to avoid too much data
                        import os
                        day = it // 24
                        hour = it % 24
                        msg = f'[Iter{it:4d} Day{day:2d}H{hour:2d}] 🔄 === ITERATION START ==='
                        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:
                            f.write(msg + '\n')
                            f.flush()
                            os.fsync(f.fileno())
                except:
                    pass
                
                if verbose == 'iterations':
                    print('Experiment {}\tIteration {}'.format(experiment, it))
                elif verbose == 'experiments' and enable_llm and (it % 12 == 0 or it == iterations - 1):
                    # 🔧 [NEW] 进度更新频率progress every 12 iterations (half day) for LLM experiments
                    print('  Progress: {}/{} iterations ({:.0f}%)'.format(it + 1, iterations, (it + 1) / iterations * 100))
                try:
                    sim.execute()  # 🔧 CRITICAL FIX: Execute simulation step
                    statistics = sim.get_statistics(kind='all')
                    statistics['iteration'] = it
                    rows.append(statistics)
                    
                    # 记录统计数据（每天一次）
                    if it % 24 == 0:
                        try:
                            day = it // 24
                            hour = it % 24
                            person_wealth = sum([statistics.get(f'Q{i}', 0) for i in range(1, 6)])
                            message = (f"[Iter{it:4d} Day{day:2d}H{hour:2d}] "
                                     f"📊 STATISTICS RECORDED: Day {day} Person_ratio={person_wealth:.6f} "
                                     f"Business={statistics.get('Business', 0):.6f} "
                                     f"Government={statistics.get('Government', 0):.6f}")
                            print(message)  # 直接输出统计信息
                        except:
                            pass
                except BaseException as iter_ex:
                    # 捕获所有异常（包括SystemExit, KeyboardInterrupt）
                    import traceback
                    error_msg = f"Iteration {it} (Day {it//24}, Hour {it%24}) failed: {type(iter_ex).__name__}: {iter_ex}"
                    print(f"\n{'='*80}")
                    print(f"[CRITICAL ERROR] {error_msg}")
                    print(f"{'='*80}")
                    print(traceback.format_exc())
                    print(f"{'='*80}\n")
                    
                    # 保存紧急转储文件
                    emergency_file = f'emergency_dump_exp{experiment}_iter{it}.txt'
                    try:
                        with open(emergency_file, 'w', encoding='utf-8') as f:
                            f.write(f"Emergency Dump - Experiment {experiment}, Iteration {it}\n")
                            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                            f.write(f"Error type: {type(iter_ex).__name__}\n")
                            f.write(f"Error message: {str(iter_ex)}\n\n")
                            f.write("Full traceback:\n")
                            f.write(traceback.format_exc())
                            f.write(f"\n\nSimulation state:\n")
                            f.write(f"  Total iterations completed: {it}\n")
                            f.write(f"  Current day: {it//24}, hour: {it%24}\n")
                            if hasattr(sim, 'iteration'):
                                f.write(f"  Sim iteration: {sim.iteration}\n")
                            
                            # ✅ 如果原始异常有 failed_decisions，也记录到dump中
                            if hasattr(iter_ex, 'failed_decisions'):
                                f.write(f"\n\nFailed LLM Decisions ({len(iter_ex.failed_decisions)}):\n")
                                for i, fail in enumerate(iter_ex.failed_decisions, 1):
                                    f.write(f"\n  [{i}] Agent {fail.get('agent_id')} ({fail.get('agent_type')})\n")
                                    f.write(f"      Error: {fail.get('error')}\n")
                                    f.write(f"      Type: {fail.get('error_type')}\n")
                        
                        print(f"📁 Emergency dump saved to: {emergency_file}")
                    except Exception as dump_ex:
                        print(f"⚠️  Failed to save emergency dump: {dump_ex}")
                    
                    # 重新抛出异常，让外层捕获
                    # ✅ 保留 failed_decisions 属性
                    new_error = RuntimeError(f"Experiment aborted at iteration {it}: {iter_ex}")
                    if hasattr(iter_ex, 'failed_decisions'):
                        new_error.failed_decisions = iter_ex.failed_decisions
                    raise new_error from iter_ex
            
            # Collect LLM logs from this experiment
            if llm_log_file and enable_llm:
                experiment_logs = sim.get_llm_logs()
                # Add experiment number to each log entry
                for log in experiment_logs:
                    log['experiment'] = experiment
                all_llm_logs.extend(experiment_logs)
            
        except Exception as ex:
            print("Exception occurred in experiment {}: {}".format(experiment, ex))
            
            # 🔧 [CRITICAL] 即使失败也要保存LLM决策记录（用于token分析）
            if llm_log_file and enable_llm and 'sim' in locals():
                try:
                    print("  ⚠️  Saving LLM logs despite experiment failure...")
                    experiment_logs = sim.get_llm_logs()
                    for log in experiment_logs:
                        log['experiment'] = experiment
                    all_llm_logs.extend(experiment_logs)
                    print(f"  ✓ Saved {len(experiment_logs)} LLM decision logs")
                except Exception as log_ex:
                    print(f"  ⚠️  Failed to save LLM logs: {log_ex}")
            
            # 🔧 [ENHANCED] 提取详细的LLM错误信息（如果存在）
            error_details = {
                'experiment': experiment,
                'error': str(ex)
            }
            
            # ✅ 如果异常包含failed_decisions属性，将其添加到错误详情中
            if hasattr(ex, 'failed_decisions'):
                error_details['llm_failures'] = ex.failed_decisions
                # 同时添加到diagnostics.errors列表，便于分析
                for fail in ex.failed_decisions:
                    diagnostics['errors'].append({
                        'experiment': experiment,
                        'iteration': sim.iteration if 'sim' in locals() else 'Unknown',
                        'agent_id': fail.get('agent_id'),
                        'agent_type': fail.get('agent_type', 'Person'),
                        'error_type': fail.get('error_type'),
                        'error_message': fail.get('error'),
                        'full_traceback': fail.get('full_traceback', 'No traceback')
                    })
            
            failed_experiments.append(error_details)

    # Summary
    if verbose == 'experiments':
        print("\n" + "="*80)
        print("  Batch Experiment Summary")
        print("="*80)
        print(f"  Total Experiments: {experiments}")
        print(f"  Successful: {experiments - len(failed_experiments)}")
        print(f"  Failed: {len(failed_experiments)}")
        print("="*80 + "\n")

    # Generate standard output
    # ✅ 修复: 使用columns变量而不是最后一次statistics.keys()
    # 确保所有实验使用相同的列定义
    if not rows:
        print("⚠️  Warning: No data collected from experiments!")
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # ✅ 验证: 确保columns中的所有列都在df中
    if columns is None:
        columns = [col for col in df.columns if col != 'iteration']
    else:
        # 确保columns中的所有列都存在于df中
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            print(f"⚠️  Warning: Missing columns in data: {missing_cols}")
            columns = [col for col in columns if col in df.columns]

    rows2 = []
    for it in range(iterations):
        try:
            df2 = df[(df['iteration'] == it)]
            
            # ✅ 检查: 如果该迭代完全没有数据，记录并跳过
            if len(df2) == 0:
                diagnostics['empty_data_warnings'].append({
                    'iteration': it,
                    'day': it // 24,
                    'hour': it % 24,
                    'metric': 'ALL',
                    'reason': 'No data for this iteration',
                    'timestamp': datetime.now().isoformat(),
                })
                print(f"[WARNING] Iteration {it}: No data available (experiment may have crashed)")
                continue
            
            for col in columns:
                values = df2[col].values
                # 修复: 处理空数组情况（zero-size array错误）
                # 当某个指标在某次迭代中没有数据时（例如某社会阶层人数为0）
                if len(values) == 0:
                    # 使用NaN填充，表示该迭代该指标无数据
                    row = [it, col, float('nan'), float('nan'), float('nan'), float('nan')]
                    
                    # 记录诊断信息
                    warning_info = {
                        'iteration': it,
                        'day': it // 24,
                        'hour': it % 24,
                        'metric': col,
                        'reason': 'Empty data array (zero-size)',
                        'timestamp': datetime.now().isoformat(),
                    }
                    diagnostics['empty_data_warnings'].append(warning_info)
                    
                    # 第一次遇到空数组时，保存完整的数据快照
                    if len(diagnostics['empty_data_warnings']) == 1:
                        snapshot_key = f'first_empty_at_iteration_{it}'
                        diagnostics['iteration_snapshots'][snapshot_key] = {
                            'iteration': it,
                            'all_metrics': df2.to_dict('records'),
                            'available_columns': list(df2.columns),
                            'data_shape': df2.shape,
                        }
                    
                    # 打印警告
                    print(f"[WARNING] Iteration {it} (Day {it//24}, Hour {it%24}): "
                          f"Metric '{col}' has no data (empty array)")
                else:
                    row = [it, col, values.min(), values.mean(), values.std(), values.max()]
                rows2.append(row)
        except Exception as ex:
            error_msg = f"Error processing iteration {it}: {ex}"
            print(f"[ERROR] {error_msg}")
            diagnostics['errors'].append({
                'iteration': it,
                'error': str(ex),
                'timestamp': datetime.now().isoformat(),
            })

    df2 = pd.DataFrame(rows2, columns=['Iteration', 'Metric', 'Min', 'Avg', 'Std', 'Max'])

    df2.to_csv(file, index=False)
    
    # Save LLM logs if requested
    if llm_log_file and len(all_llm_logs) > 0:
        os.makedirs(os.path.dirname(llm_log_file) if os.path.dirname(llm_log_file) else '.', exist_ok=True)
        
        # Show progress indicator
        if verbose == 'experiments':
            print(f"\n📝 Saving {len(all_llm_logs)} LLM decision logs to JSON...")
            print("   (This may take 10-60 seconds for large datasets)")
        
        # Sort logs by experiment and iteration
        all_llm_logs.sort(key=lambda x: (x['experiment'], x['iteration'], x.get('population_id', 0), x['agent_id']))
        
        output = {
            'metadata': {
                'simulation_type': simulation_type.__name__,
                'total_experiments': experiments,
                'successful_experiments': experiments - len(failed_experiments),
                'iterations_per_experiment': iterations,
                'total_days': iterations // 24,
                'total_decisions': len(all_llm_logs)
            },
            'decisions': all_llm_logs
        }
        
        # Save to JSON with proper formatting for readability
        import time
        save_start = time.time()
        with open(llm_log_file, 'w', encoding='utf-8') as f:
            # Use indent=2 for readable JSON (slightly slower but much more usable)
            json.dump(output, f, indent=2, ensure_ascii=False)
        save_duration = time.time() - save_start
        
        if verbose == 'experiments':
            print(f"\n✓ LLM decision logs saved: {llm_log_file}")
            print(f"  Total LLM decisions logged: {len(all_llm_logs)}")
            print(f"  Save time: {save_duration:.1f} seconds\n")
    
    # 保存诊断信息（如果有警告或错误）
    diagnostics['experiment_config']['end_time'] = datetime.now().isoformat()
    diagnostics['summary'] = {
        'total_empty_warnings': len(diagnostics['empty_data_warnings']),
        'total_errors': len(diagnostics['errors']),
        'iterations_completed': iterations,
        'experiments_completed': experiments - len(failed_experiments),
        'failed_experiments': failed_experiments,
    }
    
    # 只在有问题时才保存诊断文件
    if diagnostics['empty_data_warnings'] or diagnostics['errors'] or failed_experiments:
        # 生成诊断文件路径（与结果文件在同一目录）
        base_path = os.path.splitext(file)[0]
        diagnostics_file = f"{base_path}_diagnostics.json"
        
        os.makedirs(os.path.dirname(diagnostics_file) if os.path.dirname(diagnostics_file) else '.', exist_ok=True)
        
        with open(diagnostics_file, 'w', encoding='utf-8') as f:
            json.dump(diagnostics, f, indent=2, ensure_ascii=False)
        
        if verbose == 'experiments':
            print(f"\n⚠️  Diagnostics Report Saved: {diagnostics_file}")
            print(f"  - Empty data warnings: {len(diagnostics['empty_data_warnings'])}")
            print(f"  - Errors: {len(diagnostics['errors'])}")
            print(f"  - Failed experiments: {len(failed_experiments)}")
            if diagnostics['empty_data_warnings']:
                first_warning = diagnostics['empty_data_warnings'][0]
                print(f"  - First issue at: Iteration {first_warning['iteration']} "
                      f"(Day {first_warning['day']}, Hour {first_warning['hour']}) - "
                      f"Metric '{first_warning['metric']}'")
            print()

    return df2
