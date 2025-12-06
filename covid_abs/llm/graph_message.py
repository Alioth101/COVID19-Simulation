"""
StatusPool and decision context management specific to GraphSimulation
"""

import numpy as np
from covid_abs.llm.message import StatusPool, Decision
from covid_abs.network.agents import EconomicalStatus
from covid_abs.agents import Status, InfectionSeverity, AgentType
from covid_abs.network.util import (
    bed_time, work_time, lunch_time, free_time,
    work_day, new_day, new_month
)


class GraphStatusPool(StatusPool):
    """
    StatusPool implementation specific to GraphSimulation.
    
    Extended features:
    - Economic statistics (unemployment rate, homeless rate, business status)
    - Time context (workday, time period detection)
    - Decision context for Person/Business/House agents
    """
    
    def __init__(self, simulation, scenario_config=None):
        super().__init__(simulation)
        # Extended data structures
        self.economic_stats = {}
        self.government_policy = {}
        self.time_context = {}
        
        # 🎬 Scenario configuration for Government policy recommendations
        self.scenario_config = scenario_config or {}
        '''Scenario configuration controlling government policy behavior:
        - enable_policy_recommendation: Whether to provide dynamic policy recommendations
        - policy_recommendation_mode: 'aggressive', 'balanced', or 'conservative'
        - infection thresholds, economic weight, etc.
        '''
    
    def update_statistics(self, stats):
        """
        Update statistics (called every iteration).
        
        Args:
            stats: Statistics dictionary returned by simulation.get_statistics()
        """
        super().update_statistics(stats)
        
        # Calculate economic statistics
        self.economic_stats = {
            'unemployment_rate': self._calc_unemployment_rate(),
            'homeless_rate': self._calc_homeless_rate(),
            'business_open_rate': self._calc_business_open_rate(),
            'avg_wealth_by_stratum': self._calc_stratum_wealth(),
            'government_wealth': self.simulation.government.wealth,
            'total_wealth': self.simulation.total_wealth
        }
        
        # Update time context
        iter = self.simulation.iteration
        self.time_context = {
            'iteration': iter,
            'day': iter // 24,
            'hour': iter % 24,
            'is_bed_time': bed_time(iter),
            'is_work_time': work_time(iter),
            'is_lunch_time': lunch_time(iter),
            'is_free_time': free_time(iter),
            'is_workday': work_day(iter),
            'is_new_day': new_day(iter),
            'is_new_month': new_month(iter)
        }
    
    def _calc_unemployment_rate(self):
        """Calculate unemployment rate (ratio of unemployed in economically active population)"""
        active_population = [
            p for p in self.simulation.population
            if p.economical_status == EconomicalStatus.Active
            and p.status.name != 'Death'
        ]
        if len(active_population) == 0:
            return 0.0
        
        unemployed = [p for p in active_population if p.employer is None]
        return len(unemployed) / len(active_population)
    
    def _calc_homeless_rate(self):
        """Calculate homelessness rate"""
        total = len([p for p in self.simulation.population if p.status.name != 'Death'])
        if total == 0:
            return 0.0
        
        homeless = len([p for p in self.simulation.population 
                       if p.house is None and p.status.name != 'Death'])
        return homeless / total
    
    def _calc_business_open_rate(self):
        """Calculate business operation rate"""
        if len(self.simulation.business) == 0:
            return 0.0
        
        open_count = len([b for b in self.simulation.business if b.open])
        return open_count / len(self.simulation.business)
    
    def _calc_stratum_wealth(self):
        """Calculate average wealth by social stratum"""
        wealth_by_stratum = {}
        for stratum in range(5):
            houses = [h for h in self.simulation.houses 
                     if h.social_stratum == stratum and h.size > 0]
            if len(houses) > 0:
                avg_wealth = np.mean([h.wealth for h in houses])
            else:
                avg_wealth = 0.0
            wealth_by_stratum[f'Q{stratum+1}'] = avg_wealth
        return wealth_by_stratum
    
    def _calc_days_sustainable(self, person):
        """Calculate how many days the person's household wealth can sustain"""
        if person.house is None:
            wealth = person.wealth
        else:
            wealth = person.house.wealth
        
        if person.expenses <= 0:
            return 999  # No expenses, theoretically infinite
        
        daily_expense = person.expenses / 30  # Convert monthly to daily
        if daily_expense <= 0:
            return 999
        
        return max(0, wealth / daily_expense)
    
    def _calc_healthcare_load(self):
        """Calculate healthcare system load rate"""
        total_pop = len([p for p in self.simulation.population 
                        if p.status.name != 'Death'])
        if total_pop == 0:
            return 0.0
        
        severe_count = self._statistics_cache.get('Severe', 0) * total_pop
        hospitalized_count = self._statistics_cache.get('Hospitalization', 0) * total_pop
        
        return (severe_count + hospitalized_count) / total_pop
    
    def _get_stratum_avg_wealth(self, social_stratum):
        """Get average wealth for specified social stratum"""
        return self.economic_stats.get('avg_wealth_by_stratum', {}).get(f'Q{social_stratum+1}', 0.0)
    
    def _get_nearby_businesses(self, person):
        """
        计算Person附近的Business信息（用于Shopping决策）
        
        Returns:
            dict: {
                "count": int,  # 附近Business数量
                "closest_distance": float,  # 最近的距离
                "closest_business": dict,  # 最近Business的信息
                "open_count": int  # 开放的Business数量
            }
        """
        if not hasattr(self.simulation, 'business') or len(self.simulation.business) == 0:
            return {
                "count": 0,
                "closest_distance": 999,
                "closest_business": None,
                "open_count": 0
            }
        
        # 计算与所有Business的距离
        distances = []
        for bus in self.simulation.business:
            if bus != person.employer:  # 排除自己的工作单位
                dist = np.sqrt((person.x - bus.x)**2 + (person.y - bus.y)**2)
                distances.append({
                    "business_id": bus.id,
                    "distance": round(dist, 1),
                    "open": bus.open,
                    "has_stock": bus.stocks > 0,
                    "price": bus.price,
                    "stratum": bus.social_stratum
                })
        
        if len(distances) == 0:
            return {
                "count": 0,
                "closest_distance": 999,
                "closest_business": None,
                "open_count": 0
            }
        
        # 按距离排序
        distances.sort(key=lambda x: x['distance'])
        
        # 统计开放的Business
        open_businesses = [d for d in distances if d['open'] and d['has_stock']]
        
        return {
            "count": len(distances),
            "closest_distance": distances[0]['distance'],
            "closest_business": distances[0],
            "open_count": len(open_businesses),
            "nearest_3": distances[:3]  # 最近的3个Business
        }
    
    def _get_shopping_history(self, person):
        """
        计算Person的购物历史（用于提醒LLM考虑购物）
        
        Returns:
            dict: {
                "last_shopping_iteration": int,  # 最近一次购物的iteration
                "hours_since_shopping": int,  # 距离上次购物多少小时
                "days_since_shopping": float,  # 距离上次购物多少天
                "never_shopped": bool,  # 从未购物过
                "shopping_urgency": str,  # 购物紧迫程度
                "resource_warning": str  # 资源警告信息
            }
        """
        # 🛒 使用Person.last_shopping_time属性（更高效准确）
        last_shopping_iter = getattr(person, 'last_shopping_time', -999)
        
        # 计算距离上次购物的时间
        hours_since = self.simulation.iteration - last_shopping_iter
        days_since = hours_since / 24
        
        # ✅ 优化：调整阈值降低购物频率，更符合现实世界（疫情期间2-4天购物一次）
        # 修改：3-5天MODERATE → 4-6天MODERATE，新增3-4天LOW缓冲
        if last_shopping_iter < 0:
            # 从未购物：第一次提示适度紧迫（避免过度强调）
            urgency = "MODERATE"
            resource_warning = "Household needs initial shopping - Set up supplies for daily life (this does NOT affect work obligations)."
            never_shopped = True
        elif hours_since >= 168:  # 7天+
            urgency = "CRITICAL"
            resource_warning = f"SUPPLIES: {days_since:.1f} days without shopping - Household supplies very low. Shopping needed soon."
            never_shopped = False
        elif hours_since >= 120:  # 5-7天
            urgency = "HIGH"
            resource_warning = f"SUPPLIES: {days_since:.1f} days without shopping - Household supplies decreasing. Consider shopping when convenient."
            never_shopped = False
        elif hours_since >= 96:  # 4-6天（优化：从72h调整到96h）
            urgency = "MODERATE"
            resource_warning = f"SUPPLIES: {days_since:.1f} days since last shopping - Supplies adequate but may need replenishment soon."
            never_shopped = False
        elif hours_since >= 72:  # 3-4天（新增：缓冲区）
            urgency = "LOW"
            resource_warning = f"SUPPLIES: {days_since:.1f} days since last shopping - Supplies still good, no rush."
            never_shopped = False
        elif hours_since >= 48:  # 2-3天
            urgency = "NONE"
            resource_warning = f"SUPPLIES: {days_since:.1f} days since last shopping - Recently stocked (work/other obligations still apply)."
            never_shopped = False
        elif hours_since >= 24:  # 1-2天
            urgency = "NONE"
            resource_warning = f"SUPPLIES: {days_since:.1f} days since last shopping - Household well-stocked, no shopping needed."
            never_shopped = False
        elif hours_since >= 6:  # 6-24小时
            urgency = "NONE"
            resource_warning = f"SUPPLIES: Just shopped {hours_since}h ago - Supplies fresh, shopping unnecessary (work obligations unaffected)."
            never_shopped = False
        else:  # <6小时
            urgency = "NONE"
            resource_warning = f"SUPPLIES: JUST shopped {hours_since}h ago - Shopping again this soon would be wasteful (supplies status does NOT affect work)."
            never_shopped = False
        
        # 🛒 检查最近的购物失败记录
        last_failed_iter = getattr(person, 'last_failed_shopping', -999)
        failure_reason = getattr(person, 'shopping_failure_reason', None)
        hours_since_failure = self.simulation.iteration - last_failed_iter
        
        # 生成失败提示（与冷却期时间窗口一致：24小时）
        failure_warning = ""
        if last_failed_iter >= 0 and hours_since_failure < 24:
            # 最近24小时内有购物失败
            if failure_reason == "no_inventory":
                failure_warning = f"NOTICE: Shopping failed {hours_since_failure}h ago - stores out of stock."
            elif failure_reason == "no_money":
                failure_warning = f"NOTICE: Shopping failed {hours_since_failure}h ago - insufficient funds."
            elif failure_reason == "closed_hours":  # ✅ 新增：营业时间外
                failure_warning = f"NOTICE: Shopping failed {hours_since_failure}h ago - stores not operating at that hour."
        
        return {
            "last_shopping_iteration": last_shopping_iter,
            "hours_since_shopping": hours_since,
            "days_since_shopping": round(days_since, 1),
            "never_shopped": never_shopped,
            "shopping_urgency": urgency,
            "resource_warning": resource_warning,
            "last_shopping_failed": last_failed_iter >= 0 and hours_since_failure < 24,
            "failure_warning": failure_warning
        }
    
    def get_person_context(self, person):
        """
        Get LLM decision context for a Person agent.
        
        Args:
            person: Person instance
            
        Returns:
            dict: Context including personal info, household, employment, epidemic, economy, policy, time, etc.
        """
        house = person.house
        employer = person.employer
        
        # 🔧 [FIX] 防御性检查：确保Person有必需的属性
        # 在某些极端情况下（如Hospitalized、刚创建等），这些属性可能缺失
        if not hasattr(person, 'x'):
            person.x = 0.0
        if not hasattr(person, 'y'):
            person.y = 0.0
        if not hasattr(person, 'infected_status') or person.infected_status is None:
            from covid_abs.agents import InfectionSeverity
            person.infected_status = InfectionSeverity.Asymptomatic
        
        # Calculate days sustainable
        days_sustainable = self._calc_days_sustainable(person)
        
        # 🔧 信息不对称原则：无症状感染者不知道自己被感染
        # 只有有症状时，感染状态才可见（症状是现实中可观察的）
        # 🔧 [FIX] 安全访问infected_status，防止AttributeError
        try:
            has_symptom = person.infected_status.name != 'Asymptomatic'
        except (AttributeError, TypeError):
            has_symptom = False
        
        # 🔧 计算与附近Business的距离和购物机会
        # 🔧 [FIX] 捕获可能的异常（如坐标缺失）
        try:
            nearby_businesses_info = self._get_nearby_businesses(person)
        except Exception as e:
            # 降级到安全的默认值
            nearby_businesses_info = {
                "count": 0,
                "closest_distance": 999,
                "closest_business": None,
                "open_count": 0
            }
        
        # 🔧 计算购物历史（多久没购物了）
        shopping_history = self._get_shopping_history(person)
        
        # 🔧 [信息不对称] 仅在有症状时提供感染状态（症状是现实可观察的）
        personal_info = {
                "id": person.id,
                "age": person.age,
                "status": person.status.name,
                "social_stratum": person.social_stratum,
                "social_stratum_name": f"Q{person.social_stratum + 1}",
                "economical_status": person.economical_status.name,
            "has_symptom": has_symptom,  # ✅ 症状是可见的（现实中可感知）
            "infected_time": person.infected_time if has_symptom else 0
        }
        
        # ✅ 只有有症状时才提供infected_status（用于症状描述）
        if has_symptom:
            personal_info["infected_status"] = person.infected_status.name
        
        # ✨ 改进：增强就业信息和经济压力信息
        is_employed = employer is not None
        is_working_age = 16 < person.age <= 65
        
        employment_info = {
            "employed": is_employed,
            # ✨ 新增：明确的失业标记
            "unemployed": not is_employed and is_working_age,
            # ✨ 新增：就业状态描述
            "employment_status": self._get_employment_status(person),
            # ✨ 新增：失业时长（如果失业）
            "days_unemployed": self._calc_unemployment_duration(person),
            # ✨ 新增：远程办公可用性（基于场景配置）
            "can_work_from_home": is_employed and self.scenario_config.get('enable_remote_work', False),
            # ✨ 新增：求职建议
            "should_seek_job": not is_employed and is_working_age,
            # 原有字段
            "employer_id": employer.id if employer else None,
            "employer_name": f"Business_{employer.id}" if employer else None,
            "employer_stratum": employer.social_stratum if employer else None,
            "employer_open": employer.open if employer else False,
            "monthly_income": person.incomes,
            # ✨ 新增：预期收入（如果找到工作）
            "expected_income": self._calc_expected_income(person),
            "absence_count": getattr(person, 'absence_count', 0)
        }
        
        # ✨ 新增：经济压力信息
        economic_pressure = {
            "financial_pressure": self._calc_financial_pressure(person),
            "income_needed": person.expenses > 0 and person.incomes == 0,
            "days_until_broke": round(days_sustainable, 1),
            "unemployment_benefit": person.expenses if (not is_employed and is_working_age) else 0,
            "job_market_condition": self._get_job_market_condition()
        }
        
        context = {
            "personal": personal_info,
            "employment": employment_info,
            "economic_pressure": economic_pressure,
            "household": {
                "has_house": house is not None,
                "house_id": house.id if house else None,
                "house_size": len(house.homemates) if house else 0,
                "house_wealth": house.wealth if house else person.wealth,
                "days_sustainable": round(days_sustainable, 1),
                "monthly_expenses": person.expenses
            },
            "epidemic": {
                "infected_rate": self._statistics_cache.get('Infected', 0),
                "death_rate": self._statistics_cache.get('Death', 0),
                "recovered_rate": self._statistics_cache.get('Recovered_Immune', 0),
                "healthcare_load": self._calc_healthcare_load(),
                "total_infected": int(self._statistics_cache.get('Infected', 0) * len(self.simulation.population)),
                "total_deaths": int(self._statistics_cache.get('Death', 0) * len(self.simulation.population))
            },
            "economic": {
                "unemployment_rate": self.economic_stats.get('unemployment_rate', 0),
                "homeless_rate": self.economic_stats.get('homeless_rate', 0),
                "business_open_rate": self.economic_stats.get('business_open_rate', 1.0),
                "stratum_avg_wealth": self._get_stratum_avg_wealth(person.social_stratum),
                "government_wealth": self.economic_stats.get('government_wealth', 0)
            },
            # 🔧 新增：附近Business信息（用于Shopping决策）
            "nearby_businesses": nearby_businesses_info,
            # 🔧 新增：购物历史（用于提醒LLM考虑购物）
            "shopping_history": shopping_history,
            "policy": {
                **self.government_policy,
                "lockdown_required": getattr(person, 'lockdown_required', False),
                "mandatory_lockdown_message": (
                    "⚠️ URGENT GOVERNMENT ORDER: MANDATORY LOCKDOWN IN EFFECT ⚠️\n"
                    "You are LEGALLY REQUIRED to STAY HOME immediately. Strict penalties apply for violations.\n"
                    "EXCEPTION: You may ONLY leave home if you have absolutely NO food/supplies left (Critical Survival).\n"
                    "For all other situations, OBEDIENCE TO GOVERNMENT ORDERS IS YOUR TOP PRIORITY.\n"
                    "Ignoring this order risks your health and legal standing."
                ) if self.government_policy.get('mandatory_lockdown') else None
            },
            "time": self.time_context
            # Note: iteration removed - already in time_context['iteration']
        }
        
        return context
    
    def get_business_context(self, business):
        """
        Get LLM decision context for a Business agent (for monthly decisions).
        
        Args:
            business: Business instance
            
        Returns:
            dict: Business operations data, performance metrics, market conditions
        """
        # Count infected employees
        infected_employees = sum(
            1 for emp in business.employees 
            if emp.status.name == 'Infected'
        )
        
        # Calculate profit
        profit = business.incomes - business.expenses
        profit_rate = profit / max(business.incomes, 1)
        
        # Calculate output per employee
        output_per_employee = business.sales / max(business.num_employees, 1)
        
        context = {
            "business_info": {
                "id": business.id,
                "type": business.type.name,
                "social_stratum": business.social_stratum,
                "num_employees": business.num_employees,
                "wealth": business.wealth,
                "incomes": business.incomes,
                "expenses": business.expenses,
                "stocks": business.stocks,
                "sales": business.sales,
                "price": business.price,
                "open": business.open
            },
            "performance": {
                "profit": profit,
                "profit_rate": profit_rate,
                "output_per_employee": output_per_employee,
                "infected_employees": infected_employees
            },
            "market": {
                "competitor_count": len([
                    b for b in self.simulation.business 
                    if b.social_stratum == business.social_stratum
                ]),
                "customer_pool_size": len([
                    p for p in self.simulation.population 
                    if p.social_stratum == business.social_stratum 
                    and p.status.name != 'Death'
                ])
            },
            "epidemic": {
                "infected_rate": self._statistics_cache.get('Infected', 0),
                "healthcare_load": self._calc_healthcare_load()
            },
            "economic": self.economic_stats,
            "policy": self.government_policy,  # ✅ 添加政府政策信息
            "time": self.time_context
        }
        
        return context
    
    def get_government_context(self):
        """
        Get LLM decision context for Government agent (for weekly decisions).
        
        Returns:
            dict: Epidemic trends, economic status, current policies
        """
        # Calculate epidemic trends (simplified, would need historical data)
        total_infected = int(self._statistics_cache.get('Infected', 0) * len(self.simulation.population))
        total_deaths = int(self._statistics_cache.get('Death', 0) * len(self.simulation.population))
        
        # Count closed businesses
        closed_business = len([b for b in self.simulation.business if not b.open])
        
        context = {
            "epidemic_trend": {
                "total_infected": total_infected,
                "total_deaths": total_deaths,
                "infection_rate": self._statistics_cache.get('Infected', 0),
                "death_rate": self._statistics_cache.get('Death', 0),
                "healthcare_load": self._calc_healthcare_load(),
                "trend": "unknown"  # Would require historical data
            },
            "economic_state": {
                "unemployment_rate": self.economic_stats.get('unemployment_rate', 0),
                "government_wealth": self.simulation.government.wealth,
                "closed_business": closed_business,
                "Q1_wealth": self._statistics_cache.get('Q1', 0),
                "fiscal_sustainability": self.simulation.government.wealth / self.simulation.total_wealth
            },
            "current_policy": self.government_policy,
            "time": self.time_context,
            # 添加紧急封锁状态标记
            "emergency_lockdown_active": self.government_policy.get('mandatory_lockdown', False)
        }
        
        # 🎬 添加动态政策建议（如果启用）
        if self.scenario_config.get('enable_policy_recommendation', False):
            # 如果紧急封锁已激活，修改建议内容
            if context["emergency_lockdown_active"]:
                context["policy_recommendation"] = "[EMERGENCY LOCKDOWN ACTIVE] System has automatically activated emergency lockdown due to infection rate >15%. Focus on maintaining order and preparing for eventual reopening when rate drops below 5%."
            else:
                context["policy_recommendation"] = self._generate_policy_recommendation(context)
        
        return context
    
    def _generate_policy_recommendation(self, context):
        """
        🎬 生成动态政策建议（模块化设计，可单独禁用）
        
        根据当前疫情状况和经济状态，生成针对性的政策建议。
        建议的强度和侧重点由scenario_config控制。
        
        Args:
            context: Government context dictionary containing epidemic and economic data
            
        Returns:
            str: Formatted policy recommendation text for LLM prompt
        """
        infection_rate = context["epidemic_trend"]["infection_rate"]
        unemployment_rate = context["economic_state"]["unemployment_rate"]
        closed_business = context["economic_state"]["closed_business"]
        healthcare_load = context["epidemic_trend"]["healthcare_load"]
        current_policy = context["current_policy"]
        
        # 获取配置参数
        mode = self.scenario_config.get('policy_recommendation_mode', 'balanced')
        critical_threshold = self.scenario_config.get('critical_threshold', 0.10)
        high_threshold = self.scenario_config.get('high_threshold', 0.05)
        moderate_threshold = self.scenario_config.get('moderate_threshold', 0.02)
        economic_weight = self.scenario_config.get('economic_weight', 0.5)
        
        # 计算严重程度
        severity_level = self._assess_epidemic_severity(
            infection_rate, healthcare_load, critical_threshold, high_threshold, moderate_threshold
        )
        
        # 根据mode和severity生成建议
        if mode == 'aggressive':
            return self._generate_aggressive_recommendation(
                severity_level, infection_rate, unemployment_rate, closed_business, current_policy
            )
        elif mode == 'conservative':
            return self._generate_conservative_recommendation(
                severity_level, infection_rate, unemployment_rate, closed_business, current_policy, economic_weight
            )
        else:  # balanced
            return self._generate_balanced_recommendation(
                severity_level, infection_rate, unemployment_rate, closed_business, current_policy, economic_weight
            )
    
    def _assess_epidemic_severity(self, infection_rate, healthcare_load, critical_threshold, high_threshold, moderate_threshold):
        """评估疫情严重程度"""
        if infection_rate > critical_threshold or healthcare_load > 0.9:
            return "critical"
        elif infection_rate > high_threshold or healthcare_load > 0.7:
            return "high"
        elif infection_rate > moderate_threshold:
            return "moderate"
        else:
            return "low"
    
    def _generate_aggressive_recommendation(self, severity, infection_rate, unemployment, closed_business, policy):
        """生成激进模式的建议（优先控制疫情）"""
        if severity == "critical":
            return f"""
CRITICAL EPIDEMIC SITUATION

Infection Rate: {infection_rate*100:.1f}% - DANGEROUSLY HIGH!

IMMEDIATE ACTION REQUIRED:
1. Issue MANDATORY Stay-at-Home Order NOW if not already active
2. Increase Medical Budget to maximum capacity
3. Close Borders to prevent external spread
4. Provide Economic Stimulus to support affected businesses and unemployed

RATIONALE: At this infection level, healthcare system collapse is imminent.
Economic costs are secondary to saving lives and preventing system failure.

Current lockdown status: {'ACTIVE' if policy.get('stay_home_order') else 'NOT ACTIVE - ISSUE MANDATORY ORDER NOW!'}
"""
        elif severity == "high":
            if not policy.get('stay_home_order'):
                return f"""
HIGH INFECTION RATE ({infection_rate*100:.1f}%)

STRONG RECOMMENDATION: Issue MANDATORY Stay-at-Home Order

The infection rate is above 5%. Without intervention, it will continue to grow
exponentially and may overwhelm the healthcare system.

RECOMMENDED ACTIONS:
1. Issue MANDATORY Stay-at-Home Order to flatten the curve
2. Increase Medical Budget (prepare for more cases)
3. Provide Economic Stimulus (mitigate economic impact)

Trade-off: Short-term economic pain for long-term health security.
"""
            else:
                return f"""
HIGH INFECTION RATE ({infection_rate*100:.1f}%) - Lockdown Active

RECOMMENDATION: Maintain MANDATORY Stay-at-Home Order

The infection rate is still high. Lifting restrictions now would cause a resurgence.

CONTINUE: Stay-at-Home Order
SUPPORT: Provide Economic Stimulus to businesses and unemployed
MONITOR: Wait for infection rate to drop below 2% before reopening
"""
        elif severity == "moderate":
            return f"""
MODERATE INFECTION RATE ({infection_rate*100:.1f}%)

RECOMMENDATION: {"Maintain lockdown" if policy.get('stay_home_order') else "Close monitoring"}

The situation is manageable but requires vigilance.
{"Continue restrictions until rate drops below 2%." if policy.get('stay_home_order') else "Be prepared to implement restrictions if rate increases."}

SUGGESTED ACTIONS:
- Monitor infection trends closely
- Ensure medical capacity is adequate
- {"Prepare economic support for reopening" if policy.get('stay_home_order') else "Maintain current policies"}
"""
        else:  # low
            if policy.get('stay_home_order'):
                return f"""
LOW INFECTION RATE ({infection_rate*100:.1f}%)

STRONG RECOMMENDATION: Lift Stay-at-Home Order

The infection rate is well controlled (<2%). Safe to reopen the economy.

RECOMMENDED ACTIONS:
1. Lift Stay-at-Home Order - allow normal economic activity
2. Support businesses to recover (Public Procurement, reduce taxes)
3. Continue monitoring for any resurgence

Economic recovery is now the priority.
"""
            else:
                return f"""
LOW INFECTION RATE ({infection_rate*100:.1f}%)

RECOMMENDATION: Maintain Current Policy

Situation is well controlled. Focus on economic recovery and healthcare readiness.

SUGGESTED ACTIONS:
- Support business recovery (Public Procurement)
- Maintain healthcare system preparedness
- Monitor for any signs of resurgence
"""
    
    def _generate_balanced_recommendation(self, severity, infection_rate, unemployment, closed_business, policy, economic_weight):
        """生成平衡模式的建议（兼顾健康和经济）"""
        economic_impact = unemployment * 0.5 + (closed_business / max(len(self.simulation.business), 1)) * 0.5
        
        if severity == "critical":
            return f"""
CRITICAL SITUATION - Health Priority

Infection Rate: {infection_rate*100:.1f}%
Economic Impact: Unemployment {unemployment*100:.0f}%, {closed_business} businesses closed

BALANCED APPROACH:
1. {"Maintain" if policy.get('stay_home_order') else "Issue"} Stay-at-Home Order (health priority at this level)
2. Increase Medical Budget
3. Provide Economic Stimulus to support those affected
4. Public Procurement to maintain some business revenue

RATIONALE: At critical infection levels, controlling the epidemic is paramount.
However, we must support the economy through stimulus and procurement.
"""
        elif severity == "high":
            if economic_impact > 0.3:  # High economic impact
                return f"""
HIGH INFECTION + HIGH ECONOMIC IMPACT

Infection Rate: {infection_rate*100:.1f}%
Economic Impact: Unemployment {unemployment*100:.0f}%, {closed_business} businesses closed

DIFFICULT TRADE-OFF:
- Health risk: High (rate > 5%)
- Economic cost: High ({closed_business} businesses closed, {unemployment*100:.0f}% unemployed)

BALANCED RECOMMENDATIONS:
{"1. Consider selective/partial restrictions (vertical isolation)" if not policy.get('stay_home_order') else "1. Consider lifting restrictions gradually if trend is declining"}
2. PRIORITY: Provide Economic Stimulus (many are suffering)
3. Public Procurement to support businesses
4. Moderate Medical Budget increase

{"Note: Full lockdown has severe economic costs. Consider targeted measures." if not policy.get('stay_home_order') else "Note: Lockdown cannot continue indefinitely. Plan for gradual reopening."}
"""
            else:
                return f"""
HIGH INFECTION RATE ({infection_rate*100:.1f}%)

RECOMMENDATION: {"Maintain lockdown, prepare for reopening" if policy.get('stay_home_order') else "Issue Stay-at-Home Order"}

Economic impact is still manageable. Health should be the priority.

ACTIONS:
1. {"Continue Stay-at-Home Order until rate drops to 2-3%" if policy.get('stay_home_order') else "Issue Stay-at-Home Order to control spread"}
2. Increase Medical Budget
3. Provide moderate Economic Stimulus
"""
        elif severity == "moderate":
            return f"""
MODERATE INFECTION RATE ({infection_rate*100:.1f}%)

BALANCED APPROACH - Decision Point

This is a critical decision point. The infection rate is manageable but not negligible.

OPTIONS:
{"A. Maintain restrictions until rate drops to <2% (safer)" if policy.get('stay_home_order') else "A. Implement partial restrictions (e.g., vertical isolation)"}
{"B. Begin gradual reopening with monitoring (riskier, better for economy)" if policy.get('stay_home_order') else "B. Maintain current policy with close monitoring"}

RECOMMENDED:
- Monitor trends closely (check daily)
- Support businesses (Public Procurement)
- Maintain healthcare readiness
- {"Consider gradual reopening if unemployment > 20%" if policy.get('stay_home_order') else "Be ready to act if rate increases to >5%"}
"""
        else:  # low
            if policy.get('stay_home_order'):
                return f"""
LOW INFECTION RATE ({infection_rate*100:.1f}%) - Time to Reopen

STRONG RECOMMENDATION: Lift Stay-at-Home Order

Health situation is under control. Economic recovery is now the priority.

REOPENING PLAN:
1. Lift Stay-at-Home Order immediately
2. Public Procurement to jumpstart business activity
3. Economic Stimulus to support recovery
4. Close monitoring for resurgence (be ready to act if rate increases)

Continued lockdown at this level causes unnecessary economic damage.
"""
            else:
                return f"""
LOW INFECTION RATE ({infection_rate*100:.1f}%)

RECOMMENDATION: Focus on Economic Recovery

Health situation is stable. Prioritize economic health.

ACTIONS:
- Public Procurement to support businesses
- Economic Stimulus if unemployment is high ({unemployment*100:.0f}%)
- Maintain monitoring and healthcare readiness
"""
    
    def _generate_conservative_recommendation(self, severity, infection_rate, unemployment, closed_business, policy, economic_weight):
        """生成保守模式的建议（优先保护经济）"""
        if severity == "critical":
            return f"""
CRITICAL EPIDEMIC SITUATION

Infection Rate: {infection_rate*100:.1f}% - Very High

Even in conservative mode, this level requires action.

MINIMUM ACTIONS:
1. Increase Medical Budget (essential)
2. Provide Economic Stimulus (protect economy)
{"3. Consider Stay-at-Home Order only if healthcare system is overwhelmed" if not policy.get('stay_home_order') else "3. Plan for lifting restrictions as soon as rate drops to 5%"}

ECONOMIC PRIORITY: Avoid lockdown if possible, but don't let healthcare collapse.
"""
        elif severity == "high":
            return f"""
HIGH INFECTION RATE ({infection_rate*100:.1f}%)

CONSERVATIVE APPROACH:
The infection rate is elevated but manageable.

RECOMMENDATIONS:
{"- Maintain lockdown ONLY if absolutely necessary" if policy.get('stay_home_order') else "- Avoid lockdown - use targeted measures instead"}
{"- Consider lifting restrictions and using vertical isolation" if policy.get('stay_home_order') else "- Implement vertical isolation (protect elderly, keep workers active)"}
- Moderate Medical Budget increase
- Economic Stimulus (PRIORITY - protect jobs and businesses)
- Public Procurement to maintain business revenue

RATIONALE: Economic damage from lockdowns can be severe and long-lasting.
Targeted measures protect the vulnerable while keeping the economy running.
"""
        elif severity == "moderate":
            return f"""
MODERATE INFECTION RATE ({infection_rate*100:.1f}%)

CONSERVATIVE RECOMMENDATION: {"Lift restrictions" if policy.get('stay_home_order') else "Maintain current policy"}

At this level, economic considerations should take priority.

ACTIONS:
{"- Lift Stay-at-Home Order (rate is manageable)" if policy.get('stay_home_order') else "- Continue normal economic activity"}
- Public Procurement to support businesses
- Economic Stimulus if needed
- Monitor infection rate (be ready to act only if it exceeds 10%)

RATIONALE: 2-5% infection rate is manageable with healthcare capacity.
Economic health is equally important for long-term societal wellbeing.
"""
        else:  # low
            return f"""
LOW INFECTION RATE ({infection_rate*100:.1f}%)

RECOMMENDATION: Full Economic Recovery Mode

{"IMMEDIATE: Lift all restrictions" if policy.get('stay_home_order') else "EXCELLENT: Continue current policy"}

PRIORITY ACTIONS:
1. Public Procurement (maximum support for businesses)
2. Economic Stimulus (stimulate growth)
{"3. Lift Stay-at-Home Order immediately if still active" if policy.get('stay_home_order') else "3. Encourage business expansion and hiring"}
4. Minimal health monitoring

FOCUS: Economic growth and recovery.
"""
    
    def _get_employment_status(self, person):
        """获取清晰的就业状态描述"""
        if person.employer is not None:
            return "employed"
        elif 16 < person.age <= 65:
            return "unemployed_seeking"  # 明确表示需要找工作
        elif person.age <= 16:
            return "student"
        else:
            return "retired"
    
    def _calc_unemployment_duration(self, person):
        """计算失业天数"""
        if person.employer is not None:
            return 0
        # 从last_work_iteration计算
        if hasattr(person, 'last_work_iteration'):
            days_unemployed = (self.simulation.iteration - person.last_work_iteration) // 24
            return max(0, days_unemployed)
        return 0  # 初始失业
    
    def _calc_expected_income(self, person):
        """计算预期收入（基于阶层）"""
        # 基于社会阶层的典型收入
        stratum_incomes = [1000, 2000, 4000, 8000, 16000]  # Q1-Q5
        return stratum_incomes[min(person.social_stratum, 4)]
    
    def _calc_financial_pressure(self, person):
        """计算财务压力等级"""
        days_sustainable = self._calc_days_sustainable(person)
        if days_sustainable < 7:
            return "critical"  # 危急
        elif days_sustainable < 30:
            return "high"      # 高
        elif days_sustainable < 90:
            return "moderate"  # 中等
        else:
            return "low"       # 低
    
    def _get_job_market_condition(self):
        """获取就业市场状况"""
        unemployment_rate = self.economic_stats.get('unemployment_rate', 0)
        if unemployment_rate > 0.2:
            return "poor"      # 就业市场差
        elif unemployment_rate > 0.1:
            return "moderate"  # 一般
        else:
            return "good"      # 就业市场好
    
    def get_available_actions_for_agent(self, agent) -> list:
        """
        根据agent状态过滤可用Action（核心功能）
        
        ✅ 优化逻辑：
        - 死亡agent：无Action可用
        - 有症状感染者（Hospitalization/Severe）：只能StayHome或SeekMedical
        - 破产agent：只能接受政府救济
        - 无症状/健康：所有Action可用
        
        Args:
            agent: Agent instance
            
        Returns:
            list: 可用的Action名称列表
        """
        from covid_abs.llm.actions import get_action_registry
        
        # 死亡agent无Action可用
        if agent.status == Status.Death:
            return []
        
        # Person agent的Action过滤
        if agent.type == AgentType.Person:
            # ✅ 有症状感染者：只能居家或就医
            if agent.infected_status != InfectionSeverity.Asymptomatic:
                return ['StayHomeAction', 'SeekMedicalAction']
            
            # ✅ 破产agent：需要政府救济（无法正常消费）
            house = agent.house
            if house and house.wealth <= 0:
                # 破产但仍可以尝试找工作或居家
                return ['StayHomeAction', 'SeekJobAction']
            
            # 无症状/健康：基础Action
            person_actions = [
                'StayHomeAction',      # 始终可用
                'SeekMedicalAction',   # 始终可用（预防性就医）
                'ShoppingAction',      # 始终可用
                'MoveFreelyAction'     # 始终可用
            ]
            
            # ✅ 购物冷却机制改为Prompt引导
            # 不再硬性移除ShoppingAction，而是通过_get_shopping_history()提供的警告信息
            # 让LLM根据"刚购物过"的提示自主判断是否应该再次购物
            # 这种方式更符合LLM的决策能力，也更接近真实人类的判断过程
            
            # 🔒 [健壮性强化] GoToWorkAction: 仅在有雇主时可用
            # 避免Action执行失败（没有employer就无法GoToWork）
            if agent.employer is not None:
                person_actions.append('GoToWorkAction')
                
                # 🎬 Scenario Control: Remote Work
                # Only enable WorkFromHomeAction if allowed by scenario config
                if self.scenario_config.get('enable_remote_work', False):
                    person_actions.append('WorkFromHomeAction')  # 有工作才能远程工作
            
            # 🔒 [健壮性强化] SeekJobAction: 仅在失业时可用
            # 避免WARNING: "Attempted to hire agent who is already employed"
            if agent.employer is None:
                person_actions.append('SeekJobAction')
            
            return person_actions
        
        # Business和Government的Action不受感染状态影响
        elif agent.type == AgentType.Business:
            # ✅ 动态状态过滤：避免重复无效Action
            business_actions = ['AdjustPriceAction']  # 调价始终可用
            
            # 🔒 [健壮性强化] HireEmployeeAction: 仅在员工未满时可用
            # 避免WARNING: "Attempted to hire agent who is already employed"
            # 假设最大员工数 = 初始员工数 * 2（合理扩张上限）
            max_employees = max(10, len(agent.employees) * 2) if hasattr(agent, 'employees') else 10
            if hasattr(agent, 'employees') and len(agent.employees) < max_employees:
                business_actions.append('HireEmployeeAction')
            
            # 🔒 [健壮性强化] FireEmployeeAction: 仅在有员工时可用
            # 避免WARNING: "Attempted to fire agent who is not employed"
            if hasattr(agent, 'employees') and len(agent.employees) > 0:
                business_actions.append('FireEmployeeAction')
            
            # 根据open状态动态添加运营相关Action
            if agent.open:
                # 营业中：可以维持或关闭
                business_actions.append('MaintainOperationAction')
                business_actions.append('CloseBusinessAction')
            else:
                # 已关闭：只能重新开业
                business_actions.append('ReopenBusinessAction')
            
            return business_actions
        
        elif agent.type == AgentType.Government:
            # 🎬 SCENARIO-BASED ACTION FILTERING
            scenario_name = self.scenario_config.get('name', 'unknown')
            policy = self.government_policy  # ✅ Fix: Define policy variable early
            
            if scenario_name == 'baseline':
                # [BASELINE SCENARIO]: Laissez-faire
                # Government CANNOT take active NPIs or economic interventions.
                # Allowed: ONLY MaintainPolicy (Absolutely NO intervention)
                government_actions = [
                    'MaintainPolicyAction'
                ]
                return government_actions
            
            elif scenario_name == 'health_priority':
                # [SCENARIO B]: Health Priority
                # 使用强制性居家令 (IssueMandatoryStayHomeOrderAction)
                government_actions = [
                    'AdjustTaxRateAction',
                    'ProvideStimulusAction',
                    'IncreaseMedicalBudgetAction',
                    'MaintainPolicyAction'
                ]
                
                # Stay-Home Order相关
                if policy.get('stay_home_order', False):
                    # 检查是否是紧急封锁状态
                    if policy.get('mandatory_lockdown', False):
                        # 紧急封锁状态：只有感染率<5%才能解除
                        infected_count = sum(1 for a in self.simulation.population if a.status == Status.Infected)
                        infection_rate = infected_count / max(self.simulation.population_size, 1)
                        if infection_rate < 0.05:
                            government_actions.append('LiftStayHomeOrderAction')
                        # 否则只能维持政策，不能解除
                    else:
                        # 普通封锁：可以解除
                        government_actions.append('LiftStayHomeOrderAction')
                else:
                    # 未发布禁足令：发布强制性禁足令
                    government_actions.append('IssueMandatoryStayHomeOrderAction')
                
                # Borders相关
                if not policy.get('borders_closed', False):
                    government_actions.append('CloseBordersAction')
                    
                return government_actions
            
            elif scenario_name == 'remote_work':
                # [SCENARIO C]: Remote Work
                # Government intervention DISABLED (Same as Baseline)
                # Focus is on autonomous agent behavior (WFH)
                government_actions = [
                    'AdjustTaxRateAction',
                    'MaintainPolicyAction'
                ]
                return government_actions

            # ✅ 基础Government Action（始终可用） - 其他场景 (D, E...)
            government_actions = [
                'AdjustTaxRateAction',
                'ProvideStimulusAction',
                'IncreaseMedicalBudgetAction',
                'MaintainPolicyAction'
            ]
            
            # ✅ 动态状态过滤：根据政策状态添加/移除Action
            
            # Stay-Home Order相关
            if policy.get('stay_home_order', False):
                # 已发布禁足令：只能解除
                government_actions.append('LiftStayHomeOrderAction')
            else:
                # 未发布禁足令：只能发布
                government_actions.append('IssueStayHomeOrderAction')
            
            # Borders相关（简化：始终可关闭）
            if not policy.get('borders_closed', False):
                government_actions.append('CloseBordersAction')
            # 注：LiftBordersAction未定义，所以边境关闭后无法重开（简化模型）
            
            # ═══════════════════════════════════════════════════════════
            # 扩展Action（已在Registry中注册，但暂时不启用）
            # 需要时取消下面的注释即可启用
            # ═══════════════════════════════════════════════════════════
            
            # 'PublicProcurementAction',              # 政府采购
            # 'IssueBusinessSubsidyAction',           # 企业补贴
            # 'ImplementContactTracingAction',        # 接触追踪
            # 'LaunchVaccinationCampaignAction',      # 疫苗接种
            # 'IssuePartialLockdownAction',           # 部分封锁
            # 'LiftPartialLockdownAction',            # 解除部分封锁
            # 'AdjustBusinessRegulationAction',       # 企业监管
            # 'LiftBusinessRegulationAction',         # 解除监管
            
            return government_actions
        
        # 默认：返回空列表
        return []
