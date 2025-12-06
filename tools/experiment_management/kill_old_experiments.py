#!/usr/bin/env python3
"""
终止旧的实验进程
防止多个实验同时运行导致日志混乱
"""

import os
import sys
import psutil
import time
from datetime import datetime

def find_experiment_processes():
    """查找所有运行实验的Python进程"""
    experiment_processes = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            # 检查是否是Python进程
            if 'python' in proc.info['name'].lower():
                cmdline = proc.info['cmdline']
                if cmdline and any('run_graph_llm_batch' in cmd for cmd in cmdline):
                    # 不包括当前进程
                    if proc.info['pid'] != current_pid:
                        create_time = datetime.fromtimestamp(proc.info['create_time'])
                        experiment_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': ' '.join(cmdline),
                            'created': create_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'running_time': (datetime.now() - create_time).total_seconds() / 60  # minutes
                        })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    return experiment_processes

def kill_process(pid):
    """终止指定进程"""
    try:
        proc = psutil.Process(pid)
        proc.terminate()  # 先尝试正常终止
        time.sleep(2)     # 等待2秒
        
        if proc.is_running():
            proc.kill()   # 如果还在运行，强制终止
            print(f"  ⚡ Force killed process {pid}")
        else:
            print(f"  ✅ Terminated process {pid}")
        return True
    except psutil.NoSuchProcess:
        print(f"  ❓ Process {pid} not found (may have already terminated)")
        return False
    except psutil.AccessDenied:
        print(f"  ❌ Access denied to kill process {pid}")
        return False
    except Exception as e:
        print(f"  ❌ Error killing process {pid}: {e}")
        return False

def main():
    """主函数"""
    print("🔍 Experiment Process Manager")
    print("=" * 60)
    
    # 查找实验进程
    processes = find_experiment_processes()
    
    if not processes:
        print("✅ No running experiment processes found.")
        print("   You can safely start a new experiment.")
        return
    
    # 显示找到的进程
    print(f"\n⚠️ Found {len(processes)} running experiment process(es):\n")
    for i, proc in enumerate(processes, 1):
        print(f"{i}. PID: {proc['pid']}")
        print(f"   Started: {proc['created']} ({proc['running_time']:.1f} minutes ago)")
        print(f"   Command: {proc['cmdline'][:100]}...")
        print()
    
    # 询问用户操作
    print("Options:")
    print("  1. Kill all old experiment processes")
    print("  2. Kill specific process by PID")
    print("  3. Cancel (do nothing)")
    
    choice = input("\nYour choice (1/2/3): ").strip()
    
    if choice == '1':
        # 终止所有进程
        print("\n🔨 Terminating all experiment processes...")
        killed = 0
        for proc in processes:
            if kill_process(proc['pid']):
                killed += 1
        print(f"\n✅ Terminated {killed}/{len(processes)} processes.")
        
    elif choice == '2':
        # 终止特定进程
        pid_str = input("Enter PID to kill: ").strip()
        try:
            pid = int(pid_str)
            if any(proc['pid'] == pid for proc in processes):
                kill_process(pid)
            else:
                print(f"❌ PID {pid} not in the list of experiment processes.")
        except ValueError:
            print("❌ Invalid PID.")
            
    else:
        print("\n❌ Cancelled. No processes were terminated.")
        return
    
    # 清理日志文件
    print("\n🧹 Cleaning up log files...")
    log_files = ["debug_cashflow.log", "debug_cashflow_sorted.log"]
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                # 备份当前日志
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"{log_file}.killed_{timestamp}"
                os.rename(log_file, backup_name)
                print(f"  📦 Backed up: {log_file} -> {backup_name}")
                
                # 创建新的空日志
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== Log cleared after killing old processes at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                print(f"  ✅ Cleared: {log_file}")
            except Exception as e:
                print(f"  ❌ Error cleaning {log_file}: {e}")
    
    print("\n✅ Done! You can now start a fresh experiment.")

if __name__ == "__main__":
    # 检查是否安装了psutil
    try:
        import psutil
    except ImportError:
        print("❌ Error: psutil is not installed.")
        print("   Please install it: pip install psutil")
        sys.exit(1)
    
    main()
