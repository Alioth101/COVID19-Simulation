"""
GraphSimulation专用的Action类
保留原系统的经济逻辑(checkin/accounting等)
"""

import numpy as np
from covid_abs.llm.actions import Action
from covid_abs.agents import Status, InfectionSeverity
from covid_abs.common import basic_income
from covid_abs.network.util import work_time, bed_time


class GoToWorkAction(Action):
    """
    去上班Action - 保留原系统的checkin逻辑
    
    核心逻辑:
    - work_time: 移动到employer, 触发employer.checkin() (累积工资+生产)
    - bed_time: 回家
    - 其他时间: 自由移动
    
    重要: 必须保留checkin逻辑,这是工资累积的关键!
    """
    
    def get_description(self) -> str:
        return """Go to work - Normal work schedule, earn salary income (exposure risk)

[CRITICAL] Missing work for 3 consecutive days (72 hours) will result in termination and job loss.
[INCOME] Work provides monthly salary. Unemployed = no regular income.
[RISK] Exposure to coworkers and customers during epidemic."""
    
    def get_parameters(self):
        return []  # 无需额外参数
    
    def execute(self, agent, simulation, params=None):
        # 检查agent状态
        if agent.status == Status.Death:
            return {
                "success": False,
                "reason": "agent is dead",
                "location": "none"
            }
        
        # 检查是否有雇主
        if agent.employer is None:
            return {
                "success": False,
                "reason": "unemployed - no employer",
                "location": "none"
            }
        
        # 检查雇主是否实际营业（结合LLM决策和强制营业时间）
        current_hour = simulation.iteration % 24
        if not agent.employer.is_open_now(current_hour):
            # 公司关闭或不在营业时间,回家
            agent.move_to_home()
            return {
                "success": True,
                "reason": "employer closed or outside operating hours, stay home",
                "location": "home",
                "income_accumulated": False
            }
        
        # 根据时间段执行不同动作
        iter = simulation.iteration
        
        if work_time(iter):
            # 工作时间: 去公司上班
            agent.move_to_work()  # 这里会调用employer.checkin(agent)!
            location = "work"
            income_accumulated = True
            
            # ✅ 更新最后上班时间（用于缺勤判定）
            agent.last_work_iteration = simulation.iteration
            
        elif bed_time(iter):
            # 睡觉时间: 回家
            agent.move_to_home()
            location = "home"
            income_accumulated = False
            
        else:
            # 其他时间: 自由活动
            agent.move_freely()
            location = "free"
            income_accumulated = False
        
        # 重置缺勤计数 (正常上班) - 保留兼容性
        if hasattr(agent, 'absence_count'):
            agent.absence_count = 0
        
        return {
            "success": True,
            "location": location,
            "income_accumulated": income_accumulated,
            "employer_id": agent.employer.id
        }


class StayHomeAction(Action):
    """
    居家隔离Action - 全天在家
    
    注意: 会导致缺勤,连续3次可能被解雇
    """
    
    def get_description(self) -> str:
        return """Stay home - Avoid exposure risk, but has employment consequences

[SAFETY] Stay home to protect health and avoid virus exposure.
[WARNING] If employed: Missing work for 3 consecutive DAYS (72 hours) will result in TERMINATION.
- You will be fired and lose your job.
- After termination, no regular income until finding new employment.
[BALANCE] Consider if staying home is worth risking job loss."""
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        # 移动到家
        agent.move_to_home()
        
        # 检查是否有雇主
        if agent.employer is None:
            return {
                "success": True,
                "location": "home",
                "employment_impact": "unemployed"
            }
        
        # ✅ 修正：缺勤判定改为连续3天（72 iterations）未上班
        # 原逻辑：连续3次工作时间决策选StayHome即fire（约6小时）
        # 新逻辑：连续72个iteration未GoToWork才fire（3天）
        if work_time(simulation.iteration):
            # 初始化最后上班时间
            if not hasattr(agent, 'last_work_iteration'):
                agent.last_work_iteration = -999  # 初始化为很久以前
            
            # 检查是否连续3天未上班
            absence_duration = simulation.iteration - agent.last_work_iteration
            
            if absence_duration >= 72:  # 连续72个iteration (3天) 未上班
                employer = agent.employer
                employer.fire(agent)
                # ✅ 修复：fire后重置last_work_iteration，避免重复fire
                agent.last_work_iteration = simulation.iteration
                return {
                    "success": True,
                    "location": "home",
                    "employment_impact": "fired",
                    "reason": f"excessive absence ({absence_duration // 24} days)",
                    "fired_from": employer.id,
                    "absence_duration": absence_duration
                }
            
            return {
                "success": True,
                "location": "home",
                "employment_impact": "absence",
                "absence_duration": absence_duration,
                "warning": f"absent for {absence_duration} iterations ({absence_duration / 24:.1f} days)"
            }
        
        # 非工作时间在家
        return {
            "success": True,
            "location": "home",
            "employment_impact": "none"
        }


class WorkFromHomeAction(Action):
    """
    远程工作Action - 50%效率工作
    
    在家工作, 但仍然有部分产出和收入
    """
    
    def get_description(self) -> str:
        return "Work from home - Remote work, earn FULL salary income while staying safe at home (best of both worlds)"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        # 移动到家
        agent.move_to_home()
        
        # 检查是否有雇主
        if agent.employer is None:
            return {
                "success": False,
                "reason": "unemployed - cannot work from home",
                "location": "home"
            }
        
        # 检查雇主是否实际营业（结合LLM决策和强制营业时间）
        current_hour = simulation.iteration % 24
        if not agent.employer.is_open_now(current_hour):
            return {
                "success": True,
                "reason": "employer closed or outside operating hours",
                "location": "home",
                "work_efficiency": 0.0
            }
        
        # 工作时间: 远程工作 (50%效率)
        if work_time(simulation.iteration):
            # 模拟50%效率的工作
            agent.employer.stocks += 0.5  # 50%的生产
            
            # ✅ 修复：删除hourly工资扣款（BasicSimulation残留）
            # 原代码：agent.employer.cash(-agent.expenses / 720 * 0.5)
            # 问题：Business扣钱但Person没收钱 → 财富凭空消失
            # 解决：只累积stocks，工资由月底accounting()统一支付
            # 这和Business.checkin()的修复逻辑一致（见network/agents.py Line 236-239）
            
            # ✅ 关键修复：更新最后上班时间（防止被解雇）
            agent.last_work_iteration = simulation.iteration
            
            # 重置缺勤计数
            if hasattr(agent, 'absence_count'):
                agent.absence_count = 0
            
            return {
                "success": True,
                "location": "home",
                "work_efficiency": 0.5,
                "partial_income": True
            }
        
        # 非工作时间
        return {
            "success": True,
            "location": "home",
            "work_efficiency": 0.0
        }


class SeekMedicalAction(Action):
    """
    就医Action - 移动到healthcare, 支付医疗费用
    
    医疗费用 = 月支出的50%
    """
    
    def get_description(self) -> str:
        return "Seek medical care - Get treatment to reduce death risk, requires payment (50% of monthly expenses)"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        # 检查是否有医疗机构
        if not hasattr(simulation, 'healthcare'):
            return {
                "success": False,
                "reason": "no healthcare facility in simulation"
            }
        
        # 移动到医疗机构
        agent.move_to(simulation.healthcare)
        
        # 计算医疗费用 (月支出的50%)
        medical_cost = agent.expenses * 0.5
        
        # 支付医疗费用
        agent.demand(medical_cost)  # 从House扣除
        simulation.healthcare.cash(medical_cost)  # Healthcare收入
        
        # 治疗效果 (可选): 降低死亡风险
        if agent.infected_status == InfectionSeverity.Hospitalization:
            # 给agent添加治疗加成
            agent.treatment_bonus = 0.2  # 降低20%死亡概率
        
        return {
            "success": True,
            "location": "healthcare",
            "medical_cost": medical_cost,
            "treatment_received": agent.infected_status.name
        }


class SeekJobAction(Action):
    """
    找工作Action - 应聘开放的企业
    
    可以指定目标企业, 或随机应聘
    """
    
    def get_description(self) -> str:
        return "Seek job - Apply to open businesses to find new employment"
    
    def get_parameters(self):
        return ["target_business_id"]  # 可选参数
    
    def execute(self, agent, simulation, params=None):
        # 检查是否已有雇主
        if agent.employer is not None:
            return {
                "success": False,
                "reason": "already employed",
                "current_employer": agent.employer.id
            }
        
        # 检查是否有可用企业
        if not hasattr(simulation, 'business') or len(simulation.business) == 0:
            return {
                "success": False,
                "reason": "no business in simulation"
            }
        
        # 尝试指定的目标企业
        target_business_id = params.get("target_business_id")
        
        if target_business_id is not None:
            # 查找目标企业
            business = next((b for b in simulation.business 
                           if b.id == target_business_id), None)
            
            if business and business.open:
                business.hire(agent)
                return {
                    "success": True,
                    "employer_id": business.id,
                    "employer_stratum": business.social_stratum,
                    "salary": agent.incomes,
                    "hire_method": "targeted"
                }
        
        # 随机应聘开放的企业
        open_businesses = [b for b in simulation.business if b.open]
        
        if len(open_businesses) == 0:
            return {
                "success": False,
                "reason": "no open business available"
            }
        
        # 随机选择一个企业
        business = open_businesses[np.random.randint(0, len(open_businesses))]
        business.hire(agent)
        
        return {
            "success": True,
            "employer_id": business.id,
            "employer_stratum": business.social_stratum,
            "salary": agent.incomes,
            "hire_method": "random"
        }


class ShoppingAction(Action):
    """
    购物Action - 完整的消费行为（LLM主动决策）
    
    流程：
    1. 检查Person财富和健康状况
    2. 选择可用的Business
    3. 移动到Business附近
    4. 立即执行交易（Business.supply()）
    
    ✅ 完全由LLM驱动，Person有自主决策权
    """
    
    def get_description(self) -> str:
        return """Go shopping - Purchase household necessities

[PURPOSE] Maintain household supplies and support local economy
- Food, daily necessities, and household items need periodic replenishment
- Outdoor activity with some infection risk depending on epidemic situation

[CONSIDERATIONS]
- Health risk: Exposure to other people in stores
- Economic impact: Supports local businesses through consumer spending
- Timing: More effective when businesses are open and stocked
- Household needs: Important when supplies are running low
- Financial situation: Requires sufficient funds

[WHEN TO CONSIDER]
- Household supplies are running low
- You are healthy (no symptoms)
- Businesses are open during permitted hours
- You have adequate funds available"""
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        from covid_abs.network.agents import Person
        
        # 安全检查：必须是Person
        if not isinstance(agent, Person):
            return {
                "success": False,
                "reason": "shopping only available for Person agents"
            }
        
        # 检查健康状况：只有无症状才能购物
        if agent.infected_status != InfectionSeverity.Asymptomatic:
            agent.move_to_home()
            return {
                "success": False,
                "reason": "has symptoms, cannot go shopping",
                "location": "home"
            }
        
        # 检查是否有Business
        if not hasattr(simulation, 'business') or len(simulation.business) == 0:
            agent.move_freely()
            return {
                "success": False,
                "reason": "no business available",
                "location": "free"
            }
        
        # ✅ 选择实际营业且有库存的Business（结合LLM决策和强制营业时间8-22）
        current_hour = simulation.iteration % 24
        open_businesses = [
            b for b in simulation.business 
            if b.is_open_now(current_hour) and b.stocks > 0 and b != agent.employer
        ]
        
        if len(open_businesses) == 0:
            # 🛒 记录购物失败（用于后续决策调整）
            agent.last_failed_shopping = simulation.iteration
            
            # 区分失败原因：营业时间外 vs 无库存 vs Business关闭
            all_businesses = [b for b in simulation.business if b != agent.employer]
            if all_businesses and not any(b.is_operating_hours(current_hour) for b in all_businesses):
                # 所有商店都在营业时间外（22:00-08:00）
                agent.shopping_failure_reason = "closed_hours"
            elif all_businesses and not any(b.open for b in all_businesses):
                # 所有商店都被LLM决策关闭
                agent.shopping_failure_reason = "business_closed"
            else:
                # 商店开着但没库存
                agent.shopping_failure_reason = "no_inventory"
            
            agent.move_freely()
            return {
                "success": False,
                "reason": "no open business with inventory",
                "location": "free"
            }
        
        # 随机选择一个Business
        business = open_businesses[np.random.randint(0, len(open_businesses))]
        
        # 检查财富：确保有足够的钱购物
        purchase_price = business.price
        agent_wealth = agent.house.wealth if agent.house else agent.wealth
        
        if agent_wealth < purchase_price:
            # 🛒 记录购物失败（财富不足）
            agent.last_failed_shopping = simulation.iteration
            agent.shopping_failure_reason = "no_money"
            
            # 财富不足，不购物
            return {
                "success": False,
                "reason": "insufficient funds",
                "required": purchase_price,
                "available": agent_wealth
            }
        
        # 移动到Business附近
        x, y = np.random.normal(0.0, 0.25, 2)
        agent.x = int(business.x + x)
        agent.y = int(business.y + y)
        
        # ✅ 立即执行交易（完整的购物行为）
        # business.supply(agent)完整处理：
        #   - agent.demand() → House.demand() → House.wealth减少
        #   - Business.cash() → Business.wealth增加
        #   - Business.stocks减少，sales增加
        #   - 财富守恒 ✅
        business.supply(agent)
        
        # 🛒 更新购物时间（用于追踪购物频率）
        agent.last_shopping_time = simulation.iteration
        
        return {
            "success": True,
            "action": "shopping",
            "location": "shopping",
            "business_id": business.id,
            "business_stratum": business.social_stratum,
            "price_paid": purchase_price,
            "wealth_after": agent.house.wealth if agent.house else agent.wealth,
            "message": f"Purchased goods from Q{business.social_stratum+1} business at ${purchase_price:.2f}"
        }


class MoveFreelyAction(Action):
    """
    自由移动Action - 随机移动
    
    保留原系统的move_freely逻辑
    """
    
    def get_description(self) -> str:
        return "Move freely - Random movement for leisure and recreation, slight exposure risk"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        # 保存旧位置
        old_x, old_y = agent.x, agent.y
        
        # 执行自由移动
        agent.move_freely()
        
        # 计算移动距离
        dist = np.sqrt((agent.x - old_x) ** 2 + (agent.y - old_y) ** 2)
        
        # ✅ 修复：删除移动产生收入的逻辑
        # 原逻辑：移动会产生收入，但没有对应的支出方 → 财富凭空创造（bug）
        # 修复后：MoveFreelyAction只负责移动，不产生收入
        # 如果需要模拟经济活动，应该使用ShoppingAction
        
        # ❌ 已删除的财富创造逻辑：
        # income = 0.0
        # if dist > 0:
        #     result_ecom = np.random.rand()
        #     income = dist * result_ecom * simulation.minimum_expense * basic_income[agent.social_stratum]
        #     agent.supply(income)  # ⚠️ 凭空创造财富
        
        return {
            "success": True,
            "location": "free",
            "distance_moved": dist,
            "income_generated": 0.0  # 不再产生收入
        }


# ==================== Business专用Actions ====================

class HireEmployeeAction(Action):
    """
    雇佣员工 - Business扩张
    适用场景: 利润充足,需要扩大规模
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Hire employee - Expand business scale and increase production capacity"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        雇佣一个失业者
        
        逻辑:
        1. 获取失业人员列表
        2. 随机选择一个雇佣
        3. 增加fixed_expenses
        """
        unemployed = simulation.get_unemployed()
        if unemployed:
            ix = np.random.randint(0, len(unemployed))
            agent.hire(unemployed[ix])
            return {
                "success": True,
                "hired": unemployed[ix].id,
                "new_employee_count": len(agent.employees)
            }
        return {
            "success": False,
            "reason": "No unemployed workers available"
        }


class FireEmployeeAction(Action):
    """
    解雇员工 - Business收缩
    适用场景: 利润不足,需要减少成本
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Fire employee - Reduce labor costs to address declining profits"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        解雇一个员工
        
        逻辑:
        1. 从employees中随机选择
        2. 调用fire()方法
        3. 支付最后工资
        """
        if agent.employees:
            ix = np.random.randint(0, len(agent.employees))
            fired_employee = agent.employees[ix]
            agent.fire(fired_employee)
            return {
                "success": True,
                "fired": fired_employee.id,
                "remaining_employees": len(agent.employees)
            }
        return {
            "success": False,
            "reason": "No employees to fire"
        }


class AdjustPriceAction(Action):
    """
    调整价格 - 价格策略
    适用场景: 销售不佳时降价,销售火爆时提价
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Adjust product/service price - Balance sales volume and profit margin"
    
    def get_parameters(self):
        return ["direction"]  # "increase" or "decrease"
    
    def execute(self, agent, simulation, params=None):
        """
        调整价格
        
        Args:
            params: {"direction": "increase" or "decrease"}
        
        逻辑:
        - increase: 价格+10%
        - decrease: 价格-10%
        - 价格最低不低于基准价的50%
        """
        if params is None:
            params = {}
        
        old_price = agent.price
        direction = params.get("direction", "maintain")
        base_price = (agent.social_stratum + 1) * 12.0
        
        if direction == "increase":
            agent.price = min(agent.price * 1.1, base_price * 2.0)
        elif direction == "decrease":
            agent.price = max(agent.price * 0.9, base_price * 0.5)
        # else: maintain current price
        
        return {
            "success": True,
            "old_price": old_price,
            "new_price": agent.price,
            "direction": direction
        }


class MaintainOperationAction(Action):
    """
    维持运营 - 保持现状
    适用场景: 当前状态良好,无需改变
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Maintain current operations - Continue business as usual

[OPERATIONAL CONTINUITY] Keeping business open maintains revenue potential and market presence
- Customers can still shop even with partial workforce
- Business remains competitive and visible in market
- Fixed costs exist whether open or closed - better to have revenue opportunity

[WORKFORCE MANAGEMENT] Partial staff availability doesn't require closure
- Healthy employees can continue working
- Infected employees naturally stay home (self-isolation)
- Reduced capacity is manageable and temporary
- Closure means ZERO revenue while costs continue

[FINANCIAL STABILITY] Open business has income potential, closed business has only expenses
- Even reduced sales > zero sales
- Customer relationships maintained
- Avoid close-reopen cycle costs

[WHEN TO CHOOSE]
- Less than 80% of workforce infected
- Business has positive or neutral cash flow
- Customer demand exists (even if reduced)
- Default choice for stable operation"""
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        维持运营,不做任何变更
        """
        return {
            "success": True,
            "action": "maintain",
            "message": "Business continues normal operation"
        }


class CloseBusinessAction(Action):
    """
    关闭业务 - 暂停运营
    适用场景: 疫情严重,亏损严重,需要止损
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Close business - Temporarily suspend operations

[EFFECTS OF CLOSURE]
- No customer revenue during closure period
- Fixed expenses (rent, utilities, maintenance) continue
- May lose market position to competitors
- Can be reopened when conditions improve

[REASONS TO CONSIDER CLOSURE]
- Most workforce unable to work due to illness
- Severe financial losses with no near-term improvement
- Limited customer demand during epidemic peak
- Government mandate or public health emergency
- Protecting employee and customer health

[ALTERNATIVES TO CLOSURE]
- MaintainOperation at reduced capacity
- AdjustPrice to manage demand and revenue
- Monitor situation before deciding

[TRADE-OFF]
Closure protects health and may reduce losses in crisis, but eliminates revenue stream"""
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        关闭业务
        
        逻辑:
        1. 设置open=False
        2. 不解雇员工(保留岗位)
        """
        agent.open = False
        return {
            "success": True,
            "action": "close",
            "employees_retained": len(agent.employees)
        }


class ReopenBusinessAction(Action):
    """
    重新开业 - 恢复运营
    适用场景: 疫情缓解,现金流改善,可以恢复运营
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Reopen business - Resume operations after closure

[REOPENING CONSIDERATIONS]
Reopening works best when conditions have improved:
- Workforce infection rate <50% (more staff available)
- Cash reserves sufficient for 7+ days operation
- Customer demand likely higher (population infection <70%)
- Healthcare system has capacity

[TIMING FACTORS]
- Reopening too early may lead to reclosure if conditions unchanged
- Waiting for genuine improvement typically more sustainable
- Consider workforce health, finances, and market demand together

[CHECKLIST]
- 50%+ workforce healthy and available
- Cash reserves adequate
- Market conditions support customers
- Epidemic severity lower than at closure

[ALTERNATIVE]
If conditions similar to closure time, maintaining closure may be prudent"""
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        重新开业
        
        逻辑:
        1. 设置open=True
        2. 恢复正常运营
        """
        agent.open = True
        return {
            "success": True,
            "action": "reopen",
            "employees_ready": len(agent.employees)
        }


# ==================== Government Actions ====================

class AdjustTaxRateAction(Action):
    """
    调整税率 - 增税或减税
    
    适用场景:
    - 财政紧张: 增税(increase)
    - 经济刺激: 减税(decrease)
    
    参数:
    - direction: "increase" 或 "decrease"
    - amount: 调整幅度(0.05 = 5%)
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Adjust tax rate - Increase taxes (boost revenue) or decrease taxes (stimulate economy)"
    
    def get_parameters(self):
        return [
            {
                "name": "direction",
                "type": "string",
                "description": "increase (raise taxes) or decrease (cut taxes)",
                "required": True
            },
            {
                "name": "amount",
                "type": "float",
                "description": "adjustment magnitude (default 0.05 = 5%)",
                "required": False,
                "default": 0.05
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        调整税率
        
        Government的price属性代表税率
        """
        direction = params.get('direction', 'maintain') if params else 'maintain'
        amount = params.get('amount', 0.05) if params else 0.05
        
        old_tax_rate = agent.price
        
        if direction == 'increase':
            agent.price = min(5.0, agent.price * (1 + amount))
        elif direction == 'decrease':
            agent.price = max(0.1, agent.price * (1 - amount))
        
        return {
            "success": True,
            "old_tax_rate": old_tax_rate,
            "new_tax_rate": agent.price,
            "direction": direction
        }


class ProvideStimulusAction(Action):
    """
    发放经济刺激金 - 向低收入群体发钱
    
    适用场景:
    - 失业率高
    - 经济衰退
    - 疫情严重影响民生
    
    参数:
    - amount: 总金额(从government.wealth扣除)
    - target_stratum: 目标阶层(0-4,默认0-1为贫困和低收入)
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Provide economic stimulus - Direct cash payments to target groups
        
        Parameters:
        - amount: Total budget for stimulus
        - target_group: 'stratum' (default) or 'unemployed'
        - target_stratum: If group='stratum', which income level (0=Q1, 4=Q5)
        """
    
    def get_parameters(self):
        return [
            {
                "name": "amount",
                "type": "float",
                "description": "total amount (from government budget)",
                "required": True
            },
            {
                "name": "target_stratum",
                "type": "int",
                "description": "target stratum (0-4, default 0=poorest). Ignored if target_group='unemployed'",
                "required": False,
                "default": 0
            },
            {
                "name": "target_group",
                "type": "string",
                "description": "target group: 'stratum' (by income level) or 'unemployed' (all unemployed)",
                "required": False,
                "default": "stratum"
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        发放刺激金
        
        逻辑:
        1. 从government.wealth扣除
        2. 平均分配给目标群体 (stratum 或 unemployed)
        """
        if params is None:
            params = {}
        
        total_amount = params.get('amount', 1000)
        target_stratum = params.get('target_stratum', 0)
        target_group = params.get('target_group', 'stratum')
        
        # 检查财政是否足够
        if agent.wealth < total_amount:
            return {
                "success": False,
                "reason": "insufficient_funds",
                "available": agent.wealth,
                "requested": total_amount
            }
        
        # 找到目标群体
        from covid_abs.network.agents import Person
        
        if target_group == 'unemployed':
            # 针对所有失业者
            target_people = [
                p for p in simulation.population 
                if isinstance(p, Person) 
                and p.employer is None
                and p.age > 16 and p.age <= 65  # 工作年龄
                and p.status.name != 'Death'
            ]
            group_desc = "all unemployed"
        else:
            # 针对特定阶层 (默认)
            target_people = [
                p for p in simulation.population 
                if isinstance(p, Person) 
                and p.social_stratum == target_stratum
                and p.status.name != 'Death'
            ]
            group_desc = f"stratum Q{target_stratum+1}"
        
        if len(target_people) == 0:
            return {
                "success": False,
                "reason": "no_target_people",
                "target_group": target_group,
                "target_stratum": target_stratum
            }
        
        # 发放刺激金
        per_person = total_amount / len(target_people)
        for person in target_people:
            person.wealth += per_person
        
        # 从政府财政扣除
        agent.wealth -= total_amount
        
        return {
            "success": True,
            "total_amount": total_amount,
            "recipients": len(target_people),
            "per_person": per_person,
            "target_group": group_desc,
            "government_wealth_remaining": agent.wealth
        }


class IncreaseMedicalBudgetAction(Action):
    """
    增加医疗预算 - 向Healthcare拨款
    
    适用场景:
    - 疫情严重
    - 医疗系统过载
    - 死亡率上升
    
    参数:
    - amount: 拨款金额
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Increase medical budget - Allocate funds to expand healthcare capacity"
    
    def get_parameters(self):
        return [
            {
                "name": "amount",
                "type": "float",
                "description": "funding amount",
                "required": True
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        向Healthcare拨款
        """
        if params is None:
            params = {}
        
        amount = params.get('amount', 500)
        
        # 检查财政
        if agent.wealth < amount:
            return {
                "success": False,
                "reason": "insufficient_funds",
                "available": agent.wealth,
                "requested": amount
            }
        
        # 拨款
        agent.wealth -= amount
        simulation.healthcare.wealth += amount
        
        return {
            "success": True,
            "amount": amount,
            "government_wealth_remaining": agent.wealth,
            "healthcare_wealth_new": simulation.healthcare.wealth
        }


class IssueStayHomeOrderAction(Action):
    """
    发布居家令 - 强制所有Person留在家中
    
    适用场景:
    - 疫情爆发严重
    - 感染率飙升
    - 需要强制隔离
    
    实现: 设置全局标志,影响Person的决策
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Issue stay-at-home order - Mandatory lockdown for entire population"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        设置居家令标志
        
        注意: 需要在GraphStatusPool中添加policy字段
        """
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['stay_home_order'] = True
        
        return {
            "success": True,
            "policy": "stay_home_order",
            "status": "active"
        }


class IssueMandatoryStayHomeOrderAction(Action):
    """
    发布强制居家令 (Scenario B专供) - 极度严格的管控
    
    适用场景:
    - Scenario B (Health Priority)
    - 感染率触发Circuit Breaker
    
    Prompt强化:
    - 明确告知Person: "政府已经颁布了居家命令！除非就医或获取生活必须物资时的购物外，应尽可能配合政府的管控"
    - 语气更强硬，要求配合
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Issue MANDATORY Stay-at-Home Order (Health Priority)
        
        [CRITICAL] Invoke emergency powers to enforce strict lockdown.
        
        [EFFECT] 
        - Issues a direct command to all citizens.
        - Message to population: "GOVERNMENT ORDER: MANDATORY LOCKDOWN. Stay home unless absolutely necessary (medical/essential food). Compliance is required."
        - Expected to drastically reduce mobility and contact rate.
        
        [USE WHEN] 
        - Infection rate > 10% (Circuit Breaker triggered)
        - Immediate suppression is required
        """
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        设置强制居家令标志
        """
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            # 设置基础标志 (兼容旧逻辑)
            simulation.status_pool.government_policy['stay_home_order'] = True
            # 设置增强标志 (用于生成强硬Prompt)
            simulation.status_pool.government_policy['mandatory_lockdown'] = True
        
        return {
            "success": True,
            "policy": "mandatory_stay_home_order",
            "status": "active",
            "message": "Strict lockdown enforced"
        }


class LiftStayHomeOrderAction(Action):
    """
    解除居家令 - 允许恢复正常活动
    
    适用场景:
    - 疫情缓解
    - 感染率下降
    - 经济需要重启
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Lift stay-at-home order - Resume normal social activities"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        解除居家令标志
        """
        # 更新agent的policy
        if hasattr(agent, 'policy'):
            agent.policy['stay_home_order'] = False
            if 'mandatory_lockdown' in agent.policy:
                agent.policy['mandatory_lockdown'] = False
        
        # 更新StatusPool
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['stay_home_order'] = False
            # ✅ 关键修复：同时清除强制封锁标志
            if 'mandatory_lockdown' in simulation.status_pool.government_policy:
                simulation.status_pool.government_policy['mandatory_lockdown'] = False
        
        return {
            "success": True,
            "policy": "stay_home_order",
            "status": "lifted"
        }


class CloseBordersAction(Action):
    """
    关闭边境 - 防止外部输入
    
    适用场景:
    - 疫情早期
    - 外部感染严重
    
    实现: 设置标志(原系统可能没有边境机制,仅作标记)
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Close borders - Prevent external case imports"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        关闭边境
        """
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['borders_closed'] = True
        
        return {
            "success": True,
            "policy": "borders_closed",
            "status": "closed"
        }


class MaintainPolicyAction(Action):
    """
    维持现有政策 - 不做任何改变
    
    适用场景:
    - 当前政策有效
    - 需要观察效果
    - 无需干预
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Maintain current policy - Observe effects of existing measures"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        不做任何操作
        """
        return {
            "success": True,
            "action": "maintain",
            "message": "policy unchanged"
        }


class ForeignTradeAction(Action):
    """
    对外贸易Action - Business专用
    
    机制：
    1. 消耗一定数量的stocks库存（用于出口）
    2. 根据Business的social_stratum计算收益
    3. 收益 = base_amount × (stratum + 1) × export_qty
    4. 仅在economy_openness > 0时可用
    
    适用场景：
    - Business库存充足
    - 想要增加收入
    - 经济环境允许对外贸易
    """
    
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Foreign trade - Export products for foreign currency revenue
        
[ECONOMIC BENEFITS] Immediate cash income, independent of local market demand
- High returns based on product tier (Q1 business: ×1, Q5 business: ×5)
- Higher economy openness = stronger international demand (up to 150% revenue bonus)
- Only consumes inventory (stocks), no need to wait for local customers

[REQUIREMENTS] Sufficient inventory (stocks >= 3) and open economy environment

[IDEAL SCENARIOS]
1. Tight cash flow, need quick revenue generation
2. Insufficient local demand (high unemployment, severe epidemic)
3. Inventory backlog, no buyers
4. Strong profitability, want to maximize income

[NOTE] Consumes 3-15 units of inventory for export"""
    
    def get_parameters(self):
        return []
    
    def is_available(self, agent, simulation):
        """
        检查Action是否可用
        
        条件：
        1. 必须是Business类型
        2. 经济开放度 > 0（非完全封闭经济）
        3. 有足够的stocks库存（至少5个）
        """
        from covid_abs.network.agents import Business, AgentType
        
        # 条件1：必须是Business
        if not isinstance(agent, Business) or agent.type == AgentType.Government:
            return False
        
        # 条件2：经济开放度 > 0
        if simulation.economy_openness <= 0.0:
            return False
        
        # 条件3：有足够的stocks（降低门槛至3，让更多Business可以使用）
        if agent.stocks < 3:
            return False
        
        return True
    
    def execute(self, agent, simulation, params=None):
        """
        执行对外贸易
        
        计算逻辑：
        1. export_qty = min(stocks, 10 + random(5))  # 出口数量
        2. base_revenue = price × (stratum + 1)  # 单位收益
        3. total_revenue = base_revenue × export_qty × openness_bonus
        4. openness_bonus = 1 + (openness - 0.5)  # 开放度越高，国际市场越活跃
        
        Returns:
            dict: {
                "success": bool,
                "revenue": float,
                "export_qty": int,
                "stocks_after": int
            }
        """
        from covid_abs.network.agents import Business, AgentType
        
        # 安全检查
        if not isinstance(agent, Business) or agent.type == AgentType.Government:
            return {
                "success": False,
                "error": "foreign_trade can only be executed by Business agents"
            }
        
        if simulation.economy_openness <= 0.0:
            return {
                "success": False,
                "error": "cannot conduct foreign trade in completely closed economy"
            }
        
        if agent.stocks < 3:
            return {
                "success": False,
                "error": "insufficient inventory for export (requires at least 3 stocks)"
            }
        
        # 计算出口数量
        max_export = min(agent.stocks, 15)  # 最多出口15个（保留一些库存）
        min_export = 3  # 最少出口3个（降低门槛）
        export_qty = np.random.randint(min_export, max_export + 1)
        
        # 计算收益
        # 基础单价：price × (stratum + 1)
        # Q1 (stratum=0): price × 1
        # Q5 (stratum=4): price × 5  (高端产品出口价格高)
        base_unit_revenue = agent.price * (agent.social_stratum + 1)
        
        # 开放度加成：经济越开放，国际市场需求越旺盛
        # openness=0.3 → bonus=0.8  (80%收益)
        # openness=0.5 → bonus=1.0  (100%收益)
        # openness=1.0 → bonus=1.5  (150%收益)
        openness_bonus = 1.0 + (simulation.economy_openness - 0.5)
        
        # 总收益
        total_revenue = base_unit_revenue * export_qty * openness_bonus
        
        # 执行交易
        stocks_before = agent.stocks
        agent.stocks -= export_qty  # 消耗库存
        agent.cash(total_revenue)  # 获得收入
        agent.incomes += total_revenue  # 记录月度收入
        
        return {
            "success": True,
            "action": "foreign_trade",
            "export_qty": export_qty,
            "revenue": total_revenue,
            "unit_revenue": base_unit_revenue,
            "openness_bonus": openness_bonus,
            "stocks_before": stocks_before,
            "stocks_after": agent.stocks,
            "stratum": agent.social_stratum,
            "message": f"Exported {export_qty} products, earned {total_revenue:.2f} (Q{agent.social_stratum+1} business)"
        }


class PublicProcurementAction(Action):
    """
    政府公共采购行动 - 由LLM决策的策略性采购
    
    替代原系统的Rule-based随机采购逻辑
    
    功能:
    - Government向指定Business采购商品/服务
    - 支持本地经济（特别是困难企业）
    - 刺激特定行业/阶层
    
    策略考虑:
    - 财政状况（Government wealth是否充足）
    - 经济形势（Business破产风险、失业率）
    - 疫情影响（Business是否开门、是否需要支持）
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Public procurement - Purchase goods/services from local businesses to support specific industries or struggling enterprises"
    
    def get_parameters(self):
        return [
            {
                "name": "target_stratum",
                "type": "int",
                "description": "target business stratum (0=Q1 low-end, 4=Q5 high-end)",
                "default": 2,
                "min": 0,
                "max": 4
            },
            {
                "name": "procurement_amount",
                "type": "float",
                "description": "procurement amount multiplier (relative to normal purchase volume)",
                "default": 1.0,
                "min": 0.5,
                "max": 3.0
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        执行公共采购
        
        逻辑:
        1. 检查Government财富是否充足
        2. 选择目标阶层的Business
        3. 过滤：只向营业中的Business采购
        4. 优先选择：财富较低（需要支持）的Business
        5. 执行采购：Business.supply(government)
        """
        if params is None:
            params = {}
        
        target_stratum = params.get('target_stratum', 2)  # 默认中层Business
        amount_multiplier = params.get('procurement_amount', 1.0)
        
        # 获取目标阶层的所有Business
        target_businesses = [
            b for b in simulation.business
            if b.social_stratum == target_stratum and b.open
        ]
        
        if not target_businesses:
            return {
                "success": False,
                "reason": f"no open business in stratum {target_stratum}",
                "target_stratum": target_stratum
            }
        
        # 优先选择财富较低的Business（需要支持）
        target_businesses.sort(key=lambda b: b.wealth)
        
        # 选择最需要支持的Business（财富最低）
        target_business = target_businesses[0]
        
        # 检查Government财富
        # 估算采购金额（基于Business的price和随机数量）
        estimated_qty = int(np.random.randint(1, 10) * amount_multiplier)
        estimated_cost = target_business.price * (agent.social_stratum + 1) * estimated_qty
        
        if agent.wealth < estimated_cost:
            return {
                "success": False,
                "reason": "insufficient government funds",
                "government_wealth": agent.wealth,
                "estimated_cost": estimated_cost
            }
        
        # 执行采购
        target_business.supply(agent)
        
        return {
            "success": True,
            "action": "procurement",
            "target_business_id": target_business.id,
            "target_stratum": target_stratum,
            "business_wealth_before": target_business.wealth,
            "message": f"Government purchased from Business (Q{target_stratum+1})"
        }


# ============================================================================
# 🎬 ADDITIONAL GOVERNMENT POLICY ACTIONS (Rich Policy Toolkit)
# ============================================================================

class IssueBusinessSubsidyAction(Action):
    """
    发放企业补贴 - 定向支持特定阶层的企业
    
    适用场景：
    - Business大量倒闭/关闭
    - 特定行业需要支持（如小商户Q1-Q2）
    - 疫情期间维持企业运营
    
    参数：
    - total_amount: 总补贴金额
    - target_stratum: 目标企业阶层（0-4）
    - per_business: 每个企业获得的固定金额
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """💼 Issue business subsidy - Direct financial support to businesses
        
[PURPOSE] Help businesses survive during crisis, prevent mass closures

[BENEFITS]
- Reduce business closure rate
- Maintain employment
- Preserve economic capacity
- Support specific sectors (e.g., small businesses Q1-Q2)

[USE WHEN]
- Many businesses are closing
- Unemployment is rising due to business failures
- Want to protect small businesses
- Economic stimulus for businesses (not individuals)

[PARAMETERS]
- total_amount: Total budget for subsidies
- target_stratum: Which business tier to support (0=Q1 street shops, 4=Q5 luxury stores)
- per_business: Fixed amount per business (alternative to total_amount)"""
    
    def get_parameters(self):
        return [
            {
                "name": "total_amount",
                "type": "float",
                "description": "total subsidy budget (will be divided among eligible businesses)",
                "required": False
            },
            {
                "name": "target_stratum",
                "type": "int",
                "description": "target business stratum (0-4, default 0=Q1 small businesses)",
                "required": False,
                "default": 0
            },
            {
                "name": "per_business",
                "type": "float",
                "description": "fixed amount per business (alternative to total_amount)",
                "required": False
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        发放企业补贴
        
        逻辑：
        1. 找到目标阶层的所有Business
        2. 平均分配补贴（或每个企业固定金额）
        3. 从Government财政扣除
        """
        if params is None:
            params = {}
        
        target_stratum = params.get('target_stratum', 0)
        per_business = params.get('per_business', None)
        total_amount = params.get('total_amount', None)
        
        # 找到目标企业
        from covid_abs.network.agents import Business, AgentType
        target_businesses = [
            b for b in simulation.business
            if isinstance(b, Business)
            and b.type == AgentType.Business
            and b.social_stratum == target_stratum
        ]
        
        if len(target_businesses) == 0:
            return {
                "success": False,
                "reason": "no_eligible_businesses",
                "target_stratum": target_stratum
            }
        
        # 计算金额
        if per_business is not None:
            total_needed = per_business * len(target_businesses)
        elif total_amount is not None:
            total_needed = total_amount
            per_business = total_amount / len(target_businesses)
        else:
            # 默认：每个企业1000
            per_business = 1000
            total_needed = per_business * len(target_businesses)
        
        # 检查财政
        if agent.wealth < total_needed:
            return {
                "success": False,
                "reason": "insufficient_funds",
                "available": agent.wealth,
                "requested": total_needed
            }
        
        # 发放补贴
        for business in target_businesses:
            business.wealth += per_business
        
        # 扣除财政
        agent.wealth -= total_needed
        
        return {
            "success": True,
            "total_amount": total_needed,
            "recipients": len(target_businesses),
            "per_business": per_business,
            "target_stratum": target_stratum,
            "government_wealth_remaining": agent.wealth
        }


class ImplementContactTracingAction(Action):
    """
    实施接触追踪 - 加强疫情管理和早期预警
    
    适用场景：
    - 疫情早期，需要精准防控
    - 感染率上升，需要追踪传播链
    - 有足够医疗资源支持隔离
    
    实现：
    - 设置policy标志，可能影响传播率（需要在simulation中实现）
    - 当前实现：标记政策状态，为未来扩展预留
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """🔍 Implement contact tracing - Track and isolate infection chains
        
[PURPOSE] Identify and isolate infected individuals early, break transmission chains

[BENEFITS]
- Reduce undetected spread
- Enable targeted isolation (avoid full lockdown)
- Early intervention for high-risk contacts
- Data-driven epidemic management

[USE WHEN]
- Infection rate is rising but manageable (<5%)
- Want to avoid full lockdown
- Healthcare system has capacity for testing and isolation
- Early stage of outbreak (most effective)

[TRADE-OFFS]
- Requires government resources
- Privacy concerns (low priority in simulation)
- Only effective if infection rate is not too high

[NOTE] Most effective when combined with testing capacity and isolation facilities"""
    
    def get_parameters(self):
        return [
            {
                "name": "intensity",
                "type": "string",
                "description": "basic (low resources) or comprehensive (high resources)",
                "required": False,
                "default": "basic"
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        实施接触追踪
        
        当前实现：设置policy标志
        未来可扩展：降低传播率，增加早期检测
        """
        if params is None:
            params = {}
        
        intensity = params.get('intensity', 'basic')
        
        # 设置政策标志
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['contact_tracing'] = True
            simulation.status_pool.government_policy['contact_tracing_intensity'] = intensity
        
        # 扣除实施成本
        cost = 500 if intensity == 'basic' else 2000
        if agent.wealth >= cost:
            agent.wealth -= cost
        
        return {
            "success": True,
            "policy": "contact_tracing",
            "intensity": intensity,
            "cost": cost,
            "government_wealth_remaining": agent.wealth
        }


class LaunchVaccinationCampaignAction(Action):
    """
    启动疫苗接种活动 - 建立免疫屏障
    
    适用场景：
    - 疫情持续，需要长期解决方案
    - 经济无法承受长期封锁
    - 医疗系统压力大
    
    实现：
    - 随机选择部分Person转为Recovered_Immune状态
    - 扣除疫苗成本
    
    参数：
    - coverage: 接种覆盖率（0.0-1.0）
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """💉 Launch vaccination campaign - Build immunity in population
        
[PURPOSE] Create immunity barrier, reduce transmission and severe cases

[BENEFITS]
- Long-term solution to epidemic
- Reduce hospitalization and death rates
- Allow economic reopening safely
- Protect vulnerable populations

[USE WHEN]
- Epidemic is prolonged (not ending naturally)
- Cannot sustain long-term lockdown
- Want to safely reopen economy
- Healthcare system is under sustained pressure

[PARAMETERS]
- coverage: Vaccination coverage rate (0.0-1.0, e.g., 0.6 = 60% of population)
- priority_group: 'elderly' (prioritize high-risk) or 'general' (random)

[COST] High upfront investment, but saves long-term economic and health costs

[NOTE] Simulates immediate immunity (real vaccination has delays and requires 2 doses)"""
    
    def get_parameters(self):
        return [
            {
                "name": "coverage",
                "type": "float",
                "description": "vaccination coverage rate (0.0-1.0, e.g., 0.6 = 60%)",
                "required": True
            },
            {
                "name": "priority_group",
                "type": "string",
                "description": "elderly (prioritize age>60) or general (random)",
                "required": False,
                "default": "general"
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        启动疫苗接种活动
        
        逻辑：
        1. 计算成本（每人疫苗成本 × 接种人数）
        2. 随机选择Person进行接种
        3. 将其状态设为Recovered_Immune
        """
        if params is None:
            params = {}
        
        coverage = params.get('coverage', 0.5)
        priority_group = params.get('priority_group', 'general')
        
        # 验证参数
        if not 0.0 <= coverage <= 1.0:
            return {
                "success": False,
                "reason": "invalid_coverage",
                "coverage": coverage
            }
        
        # 找到可接种的Person（未死亡且未感染）
        from covid_abs.network.agents import Person
        from covid_abs.agents import Status
        
        eligible_people = [
            p for p in simulation.population
            if isinstance(p, Person)
            and p.status != Status.Death
            and p.status != Status.Infected  # 不给感染者接种
        ]
        
        if len(eligible_people) == 0:
            return {
                "success": False,
                "reason": "no_eligible_people"
            }
        
        # 根据优先级分组
        if priority_group == 'elderly':
            # 优先给老年人接种
            elderly = [p for p in eligible_people if p.age >= 60]
            young = [p for p in eligible_people if p.age < 60]
            
            target_count = int(len(eligible_people) * coverage)
            elderly_count = min(len(elderly), target_count)
            young_count = target_count - elderly_count
            
            selected = elderly[:elderly_count] + young[:young_count]
        else:
            # 随机选择
            import random
            target_count = int(len(eligible_people) * coverage)
            selected = random.sample(eligible_people, target_count)
        
        # 计算成本（每人100元疫苗成本）
        cost_per_person = 100
        total_cost = cost_per_person * len(selected)
        
        # 检查财政
        if agent.wealth < total_cost:
            return {
                "success": False,
                "reason": "insufficient_funds",
                "available": agent.wealth,
                "requested": total_cost
            }
        
        # 接种（设为Recovered_Immune状态）
        vaccinated_count = 0
        for person in selected:
            if person.status == Status.Susceptible or person.status == Status.Recovered_Immune:
                person.status = Status.Recovered_Immune
                vaccinated_count += 1
        
        # 扣除财政
        agent.wealth -= total_cost
        
        return {
            "success": True,
            "vaccinated_count": vaccinated_count,
            "target_coverage": coverage,
            "actual_coverage": vaccinated_count / len(simulation.population),
            "total_cost": total_cost,
            "priority_group": priority_group,
            "government_wealth_remaining": agent.wealth
        }


class IssuePartialLockdownAction(Action):
    """
    发布部分封锁令 - 介于完全封锁和正常生活之间的折中方案
    
    适用场景：
    - 感染率中等（2-5%），全面封锁过激，不封锁不够
    - 经济压力大，无法承受全面封锁
    - 需要平衡健康和经济
    
    实现：
    - 设置partial_lockdown标志
    - 可结合其他规则（如限制Business营业时间、降低移动频率等）
    
    参数：
    - severity: 'light'（轻度限制）或 'moderate'（中度限制）
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """Issue partial lockdown - Balanced restrictions (between full lockdown and normal)
        
[PURPOSE] Reduce transmission while minimizing economic damage

[BENEFITS]
- Reduce infection spread (not as effective as full lockdown)
- Maintain essential economic activities
- Lower social and economic costs than full lockdown
- Flexible approach for moderate infection rates

[USE WHEN]
- Infection rate is moderate (2-5%)
- Full lockdown is too costly (high unemployment, business closures)
- Healthcare system is under pressure but not collapsing
- Need a middle-ground solution

[SEVERITY LEVELS]
- light: Reduce mobility by 30%, businesses operate with restrictions
- moderate: Reduce mobility by 60%, non-essential businesses close

[TRADE-OFFS]
- Less effective than full lockdown for epidemic control
- More effective than no intervention
- Better economic outcomes than full lockdown

[NOTE] Can lift to normal or escalate to full lockdown based on situation"""
    
    def get_parameters(self):
        return [
            {
                "name": "severity",
                "type": "string",
                "description": "light (30% mobility reduction) or moderate (60% reduction)",
                "required": False,
                "default": "light"
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        发布部分封锁令
        
        当前实现：设置policy标志
        未来可扩展：降低Person移动频率、限制Business营业时间等
        """
        if params is None:
            params = {}
        
        severity = params.get('severity', 'light')
        
        # 设置政策标志
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['partial_lockdown'] = True
            simulation.status_pool.government_policy['lockdown_severity'] = severity
            # 如果有部分封锁，则取消完全封锁
            simulation.status_pool.government_policy['stay_home_order'] = False
        
        return {
            "success": True,
            "policy": "partial_lockdown",
            "severity": severity,
            "status": "active"
        }


class LiftPartialLockdownAction(Action):
    """
    解除部分封锁令 - 恢复正常经济活动
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Lift partial lockdown - Resume normal economic activity"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        解除部分封锁令
        """
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['partial_lockdown'] = False
        
        return {
            "success": True,
            "policy": "partial_lockdown",
            "status": "lifted"
        }


class AdjustBusinessRegulationAction(Action):
    """
    调整营业规定 - 精细化控制Business运营
    
    适用场景：
    - 想要限制传播但不完全关闭经济
    - 特定行业需要管控（如娱乐场所、大型商场）
    - 配合部分封锁使用
    
    实现：
    - 设置regulations标志，限制特定stratum的Business
    - 可设置营业时间限制、容量限制等
    
    参数：
    - affected_strata: 受影响的Business阶层列表
    - restriction_type: 'capacity_limit'（容量限制）或 'hour_limit'（时间限制）
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return """📋 Adjust business regulations - Fine-tuned operational restrictions
        
[PURPOSE] Control high-risk business sectors without full economic shutdown

[BENEFITS]
- Target high-risk businesses (e.g., Q5 luxury stores with high customer density)
- Allow essential businesses to continue (e.g., Q1-Q2 small shops)
- Flexible control based on business type
- Reduce transmission in commercial settings

[USE WHEN]
- Want to control transmission without full lockdown
- Certain business types are high-risk (large venues, luxury stores)
- Need sector-specific regulations
- Infection rate is moderate but concerning

[REGULATION TYPES]
- capacity_limit: Reduce customer capacity (simulated, symbolic)
- hour_limit: Reduce operating hours (simulated, symbolic)

[PARAMETERS]
- affected_strata: List of business tiers to restrict (e.g., [3,4] = Q4-Q5 high-end stores)
- restriction_type: Type of restriction to impose

[NOTE] Can be combined with partial lockdown for comprehensive control"""
    
    def get_parameters(self):
        return [
            {
                "name": "affected_strata",
                "type": "list",
                "description": "list of business strata to restrict (e.g., [3,4] for Q4-Q5)",
                "required": True
            },
            {
                "name": "restriction_type",
                "type": "string",
                "description": "capacity_limit or hour_limit",
                "required": False,
                "default": "capacity_limit"
            }
        ]
    
    def execute(self, agent, simulation, params=None):
        """
        调整营业规定
        
        当前实现：设置policy标志
        未来可扩展：实际限制Business的供应能力、营业时间等
        """
        if params is None:
            params = {}
        
        affected_strata = params.get('affected_strata', [])
        restriction_type = params.get('restriction_type', 'capacity_limit')
        
        # 设置政策标志
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['business_regulations'] = {
                'active': True,
                'affected_strata': affected_strata,
                'restriction_type': restriction_type
            }
        
        return {
            "success": True,
            "policy": "business_regulations",
            "affected_strata": affected_strata,
            "restriction_type": restriction_type,
            "status": "active"
        }


class LiftBusinessRegulationAction(Action):
    """
    解除营业规定 - 恢复Business正常运营
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "Lift business regulations - Resume normal business operations"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        解除营业规定
        """
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy['business_regulations'] = {
                'active': False
            }
        
        return {
            "success": True,
            "policy": "business_regulations",
            "status": "lifted"
        }


class EmergencyLockdownAction(Action):
    """
    紧急封锁动作 - Health Priority场景专用
    当感染率超过15%时自动触发，不需要等待政府决策周期
    """
    def __init__(self):
        super().__init__()
    
    def get_description(self):
        return "EMERGENCY LOCKDOWN - Automatic activation when infection rate exceeds 15% (health_priority scenario only)"
    
    def get_parameters(self):
        return []
    
    def execute(self, agent, simulation, params=None):
        """
        执行紧急封锁
        这个动作由系统自动触发，不是LLM决策的结果
        """
        if params is None:
            params = {}
        
        # 更新政府政策
        agent.policy['stay_home_order'] = True
        agent.policy['borders_closed'] = True
        
        # 同步到StatusPool
        if hasattr(simulation, 'status_pool') and simulation.status_pool:
            simulation.status_pool.government_policy = agent.policy.copy()
        
        # 计算当前感染率
        infected_count = sum(1 for a in simulation.population if a.status == Status.Infected)
        infection_rate = infected_count / max(simulation.population_size, 1)
        
        return {
            "success": True,
            "policy": "emergency_lockdown",
            "stay_home_order": True,
            "borders_closed": True,
            "trigger": "automatic",
            "infection_rate": infection_rate,
            "threshold": 0.15,
            "status": "EMERGENCY ACTIVATED"
        }