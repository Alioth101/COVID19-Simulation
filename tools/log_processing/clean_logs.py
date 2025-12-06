#!/usr/bin/env python3
"""
清理调试日志文件
在运行新实验前使用此脚本清理旧的日志
"""

import os
import glob
from datetime import datetime

def clean_debug_logs():
    """清理所有调试日志文件"""
    
    # 要清理的日志文件列表
    log_files = [
        "debug_cashflow.log",
        "debug_cashflow_sorted.log",
    ]
    
    # 清理每个日志文件
    for log_file in log_files:
        if os.path.exists(log_file):
            # 获取文件大小
            size = os.path.getsize(log_file)
            size_mb = size / (1024 * 1024)
            
            # 备份旧日志（可选）
            if size > 0:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"{log_file}.backup_{timestamp}"
                os.rename(log_file, backup_name)
                print(f"📦 Backed up: {log_file} -> {backup_name} ({size_mb:.2f} MB)")
            
            # 创建空文件
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Log Cleared at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            print(f"✅ Cleared: {log_file}")
    
    # 清理备份文件（保留最近5个）
    backup_files = glob.glob("*.log.backup_*")
    if len(backup_files) > 5:
        backup_files.sort()
        for old_backup in backup_files[:-5]:
            os.remove(old_backup)
            print(f"🗑️ Deleted old backup: {old_backup}")
    
    print("\n✨ All debug logs have been cleaned!")
    print("📝 You can now run a new experiment with clean logs.")

if __name__ == "__main__":
    print("🧹 Debug Log Cleaner")
    print("=" * 50)
    
    # 显示当前日志文件状态
    print("\n📊 Current log files:")
    for log_file in ["debug_cashflow.log", "debug_cashflow_sorted.log"]:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file) / (1024 * 1024)
            lines = sum(1 for _ in open(log_file, 'r', encoding='utf-8'))
            print(f"   {log_file}: {lines} lines, {size:.2f} MB")
        else:
            print(f"   {log_file}: Not found")
    
    # 询问用户确认
    print("\n⚠️ This will clear all debug log files.")
    response = input("Continue? (y/n): ")
    
    if response.lower() == 'y':
        print()
        clean_debug_logs()
    else:
        print("\n❌ Cancelled.")
