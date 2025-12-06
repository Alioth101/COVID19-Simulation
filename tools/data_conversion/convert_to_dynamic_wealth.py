"""
将固定分母的财富比例转换为动态分母的财富比例
保持CSV格式完全一致，便于使用原始可视化脚本
"""

import pandas as pd
import numpy as np

# 配置参数
INITIAL_TOTAL_WEALTH = 1.8e7  # 1800万初始总财富
INPUT_CSV = 'output/graph_batch/resultsP50DeepSeepV3.csv'
OUTPUT_CSV = 'output/graph_batch/resultsP50DeepSeepV3_dynamic.csv'

def convert_to_dynamic_wealth(input_csv, output_csv):
    """
    转换财富统计：从固定分母改为动态分母
    """
    print("="*80)
    print("财富统计转换工具：固定分母 → 动态分母")
    print("="*80)
    
    # 读取原始数据
    print(f"\n📁 读取原始数据: {input_csv}")
    df = pd.read_csv(input_csv)
    print(f"   数据行数: {len(df)}")
    print(f"   时间跨度: {df['Iteration'].max()+1} 迭代")
    
    # 创建新的DataFrame
    df_new = df.copy()
    
    # 统计信息收集
    stats = {
        'iterations': [],
        'fixed_total': [],
        'dynamic_total': [],
        'ratio': []
    }
    
    # 处理每个时间点
    print("\n🔄 转换财富比例...")
    unique_iterations = sorted(df['Iteration'].unique())
    
    for i, iteration in enumerate(unique_iterations):
        # 获取该时间点的所有数据
        iter_mask = df['Iteration'] == iteration
        iter_data = df[iter_mask]
        
        # Step 1: 从比例恢复绝对值
        absolute_wealth = {}
        wealth_metrics = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']
        
        for metric in wealth_metrics:
            metric_data = iter_data[iter_data['Metric'] == metric]
            if not metric_data.empty:
                # 原始比例 × 固定总财富 = 绝对值
                absolute_wealth[metric] = {
                    'Avg': metric_data['Avg'].values[0] * INITIAL_TOTAL_WEALTH,
                    'Std': metric_data['Std'].values[0] * INITIAL_TOTAL_WEALTH,
                    'Min': metric_data['Min'].values[0] * INITIAL_TOTAL_WEALTH,
                    'Max': metric_data['Max'].values[0] * INITIAL_TOTAL_WEALTH
                }
        
        # Step 2: 计算动态总财富（所有部分绝对值之和）
        dynamic_total_wealth = sum(absolute_wealth[m]['Avg'] for m in wealth_metrics if m in absolute_wealth)
        
        # 防止除零
        if abs(dynamic_total_wealth) < 1:
            dynamic_total_wealth = 1.0
        
        # Step 3: 用动态总财富重新计算比例
        for metric in wealth_metrics:
            if metric in absolute_wealth:
                # 找到对应的行
                mask = (df_new['Iteration'] == iteration) & (df_new['Metric'] == metric)
                
                # 更新为新比例（绝对值 / 动态总财富）
                df_new.loc[mask, 'Avg'] = absolute_wealth[metric]['Avg'] / dynamic_total_wealth
                df_new.loc[mask, 'Std'] = absolute_wealth[metric]['Std'] / abs(dynamic_total_wealth)
                df_new.loc[mask, 'Min'] = absolute_wealth[metric]['Min'] / dynamic_total_wealth
                df_new.loc[mask, 'Max'] = absolute_wealth[metric]['Max'] / dynamic_total_wealth
        
        # 收集统计信息
        stats['iterations'].append(iteration)
        stats['fixed_total'].append(INITIAL_TOTAL_WEALTH)
        stats['dynamic_total'].append(dynamic_total_wealth)
        stats['ratio'].append(dynamic_total_wealth / INITIAL_TOTAL_WEALTH)
        
        # 进度显示
        if i % 100 == 0 or i == len(unique_iterations) - 1:
            day = iteration / 24
            print(f"   处理进度: Day {day:.1f} (Iteration {iteration})")
            if iteration in [0, 720, 1440]:  # 关键时间点
                print(f"      固定总财富: {INITIAL_TOTAL_WEALTH/1e6:.1f}M")
                print(f"      动态总财富: {dynamic_total_wealth/1e6:.1f}M")
                print(f"      比例: {dynamic_total_wealth/INITIAL_TOTAL_WEALTH:.2%}")
    
    # 保存转换后的CSV
    print(f"\n💾 保存转换后的数据: {output_csv}")
    df_new.to_csv(output_csv, index=False)
    
    # 分析关键时间点的变化
    print("\n📊 关键时间点分析:")
    print("-"*80)
    print(f"{'时间点':<10} {'原始Gov占比':<15} {'动态Gov占比':<15} {'变化':<10}")
    print("-"*80)
    
    for day in [0, 30, 60]:
        iteration = day * 24
        
        # 原始数据
        orig_gov = df[(df['Iteration'] == iteration) & (df['Metric'] == 'Government')]
        new_gov = df_new[(df_new['Iteration'] == iteration) & (df_new['Metric'] == 'Government')]
        
        if not orig_gov.empty and not new_gov.empty:
            orig_ratio = orig_gov['Avg'].values[0]
            new_ratio = new_gov['Avg'].values[0]
            change = new_ratio - orig_ratio
            
            print(f"Day {day:<6} {orig_ratio:>14.3f} {new_ratio:>14.3f} {change:>+9.3f}")
    
    # 验证财富守恒
    print("\n✅ 财富守恒验证（动态分母后各部分之和应该=1）:")
    for day in [0, 30, 60]:
        iteration = day * 24
        iter_data = df_new[df_new['Iteration'] == iteration]
        
        total = 0
        for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']:
            metric_data = iter_data[iter_data['Metric'] == metric]
            if not metric_data.empty:
                total += metric_data['Avg'].values[0]
        
        print(f"   Day {day}: 总和 = {total:.6f} {'✅' if abs(total - 1.0) < 0.01 else '❌'}")
    
    # 导出统计信息
    stats_df = pd.DataFrame(stats)
    stats_csv = 'output/wealth_dynamics_stats.csv'
    stats_df.to_csv(stats_csv, index=False)
    print(f"\n📈 动态总财富统计已导出: {stats_csv}")
    
    return df_new, stats_df

def create_comparison_csv(df_orig, df_new):
    """
    创建对比CSV，包含原始和动态两种统计
    """
    print("\n🔧 创建对比数据集...")
    
    comparison_data = []
    
    for iteration in [0, 720, 1440]:  # Day 0, 30, 60
        day = iteration / 24
        
        for metric in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Business', 'Government']:
            orig = df_orig[(df_orig['Iteration'] == iteration) & (df_orig['Metric'] == metric)]
            new = df_new[(df_new['Iteration'] == iteration) & (df_new['Metric'] == metric)]
            
            if not orig.empty and not new.empty:
                comparison_data.append({
                    'Day': day,
                    'Iteration': iteration,
                    'Metric': metric,
                    'Original_Ratio': orig['Avg'].values[0],
                    'Dynamic_Ratio': new['Avg'].values[0],
                    'Difference': new['Avg'].values[0] - orig['Avg'].values[0],
                    'Absolute_Wealth': orig['Avg'].values[0] * INITIAL_TOTAL_WEALTH
                })
    
    comp_df = pd.DataFrame(comparison_data)
    comp_csv = 'output/wealth_comparison.csv'
    comp_df.to_csv(comp_csv, index=False)
    print(f"   对比数据已导出: {comp_csv}")
    
    # 打印对比表格
    print("\n📋 Government财富占比对比:")
    print("-"*70)
    print(f"{'Day':<8} {'固定分母':<15} {'动态分母':<15} {'差异':<15}")
    print("-"*70)
    
    for day in [0, 30, 60]:
        gov_data = comp_df[(comp_df['Day'] == day) & (comp_df['Metric'] == 'Government')]
        if not gov_data.empty:
            row = gov_data.iloc[0]
            print(f"Day {day:<4} {row['Original_Ratio']:>14.3%} {row['Dynamic_Ratio']:>14.3%} "
                  f"{row['Difference']:>+14.3%}")
    
    return comp_df

def main():
    """主函数"""
    
    # 转换数据
    df_orig = pd.read_csv(INPUT_CSV)
    df_new, stats_df = convert_to_dynamic_wealth(INPUT_CSV, OUTPUT_CSV)
    
    # 创建对比数据
    comp_df = create_comparison_csv(df_orig, df_new)
    
    print("\n" + "="*80)
    print("✅ 转换完成！")
    print("="*80)
    print("\n生成的文件:")
    print(f"1. {OUTPUT_CSV} - 使用动态分母的新CSV（可直接用原始可视化脚本）")
    print(f"2. output/wealth_dynamics_stats.csv - 动态总财富变化统计")
    print(f"3. output/wealth_comparison.csv - 固定vs动态分母对比")
    
    print("\n使用方法:")
    print("1. 对比可视化:")
    print(f"   python visualize_graph_batch.py {INPUT_CSV}  # 原始（固定分母）")
    print(f"   python visualize_graph_batch.py {OUTPUT_CSV} # 修正（动态分母）")
    print("\n2. 或直接运行对比脚本:")
    print("   python compare_visualizations.py")
    
    print("\n关键发现:")
    print(f"• Day 0: 动态总财富 = {stats_df[stats_df['iterations']==0]['dynamic_total'].values[0]/1e6:.1f}M (100%)")
    print(f"• Day 30: 动态总财富 = {stats_df[stats_df['iterations']==720]['dynamic_total'].values[0]/1e6:.1f}M "
          f"({stats_df[stats_df['iterations']==720]['ratio'].values[0]:.1%})")
    print(f"• Day 60: 动态总财富 = {stats_df[stats_df['iterations']==1440]['dynamic_total'].values[0]/1e6:.1f}M "
          f"({stats_df[stats_df['iterations']==1440]['ratio'].values[0]:.1%})")
    
    # 判断问题严重程度
    day60_ratio = stats_df[stats_df['iterations']==1440]['ratio'].values[0]
    if day60_ratio < 0:
        print("\n⚠️ 严重问题：系统总财富变为负数！整个经济体系已经崩溃。")
    elif day60_ratio < 0.5:
        print("\n⚠️ 严重问题：系统损失超过50%的财富，经济严重萧条。")
    else:
        print("\n✅ 系统财富保持相对稳定。")

if __name__ == "__main__":
    main()
