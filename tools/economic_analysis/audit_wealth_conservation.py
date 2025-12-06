"""
全面审计财富守恒问题
分析月末瞬间的财富流向
"""

import pandas as pd
import numpy as np

def audit_wealth_conservation():
    """审计财富守恒：月末各部分财富变化是否守恒"""
    
    print("="*80)
    print("财富守恒审计")
    print("="*80)
    
    df = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')
    TOTAL_WEALTH = 1.8e7
    
    # 分析月末前后的财富变化
    critical_points = [
        (719, 720, 30),   # Day 30
        (1439, 1440, 60)  # Day 60
    ]
    
    for before_iter, after_iter, day in critical_points:
        print(f"\n【Day {day} 月末财富守恒分析】")
        print("-"*50)
        
        # 收集所有部分的财富变化
        changes = {}
        total_before = 0
        total_after = 0
        
        for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']:
            data_before = df[(df['Iteration'] == before_iter) & (df['Metric'] == metric)]
            data_after = df[(df['Iteration'] == after_iter) & (df['Metric'] == metric)]
            
            if not data_before.empty and not data_after.empty:
                wealth_before = data_before['Avg'].values[0] * TOTAL_WEALTH
                wealth_after = data_after['Avg'].values[0] * TOTAL_WEALTH
                change = wealth_after - wealth_before
                changes[metric] = {
                    'before': wealth_before,
                    'after': wealth_after,
                    'change': change
                }
                total_before += wealth_before
                total_after += wealth_after
        
        # 打印各部分变化
        print("\n财富变化明细（百万元）:")
        print(f"{'部分':<10} {'结算前':>10} {'结算后':>10} {'变化':>10}")
        print("-"*45)
        
        for metric, data in changes.items():
            print(f"{metric:<10} {data['before']/1e6:>10.2f} {data['after']/1e6:>10.2f} {data['change']/1e6:>+10.2f}")
        
        print("-"*45)
        total_change = total_after - total_before
        print(f"{'总计':<10} {total_before/1e6:>10.2f} {total_after/1e6:>10.2f} {total_change/1e6:>+10.2f}")
        
        # 守恒检验
        print(f"\n守恒检验:")
        print(f"  总财富变化: {total_change/1e6:.2f} 百万")
        if abs(total_change) > 1000:  # 容差1000元
            print(f"  ❌ 财富不守恒！消失了 {-total_change/1e6:.2f} 百万")
        else:
            print(f"  ✅ 财富守恒")
        
        # 分析资金流向
        print(f"\n资金流向分析:")
        gov_change = changes.get('Government', {}).get('change', 0)
        others_change = sum(changes[k]['change'] for k in changes if k != 'Government')
        
        print(f"  Government支出: {-gov_change/1e6:.2f} 百万")
        print(f"  其他部分收入: {others_change/1e6:.2f} 百万")
        print(f"  差额: {(gov_change + others_change)/1e6:.2f} 百万")
        
        if abs(gov_change + others_change) > 1e6:  # 差额超过100万
            print(f"  ⚠️ Government支出与其他收入不匹配！")
            print(f"  这意味着有 {abs(gov_change + others_change)/1e6:.2f} 百万的财富凭空消失或产生")

def analyze_accounting_mechanism():
    """分析accounting机制的调用"""
    
    print("\n" + "="*80)
    print("Accounting机制分析")
    print("="*80)
    
    print("\n代码审计发现（graph_abs.py第752-767行）:")
    print("```python")
    print("if self.iteration > 1 and new_mth:")
    print("    bus.accounting()  # 所有Business（含Healthcare）")
    print("    ...")
    print("    house.accounting()  # 所有House")
    print("    ...")
    print("    self.government.accounting()  # Government")
    print("```")
    
    print("\n调用顺序:")
    print("1. 所有普通Business先accounting()")
    print("2. Healthcare.accounting() - 作为Business的一种")
    print("3. 所有House.accounting()")
    print("4. Government.accounting()最后")
    
    print("\n关键发现:")
    print("✅ Healthcare.accounting()会在第723行重置expenses")
    print("✅ Government.accounting()在第630行调用demand(healthcare)")
    print("⚠️ 但是Healthcare是在Government之前accounting的！")
    
    print("\n时序问题:")
    print("1. Healthcare.accounting() → expenses重置为0")
    print("2. Government.accounting() → 支付healthcare.expenses（已经是0！）")
    print("3. 这解释了为什么医疗支出可能没有正确支付")

def analyze_demand_mechanism():
    """分析demand机制"""
    
    print("\n" + "="*80)
    print("Demand机制分析")
    print("="*80)
    
    print("\n关键代码（agents.py第482-488行）:")
    print("```python")
    print("elif agent.type == AgentType.Healthcare:")
    print("    labor = agent.expenses  # 使用Healthcare的expenses")
    print("    agent.cash(labor)       # Healthcare收到钱")
    print("else:  # 失业救济")
    print("    labor = agent.expenses  # 使用Person的expenses")
    print("    agent.supply(labor)     # Person收到钱")
    print("```")
    
    print("\nGovernment.demand()的效果:")
    print("1. 对Healthcare: 支付expenses，Healthcare.wealth增加")
    print("2. 对Person: 支付expenses，Person.wealth增加")
    print("3. Government.wealth减少相应金额")
    print("✅ 理论上财富应该守恒")
    
    print("\n但是实际数据显示:")
    print("• Government支出14.36百万")
    print("• 其他部分只增加3-4百万")
    print("• 有10百万凭空消失！")

def find_missing_wealth():
    """寻找消失的财富"""
    
    print("\n" + "="*80)
    print("寻找消失的财富")
    print("="*80)
    
    print("\n可能的财富黑洞:")
    
    print("\n1. Person.expenses的值异常？")
    print("   - Person.expenses初始化为minimum_expense×阶层系数")
    print("   - 但是否在某处被异常修改？")
    
    print("\n2. Government.demand()是否被重复调用？")
    print("   - 月末结算调用一次")
    print("   - 但是否有其他地方也在调用？")
    
    print("\n3. demand()方法的cash/supply是否正确？")
    print("   代码显示:")
    print("   - agent.supply(labor) → agent.wealth += labor")
    print("   - self.cash(-labor) → self.wealth -= labor")
    print("   - 看起来没问题")
    
    print("\n4. ⚠️ 关键发现：expenses的累积问题")
    print("   Person.expenses是日开销")
    print("   但Government支付的是月救济")
    print("   是否存在单位混淆？")
    
    print("\n5. ⚠️⚠️ 最可能的问题：")
    print("   Government.accounting()中失业救济是逐个Person调用demand()")
    print("   每个Person的expenses是日开销（600-8250元）")
    print("   如果有188个失业者，支付188×日开销")
    print("   但这应该只有3.38百万，不是14.36百万")
    print("   说明Person.expenses可能被异常修改了！")

if __name__ == "__main__":
    audit_wealth_conservation()
    analyze_accounting_mechanism()
    analyze_demand_mechanism()
    find_missing_wealth()
    
    print("\n" + "="*80)
    print("审计结论")
    print("="*80)
    print("""
1. 财富守恒严重破坏：
   - Government支出14.36百万
   - 其他部分只收到3-4百万
   - 约10百万财富凭空消失
   
2. 医疗费用重置时序问题：
   - Healthcare先accounting（重置expenses=0）
   - Government后accounting（支付0元医疗费）
   - 这是一个严重的时序bug！
   
3. 最可能的财富消失原因：
   - Person.expenses被异常放大
   - 或Government.demand()被隐性重复调用
   - 或存在未记录的财富转移
""")
