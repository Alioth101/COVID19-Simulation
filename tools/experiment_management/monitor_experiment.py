#!/usr/bin/env python3
"""
实时监控实验进度
显示日志写入延迟和实际进度
"""

import time
import os
import re
from datetime import datetime

def get_last_iteration(log_file="debug_cashflow.log"):
    """获取日志中最后的迭代号"""
    iteration_pattern = re.compile(r'\[Iter\s*(\d+)\s+Day\s*(\d+)H\s*(\d+)\]')
    last_iteration = -1
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # 读取最后1000行以提高效率
            lines = f.readlines()
            for line in reversed(lines[-1000:]):
                match = iteration_pattern.match(line)
                if match:
                    last_iteration = int(match.group(1))
                    break
    except:
        pass
    
    return last_iteration

def get_console_progress(console_log_file=None):
    """从控制台日志获取实际进度"""
    if not console_log_file:
        # 查找最新的控制台日志
        import glob
        console_logs = glob.glob("output/graph_batch/console_output_*.log")
        if console_logs:
            console_log_file = max(console_logs, key=os.path.getctime)
        else:
            return -1
    
    try:
        with open(console_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines[-100:]):
                # 查找进度报告
                if "Progress:" in line and "iterations" in line:
                    # 提取 "Progress: 24/1488 iterations"
                    match = re.search(r'Progress:\s*(\d+)/\d+\s*iterations', line)
                    if match:
                        return int(match.group(1)) - 1  # 转为0-based索引
    except:
        pass
    
    return -1

def monitor_experiment(interval=5):
    """监控实验进度"""
    print("📊 Experiment Monitor")
    print("=" * 60)
    print("Press Ctrl+C to stop monitoring\n")
    
    # 获取日志文件大小
    log_file = "debug_cashflow.log"
    
    try:
        prev_iteration = -1
        prev_size = 0
        start_time = time.time()
        
        while True:
            # 获取当前状态
            current_iteration = get_last_iteration(log_file)
            actual_progress = get_console_progress()
            
            # 获取文件大小
            try:
                current_size = os.path.getsize(log_file)
                size_mb = current_size / (1024 * 1024)
            except:
                current_size = 0
                size_mb = 0
            
            # 计算速率
            elapsed = time.time() - start_time
            if elapsed > 0 and current_iteration > 0:
                iter_per_sec = current_iteration / elapsed
                if current_size > prev_size:
                    write_rate = (current_size - prev_size) / interval / 1024  # KB/s
                else:
                    write_rate = 0
            else:
                iter_per_sec = 0
                write_rate = 0
            
            # 计算延迟
            if actual_progress >= 0 and current_iteration >= 0:
                delay = actual_progress - current_iteration
            else:
                delay = 0
            
            # 清屏（简单方式）
            print("\033[H\033[J", end="")  # ANSI escape codes
            
            # 显示状态
            print("📊 Experiment Monitor")
            print("=" * 60)
            print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
            print()
            
            print(f"📝 Debug Log Status:")
            print(f"   Last logged iteration: {current_iteration}")
            print(f"   Day: {current_iteration // 24 if current_iteration >= 0 else 0}")
            print(f"   Hour: {current_iteration % 24 if current_iteration >= 0 else 0}")
            print(f"   File size: {size_mb:.2f} MB")
            print()
            
            if actual_progress >= 0:
                print(f"🚀 Actual Progress:")
                print(f"   Current iteration: {actual_progress}")
                print(f"   Day: {actual_progress // 24}")
                print(f"   Hour: {actual_progress % 24}")
                print()
                
                print(f"⚠️ Log Delay:")
                print(f"   Iterations behind: {delay}")
                if delay > 10:
                    print(f"   Status: ❌ SEVERE DELAY")
                elif delay > 5:
                    print(f"   Status: ⚠️ Moderate delay")
                else:
                    print(f"   Status: ✅ Normal")
            
            print()
            print(f"📈 Performance:")
            print(f"   Iteration rate: {iter_per_sec:.2f} iter/sec")
            print(f"   Log write rate: {write_rate:.2f} KB/sec")
            
            # 检查是否有新数据
            if current_iteration == prev_iteration and current_size == prev_size:
                print()
                print("⚠️ No new log data in last {} seconds".format(interval))
                if actual_progress > current_iteration + 50:
                    print("🔴 CRITICAL: Log writing may have stopped!")
            
            prev_iteration = current_iteration
            prev_size = current_size
            
            # 等待下次检查
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def main():
    """主函数"""
    import sys
    
    # 检查参数
    interval = 5
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except:
            print("Usage: python monitor_experiment.py [interval_seconds]")
            return
    
    print(f"Starting monitor with {interval} second interval...")
    monitor_experiment(interval)

if __name__ == "__main__":
    main()
