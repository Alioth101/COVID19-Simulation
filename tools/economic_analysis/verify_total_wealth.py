import pandas as pd
import numpy as np

# 读取CSV数据
df = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')

def calculate_total_wealth(iteration):
    """计算某个迭代时的总财富"""
    
    # 获取该迭代的所有财富数据
    iter_data = df[df['Iteration'] == iteration]
    
    # 计算各部分财富
    q1 = iter_data[iter_data['Metric'] == 'Q1']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Q1'].empty else 0
    q2 = iter_data[iter_data['Metric'] == 'Q2']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Q2'].empty else 0
    q3 = iter_data[iter_data['Metric'] == 'Q3']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Q3'].empty else 0
    q4 = iter_data[iter_data['Metric'] == 'Q4']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Q4'].empty else 0
    q5 = iter_data[iter_data['Metric'] == 'Q5']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Q5'].empty else 0
    business = iter_data[iter_data['Metric'] == 'Business']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Business'].empty else 0
    government = iter_data[iter_data['Metric'] == 'Government']['Avg'].values[0] if not iter_data[iter_data['Metric'] == 'Government'].empty else 0
    
    # 总和应该等于1（或接近1）
    total = q1 + q2 + q3 + q4 + q5 + business + government
    
    return {
        'Q1': q1,
        'Q2': q2,
        'Q3': q3,
        'Q4': q4,
        'Q5': q5,
        'Business': business,
        'Government': government,
        'Total': total
    }

print("="*80)
print("总财富分析（财富占比总和检验）")
print("="*80)
print("\n理论上，所有财富占比之和应该 = 1.0")
print("如果 < 1.0，说明财富在消失")
print("如果 > 1.0，说明财富在凭空产生\n")

# 关键时间点分析
key_iterations = [0, 719, 720, 1439, 1440]

for iter in key_iterations:
    wealth = calculate_total_wealth(iter)
    day = iter // 24
    hour = iter % 24
    
    print(f"\nDay {day}, Hour {hour} (Iteration {iter}):")
    print(f"  Q1:         {wealth['Q1']:.6f}")
    print(f"  Q2:         {wealth['Q2']:.6f}")
    print(f"  Q3:         {wealth['Q3']:.6f}")
    print(f"  Q4:         {wealth['Q4']:.6f}")
    print(f"  Q5:         {wealth['Q5']:.6f}")
    print(f"  Business:   {wealth['Business']:.6f}")
    print(f"  Government: {wealth['Government']:.6f}")
    print(f"  ---------------------")
    print(f"  总和:       {wealth['Total']:.6f}")
    
    if wealth['Total'] < 0.99:
        loss = (1.0 - wealth['Total']) * 100
        print(f"  ⚠️ 财富消失: {loss:.2f}%")
    elif wealth['Total'] > 1.01:
        gain = (wealth['Total'] - 1.0) * 100
        print(f"  ⚠️ 财富增加: {gain:.2f}%")
    else:
        print(f"  ✅ 财富守恒")

# 计算财富消失速度
print("\n" + "="*80)
print("财富消失速度分析")
print("="*80)

# Day 0 -> Day 30
wealth_day0 = calculate_total_wealth(0)
wealth_day30_before = calculate_total_wealth(719)
wealth_day30_after = calculate_total_wealth(720)

print(f"\nDay 0 -> Day 30 (月底前):")
print(f"  总财富: {wealth_day0['Total']:.6f} -> {wealth_day30_before['Total']:.6f}")
print(f"  消失: {(wealth_day0['Total'] - wealth_day30_before['Total'])*100:.2f}%")

print(f"\nDay 30 月底结算瞬间:")
print(f"  总财富: {wealth_day30_before['Total']:.6f} -> {wealth_day30_after['Total']:.6f}")
print(f"  变化: {(wealth_day30_after['Total'] - wealth_day30_before['Total'])*100:.2f}%")

# Day 30 -> Day 60
wealth_day60_before = calculate_total_wealth(1439)
wealth_day60_after = calculate_total_wealth(1440)

print(f"\nDay 30 -> Day 60 (月底前):")
print(f"  总财富: {wealth_day30_after['Total']:.6f} -> {wealth_day60_before['Total']:.6f}")
print(f"  变化: {(wealth_day60_before['Total'] - wealth_day30_after['Total'])*100:.2f}%")

print(f"\nDay 60 月底结算瞬间:")
print(f"  总财富: {wealth_day60_before['Total']:.6f} -> {wealth_day60_after['Total']:.6f}")
print(f"  变化: {(wealth_day60_after['Total'] - wealth_day60_before['Total'])*100:.2f}%")

print("\n" + "="*80)
print("结论")
print("="*80)
print("""
如果总财富占比之和 ≠ 1.0，说明系统存在财富守恒问题：
1. 财富消失：死亡、破产等导致财富凭空消失
2. 财富创造：某些机制凭空创造财富
3. 计算错误：财富占比计算有误

Government财富占比恶化可能是因为：
- 分母(total_wealth)在减少，而非分子(Government.wealth)暴跌
""")
