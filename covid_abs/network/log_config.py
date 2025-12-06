"""
日志配置模块
管理调试日志文件的路径和设置
"""
import os
from datetime import datetime

# 调试开关
DEBUG_CASHFLOW = True  # 是否记录现金流日志

# 生成带时间戳的日志文件名（避免多次实验混合）
def get_debug_log_file():
    """获取当前实验的调试日志文件路径"""
    # 检查环境变量中是否设置了特定的日志文件
    log_file = os.environ.get('DEBUG_LOG_FILE')
    if log_file:
        return log_file
    
    # 默认使用固定文件名（会被清空）
    return "debug_cashflow.log"

# 获取当前的日志文件路径
DEBUG_LOG_FILE = get_debug_log_file()

def set_debug_log_file(file_path):
    """设置调试日志文件路径"""
    global DEBUG_LOG_FILE
    DEBUG_LOG_FILE = file_path
    os.environ['DEBUG_LOG_FILE'] = file_path

def clear_debug_log():
    """清空调试日志文件"""
    with open(DEBUG_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Experiment Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
