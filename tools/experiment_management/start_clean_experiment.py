#!/usr/bin/env python3
"""
安全启动实验脚本
1. 检查并终止旧进程
2. 清理日志文件
3. 启动新实验
"""

import os
import sys
import subprocess
import time
from datetime import datetime

def check_python_processes():
    """检查是否有Python进程在运行实验"""
    print("🔍 Checking for running experiment processes...")
    
    if sys.platform == "win32":
        # Windows
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                                  capture_output=True, text=True, shell=True)
            lines = result.stdout.strip().split('\n')
            python_processes = [line for line in lines if 'python.exe' in line.lower()]
            
            if len(python_processes) > 1:  # 至少有一个除了当前进程
                print(f"⚠️ Found {len(python_processes)} Python processes running")
                print("\nOptions:")
                print("  1. Kill all Python processes (except this one)")
                print("  2. Continue anyway (risky!)")
                print("  3. Cancel")
                
                choice = input("\nYour choice (1/2/3): ").strip()
                
                if choice == '1':
                    print("🔨 Killing Python processes...")
                    subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', f'PID ne {os.getpid()}'], 
                                 shell=True)
                    time.sleep(2)
                    return True
                elif choice == '2':
                    print("⚠️ Continuing with existing processes (may cause log conflicts)")
                    return True
                else:
                    return False
        except Exception as e:
            print(f"❌ Error checking processes: {e}")
            return True
    else:
        # Linux/Mac
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            python_processes = [line for line in lines if 'python' in line and 'run_graph_llm_batch' in line]
            
            if python_processes:
                print(f"⚠️ Found experiment processes running:")
                for proc in python_processes[:3]:
                    print(f"  {proc[:100]}...")
                
                print("\nOptions:")
                print("  1. Kill old experiment processes")
                print("  2. Continue anyway (risky!)")
                print("  3. Cancel")
                
                choice = input("\nYour choice (1/2/3): ").strip()
                
                if choice == '1':
                    print("🔨 Killing old processes...")
                    subprocess.run(['pkill', '-f', 'run_graph_llm_batch'])
                    time.sleep(2)
                    return True
                elif choice == '2':
                    return True
                else:
                    return False
        except Exception as e:
            print(f"❌ Error checking processes: {e}")
            return True
    
    print("✅ No conflicting processes found")
    return True

def clean_logs():
    """清理日志文件"""
    print("\n🧹 Cleaning log files...")
    
    log_files = [
        "debug_cashflow.log",
        "debug_cashflow_sorted.log",
        "experiment.lock"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                # 备份重要的日志
                if os.path.getsize(log_file) > 1000:  # 如果文件大于1KB
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_name = f"backup/{log_file}.{timestamp}"
                    os.makedirs("backup", exist_ok=True)
                    os.rename(log_file, backup_name)
                    print(f"  📦 Backed up: {log_file} -> {backup_name}")
                else:
                    os.remove(log_file)
                    print(f"  🗑️ Deleted: {log_file}")
            except Exception as e:
                print(f"  ⚠️ Could not clean {log_file}: {e}")
    
    # 创建新的空日志文件
    with open("debug_cashflow.log", 'w', encoding='utf-8') as f:
        f.write(f"=== Experiment Log Initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    print("✅ Logs cleaned")

def start_experiment():
    """启动实验"""
    print("\n🚀 Starting experiment...")
    print("=" * 60)
    
    try:
        # 使用subprocess启动，这样可以更好地控制
        if sys.platform == "win32":
            # Windows
            process = subprocess.Popen([sys.executable, "run_graph_llm_batch.py"], 
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            # Linux/Mac
            process = subprocess.Popen([sys.executable, "run_graph_llm_batch.py"])
        
        print(f"✅ Experiment started with PID: {process.pid}")
        print(f"   Monitor logs: tail -f debug_cashflow.log")
        print(f"   Sort logs later: python sort_debug_logs.py")
        
        # 等待进程结束
        print("\n📊 Experiment is running...")
        process.wait()
        
        return_code = process.returncode
        if return_code == 0:
            print("\n✅ Experiment completed successfully!")
        else:
            print(f"\n⚠️ Experiment ended with return code: {return_code}")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Experiment interrupted by user")
        if 'process' in locals():
            process.terminate()
            print("   Process terminated")
    except Exception as e:
        print(f"\n❌ Error starting experiment: {e}")

def main():
    """主函数"""
    print("🧪 Clean Experiment Launcher")
    print("=" * 60)
    print("This script will:")
    print("  1. Check for conflicting processes")
    print("  2. Clean old log files")
    print("  3. Start a fresh experiment")
    print()
    
    # 步骤1：检查进程
    if not check_python_processes():
        print("\n❌ Aborted by user")
        return
    
    # 步骤2：清理日志
    clean_logs()
    
    # 步骤3：启动实验
    response = input("\n▶️ Ready to start experiment? (y/n): ").strip().lower()
    if response == 'y':
        start_experiment()
    else:
        print("\n❌ Experiment cancelled")

if __name__ == "__main__":
    main()
