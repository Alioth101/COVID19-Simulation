#!/usr/bin/env python3
"""
诊断迭代活动
分析哪些迭代有经济活动，哪些没有
"""

import re
from collections import defaultdict

def analyze_iteration_activity(log_file="debug_cashflow.log"):
    """分析每个迭代的活动"""
    
    iteration_activity = defaultdict(list)
    iteration_pattern = re.compile(r'\[Iter\s*(\d+)\s+Day\s*(\d+)H\s*(\d+)\]')
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = iteration_pattern.match(line)
                if match:
                    iteration = int(match.group(1))
                    day = int(match.group(2))
                    hour = int(match.group(3))
                    
                    # 记录活动类型
                    if 'ITERATION START' in line:
                        iteration_activity[iteration].append('START')
                    elif 'House.demand' in line:
                        iteration_activity[iteration].append('DEMAND')
                    elif 'House.supply' in line:
                        iteration_activity[iteration].append('SUPPLY')
                    elif 'Business' in line:
                        iteration_activity[iteration].append('BUSINESS')
                    elif 'Person' in line:
                        iteration_activity[iteration].append('PERSON')
                    elif 'STATISTICS' in line:
                        iteration_activity[iteration].append('STATS')
                    else:
                        iteration_activity[iteration].append('OTHER')
    except FileNotFoundError:
        print(f"❌ File {log_file} not found")
        return None
    
    return iteration_activity

def print_analysis(activity_dict):
    """打印分析结果"""
    
    if not activity_dict:
        print("❌ No data to analyze")
        return
    
    print("\n" + "="*60)
    print("📊 ITERATION ACTIVITY ANALYSIS")
    print("="*60)
    
    # 找出所有迭代范围
    all_iterations = sorted(activity_dict.keys())
    min_iter = min(all_iterations) if all_iterations else 0
    max_iter = max(all_iterations) if all_iterations else 0
    
    print(f"\n📈 Overview:")
    print(f"   Total iterations with activity: {len(all_iterations)}")
    print(f"   Range: Iter {min_iter} to Iter {max_iter}")
    print(f"   Total expected: {max_iter + 1}")
    
    # 查找缺失的迭代
    missing_iterations = []
    for i in range(min_iter, max_iter + 1):
        if i not in activity_dict:
            missing_iterations.append(i)
    
    if missing_iterations:
        print(f"\n❌ Missing iterations (no logs): {len(missing_iterations)}")
        if len(missing_iterations) <= 20:
            print(f"   {missing_iterations}")
        else:
            print(f"   First 20: {missing_iterations[:20]}")
            print(f"   ... and {len(missing_iterations) - 20} more")
    else:
        print(f"\n✅ All iterations have logs!")
    
    # 分析前30个迭代
    print(f"\n📋 First 30 iterations detail:")
    print(f"{'Iter':<6} {'Day':<4} {'Hour':<5} {'Activities':<20} {'Count':<6}")
    print("-" * 50)
    
    for i in range(min(30, max_iter + 1)):
        day = i // 24
        hour = i % 24
        if i in activity_dict:
            activities = activity_dict[i]
            activity_types = set(activities)
            count = len(activities)
            # 简化显示
            if 'START' in activity_types:
                activity_str = "START"
            elif 'DEMAND' in activity_types:
                activity_str = f"DEMAND({activities.count('DEMAND')})"
            else:
                activity_str = ','.join(list(activity_types)[:2])
        else:
            activity_str = "NO ACTIVITY"
            count = 0
        
        print(f"{i:<6} {day:<4} {hour:<5} {activity_str:<20} {count:<6}")
    
    # 统计活动类型
    print(f"\n📊 Activity type summary:")
    activity_counts = defaultdict(int)
    for activities in activity_dict.values():
        for activity in activities:
            activity_counts[activity] += 1
    
    for activity_type, count in sorted(activity_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {activity_type:<15}: {count:,}")
    
    # 分析时间模式
    print(f"\n⏰ Time pattern analysis:")
    hour_activity = defaultdict(int)
    for iteration, activities in activity_dict.items():
        hour = iteration % 24
        hour_activity[hour] += len(activities)
    
    print(f"   Most active hours:")
    for hour, count in sorted(hour_activity.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"      Hour {hour:2d}: {count:,} activities")
    
    print(f"\n   Least active hours:")
    for hour, count in sorted(hour_activity.items(), key=lambda x: x[1])[:5]:
        print(f"      Hour {hour:2d}: {count:,} activities")

def main():
    """主函数"""
    print("🔍 Iteration Activity Diagnostic Tool")
    print("="*60)
    
    # 分析活动
    activity = analyze_iteration_activity()
    
    if activity:
        print_analysis(activity)
        
        # 提供建议
        print(f"\n💡 Recommendations:")
        
        # 检查是否有0-9的活动
        early_iterations = [i for i in activity.keys() if i < 10]
        if not early_iterations:
            print("   ⚠️ No activity in iterations 0-9!")
            print("      - This suggests nighttime hours (0:00-10:00) have no economic activity")
            print("      - This is NORMAL if agents don't shop at night")
            print("      - Consider adding 'ITERATION START' logging to confirm iterations run")
        else:
            print(f"   ✅ Found {len(early_iterations)} iterations with activity in 0-9 range")
        
        # 检查日志延迟
        print(f"\n   📝 To check for log delays:")
        print(f"      1. Note the current iteration when viewing logs")
        print(f"      2. Check the last logged iteration")
        print(f"      3. If difference > 5, there may be buffering issues")
        print(f"      4. The fixes applied should resolve this")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
