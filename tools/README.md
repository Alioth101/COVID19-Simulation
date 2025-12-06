# Tools Directory

This directory contains various utility tools for the COVID-19 Multi-Agent Simulation project.

## Directory Structure

- `economic_analysis/` - 经济分析工具
- `log_processing/` - 日志处理工具
- `experiment_management/` - 实验管理工具
- `data_conversion/` - 数据转换工具
- `temp_visualization/` - 临时可视化

## Usage

To use any tool, run:
```bash
python tools/<category>/<tool_name>.py
```

For example:
```bash
python tools/economic_analysis/analyze_economic_debug.py
python tools/log_processing/sort_debug_logs.py
```

## Categories

### Economic Analysis
- `analyze_economic_debug.py`
- `analyze_month_end_crash.py`
- `analyze_monthly_accounting.py`
- `audit_wealth_conservation.py`
- `find_hidden_expenses.py`
- `trace_expenses_accumulation.py`
- `verify_total_wealth.py`

### Log Processing
- `sort_debug_logs.py`
- `clean_logs.py`
- `add_iteration_logging.py`
- `diagnose_iteration_activity.py`

### Experiment Management
- `experiment_lock.py`
- `kill_old_experiments.py`
- `monitor_experiment.py`
- `start_clean_experiment.py`

### Data Conversion
- `convert_to_dynamic_wealth.py`

### Temp Visualization
- `visualize_corrected_wealth.py`
- `compare_visualizations.py`
