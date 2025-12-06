"""
分析月末结算的具体问题
重点关注Healthcare费用是否真的被重置了
"""

import pandas as pd
import json
import numpy as np

# 分析CSV数据的月末变化
def analyze_monthly_drops():
    """分析月末财富暴跌的具体数值"""
    
    df = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')
    
    print("="*80)
    print("月末财富暴跌分析（绝对值）")
    print("="*80)
    
    # 初始总财富
    TOTAL_WEALTH = 1.8e7
    
    # 分析关键时间点
    critical_points = [
        (719, 720, 30),   # Day 30 月末
        (1439, 1440, 60)  # Day 60 月末
    ]
    
    for before_iter, after_iter, day in critical_points:
        print(f"\n【Day {day} 月末结算】")
        print("-"*50)
        
        # Government财富变化
        gov_before = df[(df['Iteration'] == before_iter) & (df['Metric'] == 'Government')]
        gov_after = df[(df['Iteration'] == after_iter) & (df['Metric'] == 'Government')]
        
        if not gov_before.empty and not gov_after.empty:
            wealth_before = gov_before['Avg'].values[0] * TOTAL_WEALTH
            wealth_after = gov_after['Avg'].values[0] * TOTAL_WEALTH
            drop = wealth_after - wealth_before
            
            print(f"Government财富:")
            print(f"  结算前: {wealth_before/1e6:.2f} 百万")
            print(f"  结算后: {wealth_after/1e6:.2f} 百万")
            print(f"  支出: {-drop/1e6:.2f} 百万")
            print(f"  支出占总财富: {-drop/TOTAL_WEALTH*100:.2%}")
        
        # Business财富变化（Healthcare是Business的一种）
        bus_before = df[(df['Iteration'] == before_iter) & (df['Metric'] == 'Business')]
        bus_after = df[(df['Iteration'] == after_iter) & (df['Metric'] == 'Business')]
        
        if not bus_before.empty and not bus_after.empty:
            bus_wealth_before = bus_before['Avg'].values[0] * TOTAL_WEALTH
            bus_wealth_after = bus_after['Avg'].values[0] * TOTAL_WEALTH
            bus_change = bus_wealth_after - bus_wealth_before
            
            print(f"\nBusiness财富（含Healthcare）:")
            print(f"  结算前: {bus_wealth_before/1e6:.2f} 百万")
            print(f"  结算后: {bus_wealth_after/1e6:.2f} 百万")
            print(f"  变化: {bus_change/1e6:+.2f} 百万")
        
        # 疫情指标
        print(f"\n疫情指标（Day {day}）:")
        infected = df[(df['Iteration'] == after_iter) & (df['Metric'] == 'Infected')]
        death = df[(df['Iteration'] == after_iter) & (df['Metric'] == 'Death')]
        if not infected.empty:
            print(f"  感染率: {infected['Avg'].values[0]*100:.1f}%")
        if not death.empty:
            print(f"  死亡率: {death['Avg'].values[0]*100:.1f}%")

# 分析感染率变化趋势
def analyze_infection_trend():
    """分析疫情发展趋势"""
    
    df = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')
    
    print("\n" + "="*80)
    print("疫情发展趋势分析")
    print("="*80)
    
    # 每周采样
    weeks = [0, 7, 14, 21, 28, 30, 35, 42, 49, 56, 60]
    
    print(f"\n{'Day':<6} {'感染率':<10} {'死亡率':<10} {'住院率':<10}")
    print("-"*40)
    
    for day in weeks:
        iteration = day * 24
        infected = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Infected')]
        death = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Death')]
        hosp = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Hospitalization')]
        
        inf_rate = infected['Avg'].values[0]*100 if not infected.empty else 0
        death_rate = death['Avg'].values[0]*100 if not death.empty else 0
        hosp_rate = hosp['Avg'].values[0]*100 if not hosp.empty else 0
        
        print(f"{day:<6} {inf_rate:<10.1f} {death_rate:<10.1f} {hosp_rate:<10.1f}")

# 分析LLM决策中的医疗预算增加
def analyze_medical_budget_decisions():
    """分析Government增加医疗预算的决策"""
    
    print("\n" + "="*80)
    print("Government医疗预算决策分析")
    print("="*80)
    
    try:
        with open('output/graph_batch/llm_decisionsP50DeepSeepV3.json', 'r') as f:
            content = f.read()
            # 如果是JSONL格式，按行解析
            decisions = []
            for line in content.strip().split('\n'):
                if line:
                    decisions.append(json.loads(line))
    except:
        print("无法解析LLM决策文件")
        return
    
    # 找出所有Government的医疗预算决策
    medical_decisions = []
    for decision in decisions:
        if isinstance(decision, dict) and \
           decision.get('agent_type') == 'Government' and \
           decision.get('action') == 'IncreaseMedicalBudgetAction':
            medical_decisions.append({
                'day': decision.get('day', -1),
                'iteration': decision.get('iteration', -1),
                'budget_increase': decision.get('parameters', {}).get('budget_increase_percentage', 0)
            })
    
    if medical_decisions:
        print(f"\n发现 {len(medical_decisions)} 次增加医疗预算的决策:")
        for d in medical_decisions:
            print(f"  Day {d['day']}: 增加 {d['budget_increase']}%")
        
        # 统计第一个月vs第二个月
        first_month = [d for d in medical_decisions if 0 <= d['day'] <= 30]
        second_month = [d for d in medical_decisions if 30 < d['day'] <= 60]
        
        print(f"\n月度分布:")
        print(f"  第一个月（Day 0-30）: {len(first_month)} 次增加")
        print(f"  第二个月（Day 30-60）: {len(second_month)} 次增加")
    else:
        print("\n未找到医疗预算增加决策")

# 推算实际支出构成
def estimate_expense_breakdown():
    """推算月末支出的具体构成"""
    
    print("\n" + "="*80)
    print("月末支出构成推算")
    print("="*80)
    
    # 基础参数
    TOTAL_WEALTH = 1.8e7
    POPULATION = 500
    MIN_EXPENSE = 600
    
    # Day 30的情况
    print("\n【Day 30 支出推算】")
    print("-"*50)
    
    # 根据CSV数据
    death_rate_day30 = 0.166  # 16.6%死亡率
    infected_rate_day30 = 0.0  # 感染率已降为0
    
    deaths = int(POPULATION * death_rate_day30)
    survivors = POPULATION - deaths
    
    print(f"人口情况:")
    print(f"  死亡: {deaths}人")
    print(f"  存活: {survivors}人")
    
    # 失业人数估算（假设50%失业率）
    unemployed = int(survivors * 0.452)  # 根据LLM日志Day 33显示45.2%失业率
    print(f"  失业: {unemployed}人")
    
    # 支出估算
    print(f"\n支出估算:")
    
    # 1. 失业救济（每人每天MIN_EXPENSE）
    # 注意：这是月度结算，应该是30天的累计
    unemployment_relief = unemployed * MIN_EXPENSE * 30
    print(f"  失业救济: {unemployment_relief/1e6:.2f} 百万")
    print(f"    = {unemployed}人 × {MIN_EXPENSE}元/天 × 30天")
    
    # 2. Healthcare支出
    # 假设平均每天10-20人住院
    avg_hospitalized = 15
    healthcare_cost = avg_hospitalized * MIN_EXPENSE * 0.6 * 30
    print(f"  医疗支出: {healthcare_cost/1e6:.2f} 百万")
    print(f"    = {avg_hospitalized}人 × {MIN_EXPENSE*0.6}元/天 × 30天")
    
    total_estimated = unemployment_relief + healthcare_cost
    print(f"\n  估算总支出: {total_estimated/1e6:.2f} 百万")
    print(f"  实际Gov支出: 14.36 百万（从CSV计算）")
    print(f"  差异: {(14.36e6 - total_estimated)/1e6:.2f} 百万")
    
    # Day 60的情况
    print("\n【Day 60 支出推算】")
    print("-"*50)
    
    death_rate_day60 = 0.166  # 仍是16.6%
    
    print(f"人口情况（与Day 30相同）:")
    print(f"  失业: {unemployed}人（假设未改善）")
    
    print(f"\n支出估算:")
    print(f"  失业救济: {unemployment_relief/1e6:.2f} 百万（与Day 30相同）")
    print(f"  医疗支出: {healthcare_cost/1e6:.2f} 百万（与Day 30相同）")
    
    print(f"\n⚠️ 问题发现:")
    print(f"  Day 30 Gov支出: 14.36 百万")
    print(f"  Day 60 Gov支出: 14.22 百万")
    print(f"  两个月支出几乎相同！")

# 验证医疗费用重置问题
def check_healthcare_reset():
    """检查医疗费用是否真的被重置了"""
    
    print("\n" + "="*80)
    print("医疗费用重置机制验证")
    print("="*80)
    
    print("\n当前代码（agents.py第723行）:")
    print("```python")
    print("# 重置月度统计")
    print("self.incomes = 0")
    print("self.sales = 0")
    print("self.expenses = 0  # 重置expenses，避免医疗费用无限累积")
    print("```")
    
    print("\n问题分析:")
    print("1. 如果重置生效：")
    print("   - 第一个月医疗费用应该较高（疫情严重）")
    print("   - 第二个月医疗费用应该较低（疫情已控制）")
    print("   - 总支出应该有明显差异")
    
    print("\n2. 实际情况：")
    print("   - Day 30支出: 14.36百万")
    print("   - Day 60支出: 14.22百万")
    print("   - 几乎相同！")
    
    print("\n3. 可能原因：")
    print("   a) 医疗费用重置没有生效")
    print("   b) 失业救济是主要支出，掩盖了医疗费用差异")
    print("   c) 存在其他未知的支出项")
    
    print("\n建议：")
    print("1. 检查Healthcare.expenses是否确实被重置")
    print("2. 在accounting()中添加详细日志记录各项支出")
    print("3. 验证demand()方法的调用次数和金额")

if __name__ == "__main__":
    analyze_monthly_drops()
    analyze_infection_trend()
    analyze_medical_budget_decisions()
    estimate_expense_breakdown()
    check_healthcare_reset()
    
    print("\n" + "="*80)
    print("结论")
    print("="*80)
    print("""
关键发现：
1. Day 30和Day 60的Government支出几乎相同（14.36 vs 14.22百万）
2. 第一个月疫情严重，第二个月已控制，但支出没有差异
3. 这强烈暗示医疗费用重置可能没有生效，或存在其他累积性支出

最可能的问题：
- Healthcare.expenses可能在某个地方又被累加了
- 或者Government的demand()方法被重复调用
- 或者存在隐藏的累积性支出项
""")
