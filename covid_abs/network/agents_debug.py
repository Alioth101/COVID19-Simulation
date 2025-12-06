"""
调试版本的agents.py - 添加现金流追踪日志
用于小规模测试追踪Person财富增长的来源
"""

import sys
import os

# 添加日志文件
DEBUG_LOG_FILE = "debug_cashflow.log"

def log_cashflow(message):
    """记录现金流日志"""
    with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

# 初始化日志文件
def init_debug_log():
    """初始化调试日志文件"""
    with open(DEBUG_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("="*80 + '\n')
        f.write("Person财富流动调试日志\n")
        f.write("="*80 + '\n\n')

print("""
使用说明：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

此文件包含需要添加到agents.py中的调试代码。

需要修改的方法：
1. House.supply() - 记录收入来源
2. Person.supply() - 记录收入来源
3. Business.demand() - 记录调用类型

修改步骤：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 在agents.py开头添加日志函数：
   
   import traceback
   
   DEBUG_LOG_FILE = "debug_cashflow.log"
   DEBUG_ENABLED = True  # 设为False禁用日志
   
   def log_cashflow(iteration, day, hour, message):
       if not DEBUG_ENABLED:
           return
       with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
           f.write(f"[Iter{iteration:4d} Day{day:2d}H{hour:2d}] {message}\\n")

2. 修改House.supply()添加日志：
   
   def supply(self, value = 0.0):
       if self.environment.callback('on_house_supply', self):
           return
       
       # ⚠️ 添加调试日志
       if value > 0 and hasattr(self.environment, 'iteration'):
           iteration = self.environment.iteration
           day = iteration // 24
           hour = iteration % 24
           
           # 获取调用栈
           import traceback
           stack = traceback.extract_stack()
           caller_info = f"{stack[-2].filename}:{stack[-2].lineno} {stack[-2].name}"
           
           log_cashflow(iteration, day, hour,
                       f"House.supply({value:.2f}) id={self.id[:8]}... "
                       f"wealth_before={self.wealth:.2f} "
                       f"caller={caller_info}")
       
       self.wealth += value
       self.incomes += value
       
       self.environment.callback('post_house_supply', self)

3. 修改Person.supply()添加日志：
   
   def supply(self, value = 0.0):
       if self.house is not None:
           # ⚠️ 添加调试日志
           if value > 0 and hasattr(self.environment, 'iteration'):
               iteration = self.environment.iteration
               day = iteration // 24
               hour = iteration % 24
               
               import traceback
               stack = traceback.extract_stack()
               caller_info = f"{stack[-2].filename}:{stack[-2].lineno} {stack[-2].name}"
               
               log_cashflow(iteration, day, hour,
                           f"Person.supply({value:.2f}) id={self.id[:8]}... "
                           f"has_house=True house_id={self.house.id[:8]}... "
                           f"caller={caller_info}")
           
           self.house.supply(value)
       else:
           self.wealth += value

4. 修改Business.demand()添加日志：
   
   def demand(self, agent):
       if self.environment.callback('on_business_demand', self):
           return
       labor = 0
       
       # ⚠️ 添加调试日志 - 记录进入哪个分支
       if hasattr(self.environment, 'iteration'):
           iteration = self.environment.iteration
           day = iteration // 24
           hour = iteration % 24
           
           if agent in self.employees:
               branch = "employee"
           elif agent.type == AgentType.Healthcare:
               branch = "healthcare"
           else:
               branch = "NON_EMPLOYEE"  # ⚠️ 关键分支
           
           log_cashflow(iteration, day, hour,
                       f"Business.demand() business_id={self.id[:8]}... "
                       f"business_type={self.type.name} "
                       f"agent_id={agent.id[:8]}... agent_type={agent.type.name} "
                       f"branch={branch} agent_expenses={agent.expenses:.2f}")
       
       # 原有逻辑...
       if agent in self.employees:
           ...

5. 运行小规模测试：
   
   在run_graph_llm_batch.py中修改：
   experiments = 1
   iterations = 72  # 只运行3天
   population_size = 50  # 只50人
   
   然后运行：
   python run_graph_llm_batch.py
   
   检查生成的debug_cashflow.log文件

6. 分析日志：
   
   grep "NON_EMPLOYEE" debug_cashflow.log
   # 看是否有意外的非员工demand调用
   
   grep "Day.*H.*House.supply" debug_cashflow.log | grep -v "Day 0\|Day 30"
   # 看非工资日是否有House收入

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
预期结果：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果Person在Day 31-59有异常收入，日志会显示：
- 调用来源（哪个文件哪一行）
- Business.demand()的分支类型
- agent的expenses值

这样就能精确定位问题根源！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

