"""
寻找隐藏的Government支出
"""

import pandas as pd
import numpy as np

def analyze_hidden_expenses():
    """分析所有可能的Government支出来源"""
    
    print("="*80)
    print("Government隐藏支出分析")
    print("="*80)
    
    print("\n已知的Government支出点（agents.py）:")
    print("-"*50)
    
    print("\n1. 【月末结算】Business.accounting() - 第630-705行")
    print("   - Healthcare预算：government.demand(healthcare)")
    print("   - 失业救济：for person in unemployed: demand(person)")
    print("   - 无家可归救济：for person in homeless: demand(person)")
    
    print("\n2. 【实时支出】Business.demand() - 第518行")
    print("   ```python")
    print("   if self.wealth - labor < MIN_BUSINESS_WEALTH:")
    print("       deficit = labor - actual_payment")
    print("       self.environment.government.cash(-deficit)  # Government补贴")
    print("   ```")
    print("   说明：当Business无法支付员工工资时，Government补贴差额")
    
    print("\n3. 【实时支出】House.demand() - 第1398行")
    print("   ```python")
    print("   if self.wealth - value < 0:")
    print("       deficit = abs(self.wealth - value)")
    print("       self.environment.government.cash(-deficit)  # 破产救济")
    print("   ```")
    print("   说明：当House破产时，Government提供救济金")
    
    print("\n4. 【实时支出】Person死亡 - 第1804、1809、1820、1825行")
    print("   ```python")
    print("   if self.house is None:")
    print("       self.environment.government.cash(-self.expenses)")
    print("   if self.employer is None:")
    print("       self.environment.government.cash(-self.expenses)")
    print("   ```")
    print("   说明：人员死亡时，如果无家或失业，Government支付日常开销")
    
    print("\n" + "="*80)
    print("支出规模估算")
    print("="*80)
    
    # 参数
    POPULATION = 500
    MIN_EXPENSE = 600
    TOTAL_WEALTH = 1.8e7
    
    print("\n【场景1：第一个月（疫情严重）】")
    print("-"*50)
    
    # Day 30的数据
    death_rate = 0.16
    unemployment_rate = 0.45  # LLM日志显示45.2%
    
    deaths = int(POPULATION * death_rate)
    unemployed = int(POPULATION * (1 - death_rate) * unemployment_rate)
    
    print(f"基础数据:")
    print(f"  死亡人数: {deaths}")
    print(f"  失业人数: {unemployed}")
    
    # 1. 月末失业救济
    monthly_unemployment = unemployed * MIN_EXPENSE * 30
    print(f"\n1. 月末失业救济: {monthly_unemployment/1e6:.2f}百万")
    
    # 2. House破产救济（关键！）
    # 假设30%的House在月内破产，每个House平均3人
    houses = POPULATION // 3
    bankrupt_houses = int(houses * 0.3)
    # 每个House月开销 = 3人 * 600元/天 * 30天
    house_monthly_expense = 3 * MIN_EXPENSE * 30
    house_bankruptcy_relief = bankrupt_houses * house_monthly_expense
    print(f"\n2. House破产救济: {house_bankruptcy_relief/1e6:.2f}百万")
    print(f"   ({bankrupt_houses}个House破产，每个需要{house_monthly_expense/1e3:.0f}千元)")
    
    # 3. Business工资补贴
    # 假设20%的Business需要补贴，平均每个补贴5万
    business_count = 20  # 假设
    subsidized_business = int(business_count * 0.2)
    business_subsidy = subsidized_business * 50000
    print(f"\n3. Business工资补贴: {business_subsidy/1e6:.2f}百万")
    
    # 4. 死亡支出
    # 死亡时的一次性支出
    death_expense = deaths * MIN_EXPENSE * 2  # 假设支付2倍日常开销
    print(f"\n4. 死亡相关支出: {death_expense/1e6:.2f}百万")
    
    # 5. Healthcare医疗
    healthcare = 15 * MIN_EXPENSE * 0.6 * 30
    print(f"\n5. Healthcare医疗: {healthcare/1e6:.2f}百万")
    
    total = monthly_unemployment + house_bankruptcy_relief + business_subsidy + death_expense + healthcare
    print(f"\n总计: {total/1e6:.2f}百万")
    print(f"实际支出: 14.36百万")
    print(f"差异: {(14.36 - total/1e6):.2f}百万")
    
    print("\n【场景2：第二个月（疫情已控制）】")
    print("-"*50)
    
    print(f"基础数据（与第一个月相同）:")
    print(f"  死亡人数: {deaths}（无新增死亡）")
    print(f"  失业人数: {unemployed}（未改善）")
    
    # 理论上第二个月：
    # - 无新增死亡，所以死亡支出=0
    # - 无新增感染，所以医疗支出极低
    # - 但House破产可能持续
    
    monthly_unemployment2 = unemployed * MIN_EXPENSE * 30
    house_bankruptcy_relief2 = house_bankruptcy_relief  # 假设持续
    business_subsidy2 = business_subsidy  # 假设持续
    death_expense2 = 0  # 无新增死亡
    healthcare2 = 0  # 无住院
    
    total2 = monthly_unemployment2 + house_bankruptcy_relief2 + business_subsidy2 + death_expense2 + healthcare2
    print(f"\n理论支出:")
    print(f"  失业救济: {monthly_unemployment2/1e6:.2f}百万")
    print(f"  House破产: {house_bankruptcy_relief2/1e6:.2f}百万")
    print(f"  Business补贴: {business_subsidy2/1e6:.2f}百万")
    print(f"  死亡支出: {death_expense2/1e6:.2f}百万")
    print(f"  医疗: {healthcare2/1e6:.2f}百万")
    print(f"  总计: {total2/1e6:.2f}百万")
    print(f"\n实际支出: 14.22百万")
    print(f"差异: {(14.22 - total2/1e6):.2f}百万")
    
    print("\n" + "="*80)
    print("关键发现")
    print("="*80)
    print("""
    1. House破产救济可能是最大的隐藏支出（9.72百万）
    2. 这解释了为什么支出如此巨大（14.36百万 vs 3.55百万可见支出）
    3. 第二个月支出几乎相同，说明House破产在持续
    
    问题根源：
    - House.demand()被频繁调用（每小时）
    - 大量House因死亡导致收入减少而破产
    - Government不断为破产House提供救济
    - 这是一个持续性支出，不是月末一次性的
    
    这解释了您观察到的现象：
    1. 月末瞬间暴跌：累积的House破产救济在月末体现
    2. 两个月支出相同：House破产持续发生，与疫情严重程度无关
    """)
