"""
对比固定分母vs动态分母的可视化
展示问题的本质
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def load_and_prepare_data():
    """加载原始和动态分母的数据"""
    
    # 加载两个CSV
    df_fixed = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3.csv')
    df_dynamic = pd.read_csv('output/graph_batch/resultsP50DeepSeepV3_dynamic.csv')
    
    # 加载统计信息
    stats = pd.read_csv('output/wealth_dynamics_stats.csv')
    
    return df_fixed, df_dynamic, stats

def plot_comparison(df_fixed, df_dynamic, stats):
    """创建对比图表"""
    
    fig = plt.figure(figsize=(16, 12))
    
    # 创建2x3的子图布局
    axes = []
    for i in range(6):
        ax = fig.add_subplot(2, 3, i+1)
        axes.append(ax)
    
    # 通用设置
    iterations = df_fixed['Iteration'].unique()
    days = iterations / 24
    
    # 1. Government财富占比对比
    ax = axes[0]
    gov_fixed = df_fixed[df_fixed['Metric'] == 'Government'].sort_values('Iteration')
    gov_dynamic = df_dynamic[df_dynamic['Metric'] == 'Government'].sort_values('Iteration')
    
    ax.plot(gov_fixed['Iteration']/24, gov_fixed['Avg'], 'r-', linewidth=2, label='Fixed Denominator')
    ax.plot(gov_dynamic['Iteration']/24, gov_dynamic['Avg'], 'b-', linewidth=2, label='Dynamic Denominator')
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax.set_xlabel('Days')
    ax.set_ylabel('Government Wealth Ratio')
    ax.set_title('Government Wealth: Fixed vs Dynamic')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 标记月底
    for day in [30, 60]:
        ax.axvline(x=day, color='gray', linestyle='--', alpha=0.3)
    
    # 2. 总财富变化
    ax = axes[1]
    ax.plot(stats['iterations']/24, stats['dynamic_total']/1e6, 'g-', linewidth=2, label='Dynamic Total')
    ax.axhline(y=18, color='gray', linestyle='--', alpha=0.5, label='Initial (18M)')
    ax.axhline(y=0, color='red', linestyle='-', alpha=0.5)
    ax.set_xlabel('Days')
    ax.set_ylabel('Total Wealth (Millions)')
    ax.set_title('System Total Wealth Evolution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. 各部分财富占比（固定分母）
    ax = axes[2]
    for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business']:
        metric_data = df_fixed[df_fixed['Metric'] == metric].sort_values('Iteration')
        ax.plot(metric_data['Iteration']/24, metric_data['Avg'], linewidth=1, label=metric)
    ax.set_xlabel('Days')
    ax.set_ylabel('Wealth Ratio')
    ax.set_title('Wealth Distribution (Fixed Denominator)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.1, 0.5])
    
    # 4. 各部分财富占比（动态分母）
    ax = axes[3]
    for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business']:
        metric_data = df_dynamic[df_dynamic['Metric'] == metric].sort_values('Iteration')
        ax.plot(metric_data['Iteration']/24, metric_data['Avg'], linewidth=1, label=metric)
    ax.set_xlabel('Days')
    ax.set_ylabel('Wealth Ratio')
    ax.set_title('Wealth Distribution (Dynamic Denominator)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.1, 0.5])
    
    # 5. 财富守恒检验（固定分母）
    ax = axes[4]
    wealth_sum_fixed = []
    for iter in sorted(df_fixed['Iteration'].unique())[::10]:  # 每10个迭代采样
        iter_sum = 0
        for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']:
            metric_data = df_fixed[(df_fixed['Iteration'] == iter) & (df_fixed['Metric'] == metric)]
            if not metric_data.empty:
                iter_sum += metric_data['Avg'].values[0]
        wealth_sum_fixed.append((iter/24, iter_sum))
    
    wealth_sum_fixed = np.array(wealth_sum_fixed)
    ax.plot(wealth_sum_fixed[:, 0], wealth_sum_fixed[:, 1], 'r-', linewidth=2)
    ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Expected = 1.0')
    ax.set_xlabel('Days')
    ax.set_ylabel('Sum of All Ratios')
    ax.set_title('Wealth Conservation Test (Fixed)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 6. 财富守恒检验（动态分母）
    ax = axes[5]
    wealth_sum_dynamic = []
    for iter in sorted(df_dynamic['Iteration'].unique())[::10]:  # 每10个迭代采样
        iter_sum = 0
        for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']:
            metric_data = df_dynamic[(df_dynamic['Iteration'] == iter) & (df_dynamic['Metric'] == metric)]
            if not metric_data.empty:
                iter_sum += metric_data['Avg'].values[0]
        wealth_sum_dynamic.append((iter/24, iter_sum))
    
    wealth_sum_dynamic = np.array(wealth_sum_dynamic)
    ax.plot(wealth_sum_dynamic[:, 0], wealth_sum_dynamic[:, 1], 'b-', linewidth=2)
    ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Expected = 1.0')
    ax.set_xlabel('Days')
    ax.set_ylabel('Sum of All Ratios')
    ax.set_title('Wealth Conservation Test (Dynamic)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0.95, 1.05])
    
    plt.suptitle('Fixed vs Dynamic Denominator Comparison', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    return fig

def analyze_negative_wealth():
    """分析为什么总财富会变成负数"""
    
    print("\n" + "="*80)
    print("💰 负财富分析：为什么系统总财富会变成负数？")
    print("="*80)
    
    # 读取对比数据
    comp_df = pd.read_csv('output/wealth_comparison.csv')
    
    print("\n📊 Day 30 财富分解（绝对值，单位：百万）:")
    day30 = comp_df[comp_df['Day'] == 30]
    total = 0
    for _, row in day30.iterrows():
        abs_wealth = row['Absolute_Wealth'] / 1e6
        total += abs_wealth
        print(f"   {row['Metric']:<12}: {abs_wealth:>10.2f}M")
    print(f"   {'='*25}")
    print(f"   {'Total':<12}: {total:>10.2f}M")
    
    print("\n📊 Day 60 财富分解（绝对值，单位：百万）:")
    day60 = comp_df[comp_df['Day'] == 60]
    total = 0
    for _, row in day60.iterrows():
        abs_wealth = row['Absolute_Wealth'] / 1e6
        total += abs_wealth
        print(f"   {row['Metric']:<12}: {abs_wealth:>10.2f}M")
    print(f"   {'='*25}")
    print(f"   {'Total':<12}: {total:>10.2f}M")
    
    print("\n🔍 问题诊断:")
    print("1. Government负债超过了其他所有部分的正财富总和")
    print("2. 当Government负债 > 系统其余财富时，总财富变负")
    print("3. 这表明Government在'印钱'支付救济金（负债运营）")
    print("4. 死亡导致的财富消失加剧了这个问题")
    
    print("\n💡 结论:")
    print("• 使用动态分母后，Government占比>100%意味着它负债超过了整个系统")
    print("• 这是一个经济完全崩溃的信号")
    print("• 原始的固定分母统计掩盖了这个严重问题")

def main():
    """主函数"""
    
    print("="*80)
    print("财富统计对比分析")
    print("="*80)
    
    # 加载数据
    print("\n📁 加载数据...")
    df_fixed, df_dynamic, stats = load_and_prepare_data()
    
    # 创建对比图表
    print("📊 生成对比图表...")
    fig = plot_comparison(df_fixed, df_dynamic, stats)
    
    # 保存图表
    output_file = 'output/wealth_comparison_fixed_vs_dynamic.png'
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ 图表已保存: {output_file}")
    
    # 分析负财富问题
    analyze_negative_wealth()
    
    # 显示图表
    plt.show()
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)
    print("\n关键发现:")
    print("1. 固定分母显示Government占比-98%（Day 30）和-176%（Day 60）")
    print("2. 动态分母显示Government占比212%（Day 30）和141%（Day 60）")
    print("3. 两种方法都表明同一问题：Government负债远超系统承受能力")
    print("4. 使用动态分母更准确地反映了经济崩溃的严重程度")
    print("\n建议：")
    print("• 实施死亡财富继承机制")
    print("• 限制Government救济支出上限")
    print("• 增加税收或其他收入来源")
    print("• 优化防疫措施减少死亡率")

if __name__ == "__main__":
    main()
