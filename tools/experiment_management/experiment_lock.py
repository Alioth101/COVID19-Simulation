"""
实验锁机制
防止多个实验同时运行
"""

import os
import sys
import time
import atexit
from datetime import datetime

LOCK_FILE = "experiment.lock"

class ExperimentLock:
    """实验锁，确保只有一个实验在运行"""
    
    def __init__(self):
        self.lock_file = LOCK_FILE
        self.locked = False
        
    def acquire(self, force=False):
        """获取锁"""
        if os.path.exists(self.lock_file) and not force:
            # 读取锁文件信息
            try:
                with open(self.lock_file, 'r') as f:
                    lock_info = f.read().strip().split('\n')
                    if len(lock_info) >= 3:
                        pid = int(lock_info[0])
                        start_time = lock_info[1]
                        exp_name = lock_info[2] if len(lock_info) > 2 else "Unknown"
                        
                        # 检查进程是否仍在运行
                        if self._is_process_running(pid):
                            print(f"❌ Another experiment is already running!")
                            print(f"   PID: {pid}")
                            print(f"   Started: {start_time}")
                            print(f"   Experiment: {exp_name}")
                            print(f"\nOptions:")
                            print(f"  1. Kill the old process and start new")
                            print(f"  2. Wait for it to finish")
                            print(f"  3. Cancel")
                            
                            choice = input("\nYour choice (1/2/3): ").strip()
                            
                            if choice == '1':
                                self._kill_process(pid)
                                os.remove(self.lock_file)
                            elif choice == '2':
                                print("Waiting for the old process to finish...")
                                while self._is_process_running(pid):
                                    time.sleep(5)
                                os.remove(self.lock_file)
                            else:
                                return False
                        else:
                            # 进程已结束，删除旧锁
                            print(f"📝 Removing stale lock (process {pid} no longer running)")
                            os.remove(self.lock_file)
            except Exception as e:
                print(f"⚠️ Error reading lock file: {e}")
                os.remove(self.lock_file)
        
        # 创建新锁
        try:
            with open(self.lock_file, 'w') as f:
                f.write(f"{os.getpid()}\n")
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"COVID-19 Multi-Agent Simulation\n")
            self.locked = True
            
            # 注册退出时自动释放锁
            atexit.register(self.release)
            
            print(f"✅ Experiment lock acquired (PID: {os.getpid()})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to acquire lock: {e}")
            return False
    
    def release(self):
        """释放锁"""
        if self.locked and os.path.exists(self.lock_file):
            try:
                # 检查是否是当前进程的锁
                with open(self.lock_file, 'r') as f:
                    pid = int(f.readline().strip())
                    if pid == os.getpid():
                        os.remove(self.lock_file)
                        self.locked = False
                        print(f"🔓 Experiment lock released")
            except Exception as e:
                print(f"⚠️ Error releasing lock: {e}")
    
    def _is_process_running(self, pid):
        """检查进程是否在运行"""
        try:
            # Windows
            if sys.platform == "win32":
                import subprocess
                output = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}'], 
                                                shell=True, text=True)
                return str(pid) in output
            else:
                # Unix/Linux
                os.kill(pid, 0)
                return True
        except (OSError, subprocess.CalledProcessError):
            return False
    
    def _kill_process(self, pid):
        """终止进程"""
        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.call(['taskkill', '/F', '/PID', str(pid)], shell=True)
            else:
                os.kill(pid, 9)
            print(f"⚡ Killed process {pid}")
            time.sleep(2)  # 等待进程终止
        except Exception as e:
            print(f"❌ Failed to kill process {pid}: {e}")

# 全局锁实例
experiment_lock = ExperimentLock()
