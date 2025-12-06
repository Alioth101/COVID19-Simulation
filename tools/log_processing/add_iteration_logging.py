#!/usr/bin/env python3
"""
添加迭代日志记录
在每个迭代开始时记录一条日志，确保所有迭代都有记录
"""

def add_iteration_logging():
    """在experiments.py中添加迭代日志"""
    
    # 读取experiments.py
    with open('covid_abs/experiments.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找batch_experiment函数中的迭代循环
    modified = False
    for i, line in enumerate(lines):
        # 查找迭代循环
        if 'for it in range(iterations):' in line:
            # 在循环开始后添加日志
            indent = len(line) - len(line.lstrip())
            next_indent = ' ' * (indent + 4)
            
            # 检查下一行是否已经有日志
            if i + 1 < len(lines) and 'Iteration started' not in lines[i + 1]:
                # 插入日志代码
                log_code = [
                    f"{next_indent}# Log iteration start\n",
                    f"{next_indent}try:\n",
                    f"{next_indent}    from covid_abs.network.log_config import DEBUG_CASHFLOW, DEBUG_LOG_FILE\n",
                    f"{next_indent}    if DEBUG_CASHFLOW:\n",
                    f"{next_indent}        import os\n",
                    f"{next_indent}        day = it // 24\n",
                    f"{next_indent}        hour = it % 24\n",
                    f"{next_indent}        msg = f'[Iter{{it:4d}} Day{{day:2d}}H{{hour:2d}}] 🔄 Iteration started'\n",
                    f"{next_indent}        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:\n",
                    f"{next_indent}            f.write(msg + '\\n')\n",
                    f"{next_indent}            f.flush()\n",
                    f"{next_indent}            os.fsync(f.fileno())\n",
                    f"{next_indent}except:\n",
                    f"{next_indent}    pass\n",
                    f"{next_indent}\n"
                ]
                
                # 插入代码
                lines = lines[:i+1] + log_code + lines[i+1:]
                modified = True
                print(f"✅ Added iteration logging at line {i+1}")
                break
    
    if modified:
        # 写回文件
        with open('covid_abs/experiments.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("✅ File updated successfully")
        return True
    else:
        print("❌ Could not find iteration loop or logging already exists")
        return False

if __name__ == "__main__":
    print("📝 Adding iteration logging to experiments.py...")
    if add_iteration_logging():
        print("\n✅ Success! Now every iteration will be logged.")
        print("   This will help identify which iterations have no economic activity.")
    else:
        print("\n⚠️ No changes made.")
