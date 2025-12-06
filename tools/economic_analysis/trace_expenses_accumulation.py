"""
深入追踪expenses累积问题
找出财富消失的真正原因
"""

import re

def analyze_code_flow():
    """分析代码执行流程"""
    
    print("="*80)
    print("代码执行流程分析")
    print("="*80)
    
    print("\n【月末结算流程】graph_abs.py第752-767行:")
    print("```python")
    print("if self.iteration > 1 and new_mth:")
    print("    # 1. 所有Business先accounting（包括Healthcare）")
    print("    for bus in self.business:")
    print("        bus.accounting()")
    print("    ")
    print("    # 2. 所有House再accounting")
    print("    for house in self.houses:")
    print("        house.accounting()")
    print("    ")
    print("    # 3. Government最后accounting")
    print("    self.government.accounting()")
    print("```")
    
    print("\n⚠️ 关键时序问题发现！")
    print("-"*50)
    
    print("\n1. Healthcare.accounting()执行（作为Business）:")
    print("   第723行: self.expenses = 0  # 重置为0")
    
    print("\n2. Government.accounting()执行:")
    print("   第646行: healthcare_expense = self.environment.healthcare.expenses")
    print("   此时healthcare.expenses已经是0！")
    print("   第630行: self.demand(self.environment.healthcare)")
    print("   支付0元给Healthcare！")
    
    print("\n❌ 这就是为什么两个月医疗支出相同的原因：")
    print("   实际上Government根本没有支付医疗费用！")

def analyze_person_expenses_accumulation():
    """分析Person.expenses是否被异常累积"""
    
    print("\n" + "="*80)
    print("Person.expenses累积分析")
    print("="*80)
    
    print("\n初始化（graph_abs.py第254行）:")
    print("agent.expenses = basic_income[stratum] * minimum_expense")
    print("• Q1: 1 × 600 = 600元")
    print("• Q2: 2 × 600 = 1200元")
    print("• Q3: 3.25 × 600 = 1950元")
    print("• Q4: 5 × 600 = 3000元")
    print("• Q5: 13.75 × 600 = 8250元")
    
    print("\n⚠️ 关键发现：这是日开销还是月开销？")
    print("-"*50)
    
    print("\n证据1 - House.add_mate()（第1362行）:")
    print("self.fixed_expenses += agent.expenses / 720  # 每小时开销")
    print("这暗示expenses是月开销（720小时=30天）")
    
    print("\n证据2 - Government.demand()支付失业救济:")
    print("for person in unemployed:")
    print("    self.demand(person)  # 支付person.expenses")
    print("如果expenses是月开销，那么支付就是合理的")
    
    print("\n但是问题是：")
    print("• 188个失业者")
    print("• 平均expenses约2000元（月开销）")
    print("• 总支出应该是：188 × 2000 = 376,000元 = 0.38百万")
    print("• 实际支出：14.36百万！")
    print("• 差异：14百万！")
    
    print("\n可能的原因：")
    print("1. Person.expenses被某处修改放大了")
    print("2. Government.demand()被重复调用了")
    print("3. 存在其他隐藏的expenses累积")

def find_hidden_multiplication():
    """寻找隐藏的倍数关系"""
    
    print("\n" + "="*80)
    print("寻找隐藏的倍数关系")
    print("="*80)
    
    print("\n观察到的倍数：")
    print("• 预期支出：0.38百万（失业救济）")
    print("• 实际支出：14.36百万")
    print("• 倍数：14.36 / 0.38 ≈ 38倍")
    
    print("\n38倍可能来自哪里？")
    print("• 30天？不太像")
    print("• 24小时？也不像")
    print("• 720小时？太大了")
    
    print("\n⚠️⚠️ 关键猜想：")
    print("是否存在循环调用？")
    print("比如Government.demand()中调用了某个会再次触发demand的方法？")

def analyze_demand_chain():
    """分析demand调用链"""
    
    print("\n" + "="*80)
    print("Demand调用链分析")
    print("="*80)
    
    print("\n当Government.demand(person)时（第703行）:")
    print("```python")
    print("def demand(self, agent):  # Business.demand")
    print("    if agent in self.employees:")
    print("        # 分支1：员工")
    print("    elif agent.type == AgentType.Healthcare:")
    print("        # 分支2：Healthcare")
    print("    else:")
    print("        # 分支3：失业者走这里")
    print("        labor = agent.expenses  # Person的expenses")
    print("        agent.supply(labor)     # Person收钱")
    print("        self.cash(-labor)       # Government付钱")
    print("```")
    
    print("\nPerson.supply(value)（第1661行）:")
    print("```python")
    print("if self.house is not None:")
    print("    self.house.supply(value)  # 传给House")
    print("else:")
    print("    self.wealth += value      # 自己收钱")
    print("```")
    
    print("\nHouse.supply(value)（第1431行）:")
    print("```python")
    print("self.wealth += value          # House收钱")
    print("self.incomes += value         # 记录收入")
    print("```")
    
    print("\n✅ 这个链条看起来正常，没有循环")
    
    print("\n但是等等！Government支出14.36百万，")
    print("Q1-Q5总共只增加0.95百万，")
    print("Business减少1.03百万，")
    print("差额：14.36 - 0.95 + 1.03 = 14.44百万凭空消失！")
    
    print("\n💡 新的猜想：")
    print("财富根本没有转移到Person/House，而是消失了！")
    print("可能是supply方法有bug？")

if __name__ == "__main__":
    analyze_code_flow()
    analyze_person_expenses_accumulation()
    find_hidden_multiplication()
    analyze_demand_chain()
    
    print("\n" + "="*80)
    print("最终诊断")
    print("="*80)
    print("""
发现两个严重问题：

1. 医疗费用时序bug（已确认）：
   - Healthcare先重置expenses=0
   - Government后支付，实际支付0元
   - 导致医疗费用完全没有支付

2. 财富消失之谜（需要进一步调查）：
   - Government支出14.36百万
   - 各部分收入总和接近0
   - 14.44百万财富凭空消失
   
   最可能的原因：
   a) Person/House的supply方法有bug，钱没有正确加到wealth
   b) 存在某个隐藏的财富销毁机制
   c) Person.expenses被异常放大（比如累积了30天）
   
建议：
1. 修复医疗费用时序：Government应该先accounting，或保存expenses值
2. 添加详细日志追踪每一笔Government支出的去向
3. 验证Person.expenses的值是否正常
""")
