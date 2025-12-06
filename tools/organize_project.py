#!/usr/bin/env python3
"""
项目文件组织工具
将临时工具文件移动到tools目录，保持根目录整洁
"""

import os
import shutil
from datetime import datetime

# 定义需要保留在根目录的核心文件
CORE_FILES = {
    # 可视化脚本（3个）
    'visualize_basic_batch.py',
    'visualize_graph_batch.py',
    'visualize_multipopulation_batch.py',
    
    # 运行实验脚本（6个）
    'run_graph_llm_batch.py',
    'run_graph_llm_simulation.py', 
    'run_llm_basic_batch.py',
    'run_llm_basic_simulation.py',
    'run_llm_multipopulation_batch.py',
    'run_llm_multipopulation_simulation.py',
    
    # 配置文件（2个）
    'llm_config.py',
    'setup.py',
    
    # 自己（组织脚本）
    'organize_project.py'
}

# 需要移动到tools目录的临时文件
TOOL_FILES = {
    # 经济分析工具
    'analyze_economic_debug.py',
    'analyze_month_end_crash.py', 
    'analyze_monthly_accounting.py',
    'audit_wealth_conservation.py',
    'find_hidden_expenses.py',
    'trace_expenses_accumulation.py',
    'verify_total_wealth.py',
    
    # 日志处理工具
    'sort_debug_logs.py',
    'clean_logs.py',
    'add_iteration_logging.py',
    'diagnose_iteration_activity.py',
    
    # 实验管理工具
    'experiment_lock.py',
    'kill_old_experiments.py',
    'monitor_experiment.py',
    'start_clean_experiment.py',
    
    # 数据转换工具
    'convert_to_dynamic_wealth.py',
    
    # 临时可视化
    'visualize_corrected_wealth.py',
    'compare_visualizations.py'
}

def organize_files():
    """组织项目文件"""
    
    print("🗂️ Project File Organizer")
    print("=" * 60)
    
    # 创建tools目录
    tools_dir = "tools"
    if not os.path.exists(tools_dir):
        os.makedirs(tools_dir)
        print(f"✅ Created directory: {tools_dir}/")
    
    # 创建分类子目录
    subdirs = {
        'economic_analysis': '经济分析工具',
        'log_processing': '日志处理工具',
        'experiment_management': '实验管理工具',
        'data_conversion': '数据转换工具',
        'temp_visualization': '临时可视化'
    }
    
    for subdir, desc in subdirs.items():
        path = os.path.join(tools_dir, subdir)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"✅ Created subdirectory: {path}/ ({desc})")
    
    # 文件分类映射
    file_categories = {
        'economic_analysis': [
            'analyze_economic_debug.py',
            'analyze_month_end_crash.py',
            'analyze_monthly_accounting.py',
            'audit_wealth_conservation.py',
            'find_hidden_expenses.py',
            'trace_expenses_accumulation.py',
            'verify_total_wealth.py'
        ],
        'log_processing': [
            'sort_debug_logs.py',
            'clean_logs.py',
            'add_iteration_logging.py',
            'diagnose_iteration_activity.py'
        ],
        'experiment_management': [
            'experiment_lock.py',
            'kill_old_experiments.py',
            'monitor_experiment.py',
            'start_clean_experiment.py'
        ],
        'data_conversion': [
            'convert_to_dynamic_wealth.py'
        ],
        'temp_visualization': [
            'visualize_corrected_wealth.py',
            'compare_visualizations.py'
        ]
    }
    
    # 统计
    moved_count = 0
    kept_count = 0
    error_count = 0
    
    print("\n📋 Processing files...")
    print("-" * 60)
    
    # 移动工具文件到相应目录
    for category, files in file_categories.items():
        category_path = os.path.join(tools_dir, category)
        for file in files:
            if os.path.exists(file):
                try:
                    dest = os.path.join(category_path, file)
                    shutil.move(file, dest)
                    print(f"  📁 Moved: {file} → {category_path}/")
                    moved_count += 1
                except Exception as e:
                    print(f"  ❌ Error moving {file}: {e}")
                    error_count += 1
    
    # 创建README文件
    create_readme_files(tools_dir, subdirs, file_categories)
    
    # 检查根目录中的Python文件
    print("\n📊 Final status:")
    print("-" * 60)
    
    root_py_files = [f for f in os.listdir('.') if f.endswith('.py')]
    
    print(f"\n✅ Files kept in root directory ({len([f for f in root_py_files if f in CORE_FILES])}):")
    for file in sorted(root_py_files):
        if file in CORE_FILES:
            print(f"   • {file}")
            kept_count += 1
    
    # 警告未处理的文件
    unhandled = [f for f in root_py_files if f not in CORE_FILES and f not in TOOL_FILES]
    if unhandled:
        print(f"\n⚠️ Unhandled files in root ({len(unhandled)}):")
        for file in unhandled:
            print(f"   • {file}")
    
    # 检查tools目录中的散落文件并组织
    tools_root_files = [f for f in os.listdir(tools_dir) if f.endswith('.py')]
    if tools_root_files:
        print(f"\n📦 Organizing files already in tools/ root:")
        misc_dir = os.path.join(tools_dir, 'miscellaneous')
        if not os.path.exists(misc_dir):
            os.makedirs(misc_dir)
            print(f"✅ Created subdirectory: {misc_dir}/ (杂项工具)")
        
        for file in tools_root_files:
            src = os.path.join(tools_dir, file)
            dest = os.path.join(misc_dir, file)
            try:
                shutil.move(src, dest)
                print(f"  📁 Moved: {file} → miscellaneous/")
            except Exception as e:
                print(f"  ❌ Error moving {file}: {e}")
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   Files moved to tools/: {moved_count}")
    print(f"   Files kept in root: {kept_count}")
    if error_count > 0:
        print(f"   Errors: {error_count}")
    
    print("\n✨ Project organized successfully!")
    print("\n💡 Tips:")
    print("   • Core experiment files remain in root for easy access")
    print("   • Tools are organized in tools/ by category")
    print("   • Run 'python tools/<category>/<tool>.py' to use tools")

def create_readme_files(tools_dir, subdirs, file_categories):
    """创建README文件说明工具用途"""
    
    # 主README
    main_readme = f"""# Tools Directory

This directory contains various utility tools for the COVID-19 Multi-Agent Simulation project.

## Directory Structure

"""
    for subdir, desc in subdirs.items():
        main_readme += f"- `{subdir}/` - {desc}\n"
    
    main_readme += """
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
"""
    
    # 各子目录README
    readme_contents = {
        'economic_analysis': """# Economic Analysis Tools

Tools for analyzing economic aspects of the simulation.

## Available Tools

- `analyze_economic_debug.py` - Analyze economic debug logs
- `analyze_month_end_crash.py` - Diagnose month-end economic crashes
- `analyze_monthly_accounting.py` - Analyze monthly accounting cycles
- `audit_wealth_conservation.py` - Audit wealth conservation in the system
- `find_hidden_expenses.py` - Find hidden or accumulated expenses
- `trace_expenses_accumulation.py` - Trace expense accumulation patterns
- `verify_total_wealth.py` - Verify total wealth conservation

## Usage Example

```bash
python analyze_economic_debug.py
```
""",
        'log_processing': """# Log Processing Tools

Tools for processing and analyzing simulation logs.

## Available Tools

- `sort_debug_logs.py` - Sort debug logs by iteration number
- `clean_logs.py` - Clean and backup old log files
- `add_iteration_logging.py` - Add iteration logging to experiments
- `diagnose_iteration_activity.py` - Diagnose iteration activity patterns

## Usage Example

```bash
python sort_debug_logs.py
python clean_logs.py
```
""",
        'experiment_management': """# Experiment Management Tools

Tools for managing experiment execution and processes.

## Available Tools

- `experiment_lock.py` - Prevent multiple experiments running simultaneously
- `kill_old_experiments.py` - Terminate old experiment processes
- `monitor_experiment.py` - Real-time experiment monitoring
- `start_clean_experiment.py` - Start experiments with clean environment

## Usage Example

```bash
python monitor_experiment.py
python kill_old_experiments.py
```
""",
        'data_conversion': """# Data Conversion Tools

Tools for converting and transforming experiment data.

## Available Tools

- `convert_to_dynamic_wealth.py` - Convert static to dynamic wealth data

## Usage Example

```bash
python convert_to_dynamic_wealth.py input.csv output.csv
```
""",
        'temp_visualization': """# Temporary Visualization Tools

Temporary or experimental visualization scripts.

## Available Tools

- `visualize_corrected_wealth.py` - Visualize corrected wealth data
- `compare_visualizations.py` - Compare different visualization outputs

## Note

These are experimental visualizations. Use the main visualization scripts in the root directory for standard analysis.
"""
    }
    
    # 写入主README
    with open(os.path.join(tools_dir, 'README.md'), 'w', encoding='utf-8') as f:
        for category, files in file_categories.items():
            main_readme += f"\n### {category.replace('_', ' ').title()}\n"
            for file in files:
                main_readme += f"- `{file}`\n"
        
        f.write(main_readme)
    
    # 写入子目录README
    for subdir, content in readme_contents.items():
        readme_path = os.path.join(tools_dir, subdir, 'README.md')
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except:
            pass

def main():
    """主函数"""
    print("This will organize project files by moving temporary tools to a 'tools' directory.")
    print("Core experiment and visualization scripts will remain in the root directory.")
    print()
    
    response = input("Proceed with organization? (y/n): ").strip().lower()
    
    if response == 'y':
        organize_files()
    else:
        print("\n❌ Organization cancelled.")

if __name__ == "__main__":
    main()
