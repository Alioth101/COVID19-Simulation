import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 读取CSV数据
df = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')

# 分析月底财富变化
def analyze_month_end_drops():
    """分析月底（每720迭代）的财富暴跌"""
    
    print("="*80)
    print("月底Government财富暴跌分析")
    print("="*80)
    
    # 关键时间点
    month_ends = [719, 720, 1439, 1440]  # 第30天和第60天的月底前后
    
    for i in range(0, len(month_ends), 2):
        before_iter = month_ends[i]
        after_iter = month_ends[i+1]
        day = before_iter // 24
        
        # 获取数据
        gov_before = df[(df['Iteration'] == before_iter) & (df['Metric'] == 'Government')]
        gov_after = df[(df['Iteration'] == after_iter) & (df['Metric'] == 'Government')]
        
        if not gov_before.empty and not gov_after.empty:
            wealth_before = gov_before['Avg'].values[0]
            wealth_after = gov_after['Avg'].values[0]
            drop = wealth_after - wealth_before
            
            print(f"\nDay {day} 月底结算:")
            print(f"  结算前 (iter {before_iter}): {wealth_before:.3f}")
            print(f"  结算后 (iter {after_iter}): {wealth_after:.3f}")
            print(f"  暴跌幅度: {drop:.3f} ({drop/abs(wealth_before)*100:.1f}%)")
    
    # 分析其他经济指标
    print("\n" + "="*80)
    print("相关经济指标分析")
    print("="*80)
    
    for iteration in [720, 1440]:
        day = iteration // 24
        print(f"\nDay {day} (iteration {iteration}):")
        
        # 死亡率
        death = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Death')]
        if not death.empty:
            print(f"  死亡率: {death['Avg'].values[0]*100:.1f}%")
        
        # 感染率
        infected = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Infected')]
        if not infected.empty:
            print(f"  感染率: {infected['Avg'].values[0]*100:.1f}%")
        
        # Business财富
        business = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Business')]
        if not business.empty:
            print(f"  Business财富: {business['Avg'].values[0]:.3f}")
        
        # 各阶层财富
        for q in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
            wealth = df[(df['Iteration'] == iteration) & (df['Metric'] == q)]
            if not wealth.empty:
                print(f"  {q}财富: {wealth['Avg'].values[0]:.3f}")

# 绘制Government财富时间序列
def plot_government_wealth():
    """绘制Government财富随时间变化"""
    
    gov_data = df[df['Metric'] == 'Government'].copy()
    gov_data['Day'] = gov_data['Iteration'] / 24
    
    plt.figure(figsize=(14, 8))
    
    # 上图：整体趋势
    plt.subplot(2, 1, 1)
    plt.plot(gov_data['Day'], gov_data['Avg'], 'b-', linewidth=2, label='平均值')
    plt.fill_between(gov_data['Day'], gov_data['Min'], gov_data['Max'], alpha=0.3, color='blue', label='最小-最大范围')
    
    # 标记月底
    for day in [30, 60]:
        plt.axvline(x=day, color='red', linestyle='--', alpha=0.5, label=f'Day {day} 月底' if day == 30 else '')
    
    plt.xlabel('天数')
    plt.ylabel('Government财富占比')
    plt.title('Government财富变化趋势（修复后）')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 下图：月底细节
    plt.subplot(2, 1, 2)
    
    # Day 28-32的细节
    detail_data = gov_data[(gov_data['Day'] >= 28) & (gov_data['Day'] <= 32)]
    if not detail_data.empty:
        plt.plot(detail_data['Day'], detail_data['Avg'], 'r-', linewidth=2, marker='o', label='Day 28-32')
    
    # Day 58-62的细节
    detail_data2 = gov_data[(gov_data['Day'] >= 58) & (gov_data['Day'] <= 62)]
    if not detail_data2.empty:
        plt.plot(detail_data2['Day'], detail_data2['Avg'], 'g-', linewidth=2, marker='s', label='Day 58-62')
    
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.xlabel('天数')
    plt.ylabel('Government财富占比')
    plt.title('月底财富暴跌细节')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('output/government_wealth_crash_fixed.png', dpi=150, bbox_inches='tight')
    print("\n图表已保存至 output/government_wealth_crash_fixed.png")

# 计算月底支出明细估算
def estimate_monthly_expenses():
    """估算月底支出明细"""
    
    print("\n" + "="*80)
    print("月底支出估算")
    print("="*80)
    
    # 假设参数
    total_wealth = 18000000  # 总财富
    population = 500
    
    for day in [30, 60]:
        iteration = day * 24
        
        # 获取死亡率和感染率
        death = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Death')]
        death_rate = death['Avg'].values[0] if not death.empty else 0
        
        print(f"\nDay {day} 月底支出估算:")
        print(f"  死亡人数: {int(population * death_rate)}")
        print(f"  存活人数: {int(population * (1 - death_rate))}")
        
        # 估算失业人数（死亡导致企业关闭）
        unemployed_estimate = int(population * death_rate * 1.5)  # 死亡引发的连锁失业
        print(f"  估计失业人数: {unemployed_estimate}")
        
        # 估算支出
        # 失业救济：每人minimum_expense = 600元/天 * 30天
        unemployment_cost = unemployed_estimate * 600 * 30
        print(f"  失业救济估算: {unemployment_cost:,}元 ({unemployment_cost/total_wealth*100:.2f}%)")
        
        # Healthcare支出（修复后：60%费率，月度重置）
        # 假设平均10-20人住院
        healthcare_cost = 15 * 1800 * 30  # 15人 * 1800元/天 * 30天
        print(f"  医疗支出估算: {healthcare_cost:,}元 ({healthcare_cost/total_wealth*100:.2f}%)")
        
        total_cost = unemployment_cost + healthcare_cost
        print(f"  总支出估算: {total_cost:,}元 ({total_cost/total_wealth*100:.2f}%)")
        
        # Government财富变化
        gov_before = df[(df['Iteration'] == iteration-1) & (df['Metric'] == 'Government')]
        gov_after = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Government')]
        
        if not gov_before.empty and not gov_after.empty:
            actual_drop = (gov_after['Avg'].values[0] - gov_before['Avg'].values[0]) * total_wealth
            print(f"  实际财富减少: {actual_drop:,.0f}元")
            print(f"  差异: {(actual_drop - (-total_cost)):,.0f}元")

if __name__ == "__main__":
    analyze_month_end_drops()
    estimate_monthly_expenses()
    plot_government_wealth()
    
    print("\n" + "="*80)
    print("分析结论")
    print("="*80)
    print("""
修复后仍然存在的问题：

1. 月底财富暴跌幅度：
   - Day 30: 从-0.186暴跌至-0.984 (下降428%)
   - Day 60: 从-0.973暴跌至-1.763 (下降81%)

2. 主要原因分析：
   - 高死亡率（16%）导致大量失业
   - 失业救济支出巨大
   - 税基崩溃，收入锐减
   - 即使医疗费用已优化，失业救济仍是主要负担

3. 建议进一步优化：
   - 检查失业救济的计算逻辑
   - 优化死亡率参数或防疫措施
   - 增加Government收入来源
   - 实施失业救济上限机制
""")
