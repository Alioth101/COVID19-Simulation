from enum import Enum
import os

import numpy as np

from covid_abs.agents import Agent, AgentType, InfectionSeverity, Status
from covid_abs.common import *
from covid_abs.network.log_config import DEBUG_CASHFLOW, DEBUG_LOG_FILE
from covid_abs.economic_logger import economic_logger

# ============================================================================
# ⚠️⚠️⚠️ 调试功能：追踪Person财富流动
# ============================================================================
def log_cashflow(iteration, day, hour, message):
    """记录现金流日志"""
    if not DEBUG_CASHFLOW:
        return
    try:
        # 构建完整日志消息
        full_message = f"[Iter{iteration:4d} Day{day:2d}H{hour:2d}] {message}"
        
        # 直接写入文件并立即刷新（确保实时写入）
        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:  # buffering=1 = 行缓冲
            f.write(full_message + "\n")
            f.flush()  # 强制刷新
            os.fsync(f.fileno())  # 强制写入磁盘
    except Exception as e:
        # 调试：记录错误
        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"LOG ERROR: {e} - {message}\n")

def log_wealth_change(iteration, day, hour, agent_type, agent_id, old_wealth, new_wealth, reason, source=""):
    """记录财富变化（精确追踪）"""
    if not DEBUG_CASHFLOW:
        return
    change = new_wealth - old_wealth
    if abs(change) > 0.01:  # 只记录有实际变化的
        try:
            # 构建日志消息
            message = (f"[Iter{iteration:4d} Day{day:2d}H{hour:2d}] "
                      f"💰 {agent_type}({agent_id[-8:]}) wealth: {old_wealth:.2f}→{new_wealth:.2f} "
                      f"({change:+.2f}) | {reason} | {source}")
            
            # 只写入文件（不输出到控制台）并立即刷新
            with open(DEBUG_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:
                f.write(message + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            pass

# ============================================================================
# 共享工具函数
# ============================================================================

def extract_json_from_llm_response(text: str) -> str:
    """
    从LLM响应文本中智能提取完整的JSON对象
    支持嵌套的{}、多行文本、字符串中的引号转义、移除//和/* */注释
    增强了对LLM生成错误的容错处理（如多余的引号）
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        str: 提取的JSON字符串,如果没找到返回空字符串
    """
    import re
    import json
    
    def fix_common_json_errors(json_str: str) -> str:
        """修复LLM生成的常见JSON错误"""
        # 修复方法：使用正则表达式替换多余的引号
        # 模式：在非转义的引号后，如果紧跟着更多引号，只保留一个
        
        # 步骤1：修复 ""+ （连续的多个引号）为单个引号
        # 使用更简单的方法：扫描整个字符串，当遇到 "" 时，检查是否是字符串值的结尾
        result = []
        i = 0
        in_string = False
        escape_next = False
        
        while i < len(json_str):
            char = json_str[i]
            
            # 处理转义字符
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\' and in_string:
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            # 处理引号
            if char == '"':
                if in_string:
                    # 这是字符串的结束引号
                    result.append(char)
                    in_string = False
                    i += 1
                    
                    # 跳过所有紧跟的多余引号
                    while i < len(json_str) and json_str[i] == '"':
                        i += 1
                    continue
                else:
                    # 这是字符串的开始引号
                    result.append(char)
                    in_string = True
                    i += 1
                    continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def remove_json_comments(json_str: str) -> str:
        """移除JSON字符串中的 // 和 /* */ 注释"""
        result = []
        i = 0
        in_string = False
        escape_next = False
        
        while i < len(json_str):
            char = json_str[i]
            
            # 处理字符串状态
            if char == '"' and not escape_next:
                in_string = not in_string
                result.append(char)
                i += 1
                continue
            elif char == '\\' and not escape_next:
                escape_next = True
                result.append(char)
                i += 1
                continue
            
            escape_next = False
            
            # 只在非字符串中移除注释
            if not in_string:
                # 检查 // 单行注释
                if char == '/' and i + 1 < len(json_str) and json_str[i + 1] == '/':
                    # 跳过到行尾
                    while i < len(json_str) and json_str[i] not in ['\n', '\r']:
                        i += 1
                    continue
                
                # 检查 /* */ 多行注释
                if char == '/' and i + 1 < len(json_str) and json_str[i + 1] == '*':
                    # 跳过到 */
                    i += 2
                    while i < len(json_str) - 1:
                        if json_str[i] == '*' and json_str[i + 1] == '/':
                            i += 2
                            break
                        i += 1
                    continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    # 预处理：先对整个文本进行简单的多余引号修复
    # 这样可以确保后续的字符串状态检测正确工作
    text_preprocessed = fix_common_json_errors(text)
    
    # 查找所有可能的JSON起始位置(包含"action"关键字)
    matches = list(re.finditer(r'\{[^{}]*"action"[^{}]*:', text_preprocessed, re.DOTALL))
    
    if not matches:
        return ""
    
    # 尝试每个匹配位置,找到第一个有效的完整JSON
    for match in matches:
        start_pos = match.start()
        
        # 从起始位置开始,匹配完整的{}对
        brace_count = 0
        in_string = False
        escape_next = False
        last_valid_pos = start_pos
        
        for i, char in enumerate(text_preprocessed[start_pos:], start=start_pos):
            # 处理字符串中的引号
            if char == '"' and not escape_next:
                in_string = not in_string
            elif char == '\\' and not escape_next:
                escape_next = True
                continue
            
            escape_next = False
            
            # 只在非字符串中计数花括号
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # 找到完整的JSON对象
                    if brace_count == 0:
                        json_str = text_preprocessed[start_pos:i+1]
                        
                        # 移除注释
                        json_str_clean = remove_json_comments(json_str)
                        
                        # 🔧 修复尾部逗号（trailing commas）- LLM常见错误
                        # 移除对象/数组最后一个元素后的逗号
                        json_str_clean = re.sub(r',(\s*[}\]])', r'\1', json_str_clean)
                        
                        # 验证是否是有效JSON
                        try:
                            json.loads(json_str_clean)
                            return json_str_clean
                        except json.JSONDecodeError:
                            # 这个不是有效JSON,尝试下一个匹配
                            break
            
            # 记录最后一个有效位置（用于修复不完整的JSON）
            last_valid_pos = i
        
        # 🔧 [NEW] 如果扫描到末尾仍未找到完整JSON，尝试修复不完整的JSON
        if brace_count > 0:
            # JSON不完整，缺少闭合括号
            json_str = text_preprocessed[start_pos:last_valid_pos+1]
            
            # 移除注释
            json_str_clean = remove_json_comments(json_str)
            
            # 修复尾部逗号
            json_str_clean = re.sub(r',(\s*[}\]])', r'\1', json_str_clean)
            
            # 🔧 检查是否有未闭合的字符串
            # 如果最后一个字符不是引号、括号或空白，可能是字符串被截断
            json_str_stripped = json_str_clean.rstrip()
            if json_str_stripped and json_str_stripped[-1] not in '"}]':
                # 可能是字符串被截断，添加引号
                json_str_clean = json_str_clean + '"'
            
            # 添加缺少的闭合括号
            json_str_fixed = json_str_clean + '}' * brace_count
            
            # 验证修复后的JSON
            try:
                json.loads(json_str_fixed)
                print(f"[JSON Fix] Auto-fixed incomplete JSON by adding {brace_count} closing brace(s)")
                return json_str_fixed
            except json.JSONDecodeError as e:
                # 修复失败，尝试下一个匹配
                # 记录详细错误信息用于诊断
                # print(f"[JSON Fix] Failed to fix: {str(e)[:50]}")
                continue
    
    # 如果所有匹配都失败,返回空字符串
    return ""


# ============================================================================
# Agent类定义
# ============================================================================

class EconomicalStatus(Enum):
    Active = 1
    Inactive = 0


class Business(Agent):
    """
    The container of Agent's attributes and status
    """
    def __init__(self, **kwargs):
        super(Business, self).__init__(**kwargs)
        self.employees = []
        self.num_employees = 0
        self.initial_employees = 10  # ✨ 新增：初始员工数基准（会被实际值覆盖）
        self.type = AgentType.Business
        self.incomes = 0.0
        self.expenses = 0.0
        #self.labor_expenses = {}
        self.stocks = 10
        self.sales = 0
        self.open = True
        self.type = kwargs.get("type", AgentType.Business)
        # ✅ 优化：大幅降低Shopping价格，减缓Day 0-30财富流失速度
        # 实测数据（base_price=7.0）：5天损失8.74%，推算30天损失52.5%
        # 原论文预期：30天损失约10%
        # 计算：需降价81% → 7.0 × (1-0.81) = 1.33
        # 新设计：(stratum+1) × 1.33 → 预期30天损失约10%
        self.price = kwargs.get("price", (self.social_stratum+1) * 2)
        
        # ========================================
        # Business运营成本设计（优化版）
        # ========================================
        # 【设计理念】
        # fixed_expenses = 员工数量 × 阶层系数
        # 
        # - 员工数量：反映企业规模（办公/营业面积需求）
        # - 阶层系数：反映企业档次（装修质量、租金水平、设备等级）
        #
        # 【阶层对应的真实场景】
        # Q1 (0): 街边小店、小作坊 - 简陋装修、城郊低租金
        # Q2 (1): 普通商店 - 一般装修、普通租金
        # Q3 (2): 连锁店、中型企业 - 标准装修、商业区租金
        # Q4 (3): 品牌店、知名企业 - 精致装修、高端商圈
        # Q5 (4): 奢侈品店、豪华写字楼 - 顶级装修、核心地段
        #
        # 【阶层系数设置】（可调参）
        # 基于basic_income倍数 [1, 2, 3.25, 5, 13.75]
        # 基础成本：200元/员工/月
        # 
        # 🔧 调参说明：
        # - 修改BASE_COST可调整整体成本水平（默认200）
        # - 修改STRATUM_MULTIPLIERS可调整各阶层相对差异
        # - 当前Q5是Q1的13.75倍，符合Lorenz曲线财富分配
        # ========================================
        
        # 🔧 可调参数：基础成本（元/员工/月）
        # 优先从environment获取（实验用例配置），否则使用默认值
        BASE_COST = kwargs.get('base_cost', 200)
        if hasattr(self, 'environment') and self.environment is not None:
            BASE_COST = getattr(self.environment, 'business_base_cost', BASE_COST)
        
        # 🔧 可调参数：各阶层的成本倍数（基于社会财富分配）
        # 来源：basic_income = [1, 2, 3.25, 5, 13.75]
        STRATUM_MULTIPLIERS = kwargs.get('stratum_multipliers', [1.0, 2.0, 3.25, 5.0, 13.75])
        if hasattr(self, 'environment') and self.environment is not None:
            STRATUM_MULTIPLIERS = getattr(self.environment, 'business_stratum_multipliers', STRATUM_MULTIPLIERS)
        
        # 计算该Business的单位运营成本系数
        self._cost_per_employee_monthly = BASE_COST * STRATUM_MULTIPLIERS[self.social_stratum]
        
        # 初始化fixed_expenses（无员工时为0）
        # 实际值会在hire()后由_update_fixed_expenses()计算
        self.fixed_expenses = kwargs.get('fixed_expenses', 0.0)

    def cash(self, value):
        old_wealth = self.wealth
        self.wealth += value
        
        # Log economic transaction
        if value != 0 and hasattr(self, 'environment'):
            try:
                iteration = getattr(self.environment, 'iteration', -1)
                economic_logger.log_transaction(
                    iteration=iteration,
                    source_type="External",
                    source_id="",
                    target_type=self.type.name,
                    target_id=str(self.id),
                    amount=value,
                    transaction_type="cash",
                    details={"old_wealth": old_wealth, "new_wealth": self.wealth}
                )
            except:
                pass
    
    def is_operating_hours(self, current_hour):
        """
        判断当前时间是否在营业时间范围内（强制规则）
        
        ⚠️ 强制营业时间：8:00-22:00
        - Person只能在此时间段购物
        - Business在此时间段外强制关闭（即使LLM决策open=True）
        
        Args:
            current_hour: 当前小时 (0-23)
            
        Returns:
            bool: True表示在营业时间范围内
        """
        # 强制营业时间：8:00-22:00（早8点到晚10点）
        return 8 <= current_hour < 22
    
    def is_open_now(self, current_hour):
        """
        判断Business当前是否实际营业（综合考虑LLM决策和强制营业时间）
        
        实际营业 = LLM决策意愿(self.open) AND 强制营业时间(8-22)
        
        设计说明：
        - self.open: Business LLM的决策意愿（"我想开业/关闭"）
        - is_operating_hours(): 强制营业时间规则（8-22点）
        - is_open_now(): 两者的结合，表示实际营业状态
        
        兼容性保证：
        - 无论Business决策频率是6h/12h/24h，都能正确处理
        - 例如：Business在20:00决策open=True（持续12小时）
          - 20:00-22:00: is_open_now()=True（营业时间内）
          - 22:00-08:00: is_open_now()=False（强制关闭）
          - 08:00-08:00(+12h): is_open_now()=True（恢复营业）
        
        Args:
            current_hour: 当前小时 (0-23)
            
        Returns:
            bool: True表示实际营业
        """
        # ✅ 强制营业时间约束：只有在8-22点且LLM决策open=True时才实际营业
        return self.open and self.is_operating_hours(current_hour)
    
    def _update_fixed_expenses(self):
        """
        根据当前员工数量和阶层系数更新运营成本
        
        计算公式：
        月度成本 = 员工数 × 单位月成本
        日度成本 = 月度成本 / 30（配合每日update()调用）
        
        示例（BASE_COST=200）：
        - Q1 Business, 5员工: (5 × 200) / 30 = 33.33元/天
        - Q5 Business, 5员工: (5 × 2750) / 30 = 458.33元/天
        """
        monthly_cost = len(self.employees) * self._cost_per_employee_monthly
        self.fixed_expenses = monthly_cost / 30

    def hire(self, agent):
        """
        Business雇佣方法 - 只能雇佣无症状者（符合现实）
        """
        # ✅ 安全检查：只雇佣符合条件且未被雇佣的员工
        if agent.status == Status.Death:
            return False
        if agent.infected_status != InfectionSeverity.Asymptomatic:
            return False
        if agent.employer is not None:
            return False
        if agent in self.employees:
            return False
        
        # 直接雇佣（暂时移除概率判断）
        self.employees.append(agent)
        agent.employer = self
        self.num_employees += 1
        
        # ✅ 初始化最后上班时间（避免新员工立即被判定为缺勤3天）
        if hasattr(self, 'environment') and self.environment is not None:
            agent.last_work_iteration = getattr(self.environment, 'iteration', 0)
        
        # ✅ 优化：基于员工数和阶层系数重新计算运营成本
        self._update_fixed_expenses()
        
        return True

    def fire(self, agent):
        if self.environment.callback('on_business_fire', self):
            return
        
        # 🔒 [健壮性] 确保员工在列表中，否则静默拒绝（由LLM Action过滤避免）
        if agent not in self.employees:
            # 不执行fire操作，数据保持一致
            return
        
        self.employees.remove(agent)
        #self.labor_expenses[agent.id] = None
        agent.employer = None
        agent.supply(agent.incomes)
        self.cash(-agent.incomes)
        self.num_employees -= 1
        
        # ✅ 优化：基于员工数和阶层系数重新计算运营成本
        self._update_fixed_expenses()

    def demand(self, agent):
        """Expenses due to employee payments"""
        if self.environment.callback('on_business_demand', self):
            return
        
        # ⚠️ 调试日志：记录demand调用
        try:
            iteration = getattr(self.environment, 'iteration', -1)
            day = iteration // 24 if iteration >= 0 else -1
            hour = iteration % 24 if iteration >= 0 else -1
            
            if agent in self.employees:
                branch = "EMPLOYEE"
            elif agent.type == AgentType.Healthcare:
                branch = "HEALTHCARE"
            else:
                branch = "NON_EMPLOYEE_⚠️"  # 关键：非员工调用
            
            log_cashflow(iteration, day, hour,
                        f"Business.demand() bus_id={str(self.id)[:8]} bus_type={self.type.name} "
                        f"agent_id={str(agent.id)[:8]} agent_type={agent.type.name} "
                        f"branch={branch} expenses={agent.expenses:.2f}")
        except:
            pass
        
        labor = 0
        if agent in self.employees:
            #labor = self.labor_expenses[agent.id]
            if agent.status != Status.Death and agent.infected_status == InfectionSeverity.Asymptomatic:
                labor = agent.incomes
                agent.supply(labor)
                
                # 记录工资支付
                try:
                    iteration = getattr(self.environment, 'iteration', -1)
                    day = iteration // 24 if iteration >= 0 else -1
                    hour = iteration % 24 if iteration >= 0 else -1
                    log_cashflow(iteration, day, hour,
                                f"💼 SALARY: Business({str(self.id)[:8]}) pays {labor:.2f} to Employee({str(agent.id)[:8]})")
                except:
                    pass
            #self.labor_expenses[agent.id] = 0
        elif agent.type == AgentType.Healthcare:
            labor = agent.expenses
            agent.cash(labor)
            agent.expenses = 0  # 重要：支付后清零医疗账单
        else:
            if agent.status != Status.Death and agent.infected_status == InfectionSeverity.Asymptomatic:
                # 调整失业救济金：只给30%生活费（而不是100%）
                # 这更符合现实的失业保险制度
                UNEMPLOYMENT_RELIEF_RATIO = 0.3
                labor = agent.expenses * UNEMPLOYMENT_RELIEF_RATIO
                agent.supply(labor)
                
                # ⚠️⚠️⚠️ 关键日志：政府救济金发放（非员工）
                try:
                    iteration = getattr(self.environment, 'iteration', -1)
                    day = iteration // 24 if iteration >= 0 else -1
                    hour = iteration % 24 if iteration >= 0 else -1
                    
                    import traceback
                    stack = traceback.extract_stack()
                    caller_info = []
                    for frame in stack[-5:-1]:  # 获取调用栈
                        caller_info.append(f"{frame.name}:{frame.lineno}")
                    
                    log_cashflow(iteration, day, hour,
                                f"🚨🚨🚨 WELFARE: {self.type.name}({str(self.id)[:8]}) pays {labor:.2f} "
                                f"to NON_EMPLOYEE Person({str(agent.id)[:8]}) "
                                f"| Call stack: {' <- '.join(caller_info)}")
                except:
                    pass

        # ✅ 优化：Business破产保护（允许有限负债）
        # Business可以负债经营，但有下限
        MIN_BUSINESS_WEALTH = -10000  # 最低财富下限 (约5%总财富)
        if self.wealth - labor < MIN_BUSINESS_WEALTH:
            # Business无法支付：Government兜底
            actual_payment = max(0, self.wealth - MIN_BUSINESS_WEALTH)
            deficit = labor - actual_payment
            self.cash(-actual_payment)
            if deficit > 0:
                self.environment.government.cash(-deficit)  # Government补贴
                
                # Log Government subsidy
                economic_logger.log_transaction(
                    iteration=getattr(self.environment, 'iteration', -1),
                    source_type="Government",
                    source_id=str(self.environment.government.id),
                    target_type=self.type.name,
                    target_id=str(self.id),
                    amount=deficit,
                    transaction_type="business_subsidy",
                    details={"reason": "Business cannot pay wages", "employee_id": str(agent.id)[:8]}
                )
        else:
            self.cash(-labor)

        return labor

    def supply(self, agent):
        """Incomes due to selling product/service"""
        if self.environment.callback('on_business_supply', self):
            return
        qty = np.random.randint(1, 10)
        if qty > self.stocks:
            qty = self.stocks
        # ✅ 优化：保持LLM系统原始公式，通过降低基础price来控制消费
        # 公式：price × (stratum+1) × qty
        # 优势：
        #   1. Q1不为0（修正原论文bug）
        #   2. 保留阶层差异（Q5是Q1的5倍）
        #   3. 通过降低base price（12→7）统一降价42%
        value = self.price * (agent.social_stratum + 1) * qty
        if agent.type == AgentType.Person:
            agent.demand(value)
        else:
            agent.cash(-value)
        self.cash(value)
        self.incomes += value
        self.stocks -= qty
        self.sales += qty

    def checkin(self, agent):
        """Employee is working"""

        if self.environment.callback('on_business_checkin', self):
            return

        if self.type == AgentType.Business:
            self.stocks += 1
            # 修复：删除hourly扣款（这是财富消失的根源）
            # 原代码：self.cash(-agent.expenses/720)
            # 问题：Business扣钱但Person没收钱 → 财富消失
            # 解决：完全删除hourly扣款，只在月底accounting()时通过demand()统一支付
            
        elif self.type == AgentType.Healthcare:
            # 调整医疗费率为日常开销的40%，使其更符合实际
            self.expenses += agent.expenses * 0.4

    def taxes(self):
        """Expenses due to employee payments"""
        tax = self.environment.government.price * self.num_employees + self.incomes/20
        self.environment.government.cash(tax)
        self.cash(-tax)
        return tax

    def accounting(self):
        """
        每月财务清算
        
        ⚠️ 注意: 只处理财务计算，不包含决策逻辑
        所有雇佣/解雇决策由LLM完成 (Business.decide)
        
        ✅ 恢复原系统工资支付逻辑（通过Business.demand()）
        """
        # 🛡️ 防御性代码：防止同一天内重复调用
        if not hasattr(self, '_last_accounting_day'):
            self._last_accounting_day = -999
        
        current_day = self.environment.iteration // 24
        if current_day == self._last_accounting_day:
            # 同一天内已经调用过，跳过
            try:
                iteration = self.environment.iteration
                day = iteration // 24
                hour = iteration % 24
                log_cashflow(iteration, day, hour,
                            f"⚠️ Business.accounting() BLOCKED (already called today) type={self.type.name} id={str(self.id)[:8]}")
            except:
                pass
            return
        
        self._last_accounting_day = current_day
        
        # ⚠️⚠️⚠️ 强制日志：追踪accounting()调用
        try:
            iteration = getattr(self.environment, 'iteration', -1)
            day = iteration // 24 if iteration >= 0 else -1
            hour = iteration % 24 if iteration >= 0 else -1
            log_cashflow(iteration, day, hour,
                        f"Business.accounting() CALLED type={self.type.name} id={str(self.id)[:8]}")
        except:
            pass
        
        if self.environment.callback('on_business_accounting', self):
            return 
        
        if self.type == AgentType.Business:
            # ✅ 恢复原系统逻辑：遍历所有员工，支付月工资
            labor = 0.0
            for person in self.employees:
                labor += self.demand(person)  # Business.demand()会正确支付工资
            
            # 缴税
            tax = self.taxes()
            
            # ✅ 删除Rule-based雇佣/解雇逻辑
            # 所有雇佣/解雇决策由Business的LLM决策完成
            # LLM会根据profit, employee count, epidemic等因素做出决策
            # 原来这里有：
            # if 2 * (labor + tax) < self.incomes: hire()
            # elif (labor + tax) > self.incomes: fire()
            
        elif self.type == AgentType.Healthcare:
            # Healthcare从Government获得预算
            self.environment.government.demand(self)
            
        elif self.type == AgentType.Government:
            # ========================================
            # 🔍 诊断日志：Government月度结算详细追踪
            # ========================================
            iteration = self.environment.iteration
            day = iteration // 24
            
            gov_wealth_before = self.wealth
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"\n{'='*80}")
                print(f"🏛️ Government月度结算 (Day {day}, Iteration {iteration})")
                print(f"{'='*80}")
                print(f"  政府财富（结算前）: {gov_wealth_before:,.2f}元 ({gov_wealth_before/self.environment.total_wealth*100:.4f}%)")
            
            # ① 医疗预算
            healthcare_expense_before_reset = self.environment.healthcare.expenses
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"\n  ① Healthcare医疗预算:")
                print(f"     Healthcare.expenses (before reset) = {healthcare_expense_before_reset:,.2f}元")
            
            # 记录Healthcare expenses值用于调试
            economic_logger.log_person_expenses(
                iteration=iteration,
                person_id=str(self.environment.healthcare.id),
                expenses=healthcare_expense_before_reset,
                social_stratum=-1,
                employed=False,
                has_house=False,
                context="Healthcare.expenses before Government.demand"
            )
            
            self.demand(self.environment.healthcare)
            gov_after_healthcare = self.wealth
            healthcare_cost = gov_wealth_before - gov_after_healthcare
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"     实际支付: {healthcare_cost:,.2f}元")
            
            # ② 无家可归者救济
            homeless = self.environment.get_homeless()
            homeless_expenses = []
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"\n  ② 无家可归者救济:")
                print(f"     人数: {len(homeless)}人")
                if homeless:
                    homeless_expenses = [p.expenses for p in homeless]
                    print(f"     平均expenses: {sum(homeless_expenses)/len(homeless):.2f}元")
                    print(f"     救济总额估算: {sum(homeless_expenses):,.2f}元")
                
                # 记录每个homeless的expenses
                for p in homeless:
                    economic_logger.log_person_expenses(
                        iteration=iteration,
                        person_id=str(p.id),
                        expenses=p.expenses,
                        social_stratum=p.social_stratum,
                        employed=False,
                        has_house=False,
                        context="Homeless relief recipient"
                    )
            
            gov_before_homeless = self.wealth
            for person in homeless:
                # 记录每笔支付前的详细信息
                person_wealth_before = person.wealth if person.house is None else person.house.wealth
                self.demand(person)
                person_wealth_after = person.wealth if person.house is None else person.house.wealth
                
                economic_logger.log_transaction(
                    iteration=iteration,
                    source_type="Government",
                    source_id=str(self.id),
                    target_type="Person",
                    target_id=str(person.id),
                    amount=person.expenses,
                    transaction_type="homeless_relief",
                    details={
                        "person_wealth_before": person_wealth_before,
                        "person_wealth_after": person_wealth_after,
                        "wealth_change": person_wealth_after - person_wealth_before,
                        "has_house": person.house is not None
                    }
                )
            homeless_cost = gov_before_homeless - self.wealth
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"     实际支付: {homeless_cost:,.2f}元")
            
            # ③ 失业救济（关键！）
            unemployed = self.environment.get_unemployed()
            unemployed_expenses = []
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"\n  ③ 失业救济（关键支出）:")
                print(f"     失业人数: {len(unemployed)}人 ({len(unemployed)/len(self.environment.population)*100:.1f}%)")
            
            if unemployed:
                unemployed_expenses = [p.expenses for p in unemployed]
                RELIEF_RATIO = 0.3  # 与demand()中保持一致
                if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                    print(f"     失业者expenses范围: {min(unemployed_expenses):,.2f} - {max(unemployed_expenses):,.2f}元")
                    print(f"     失业者平均expenses: {sum(unemployed_expenses)/len(unemployed_expenses):,.2f}元")
                    print(f"     救济金比例: {RELIEF_RATIO:.0%} (原expenses的30%)")
                    print(f"     失业救济总额估算: {sum(unemployed_expenses) * RELIEF_RATIO:,.2f}元")
                    
                    # 检查异常值
                    abnormal = [p for p in unemployed if p.expenses > 10000]
                    if abnormal:
                        print(f"     ⚠️ expenses>10000的异常失业者: {len(abnormal)}人")
                        for p in abnormal[:5]:
                            print(f"        Person {str(p.id)[:8]}: expenses={p.expenses:,.2f}, stratum=Q{p.social_stratum+1}")
                    
                    # 按阶层统计
                    by_stratum = {}
                    for p in unemployed:
                        s = p.social_stratum
                        if s not in by_stratum:
                            by_stratum[s] = []
                        by_stratum[s].append(p.expenses)
                    
                    print(f"     按阶层分布:")
                    for s in sorted(by_stratum.keys()):
                        count = len(by_stratum[s])
                        avg = sum(by_stratum[s]) / count
                        print(f"        Q{s+1}: {count}人, 平均expenses={avg:.2f}元")
                
                # 记录每个失业者的expenses
                for p in unemployed:
                    economic_logger.log_person_expenses(
                        iteration=iteration,
                        person_id=str(p.id),
                        expenses=p.expenses,
                        social_stratum=p.social_stratum,
                        employed=False,
                        has_house=p.house is not None,
                        context="Unemployed relief recipient"
                    )
            
            gov_before_unemployed = self.wealth
            for person in unemployed:
                # 记录每笔支付前后的详细信息
                person_wealth_before = person.wealth if person.house is None else person.house.wealth
                house_wealth_before = person.house.wealth if person.house else 0
                
                self.demand(person)
                
                person_wealth_after = person.wealth if person.house is None else person.house.wealth
                house_wealth_after = person.house.wealth if person.house else 0
                
                economic_logger.log_transaction(
                    iteration=iteration,
                    source_type="Government",
                    source_id=str(self.id),
                    target_type="Person",
                    target_id=str(person.id),
                    amount=person.expenses,
                    transaction_type="unemployment_relief",
                    details={
                        "person_wealth_before": person_wealth_before,
                        "person_wealth_after": person_wealth_after,
                        "wealth_change": person_wealth_after - person_wealth_before,
                        "has_house": person.house is not None,
                        "house_wealth_before": house_wealth_before,
                        "house_wealth_after": house_wealth_after,
                        "house_wealth_change": house_wealth_after - house_wealth_before
                    }
                )
            unemployed_cost = gov_before_unemployed - self.wealth
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"     实际支付: {unemployed_cost:,.2f}元")
            
            # 总结
            gov_wealth_after = self.wealth
            total_cost = gov_wealth_before - gov_wealth_after
            
            if os.environ.get('ENABLE_GOVERNMENT_DEBUG') == 'True':
                print(f"\n  📊 月度结算总结:")
                print(f"     Healthcare: {healthcare_cost:,.2f}元")
                print(f"     无家可归救济: {homeless_cost:,.2f}元")
                print(f"     失业救济: {unemployed_cost:,.2f}元")
                print(f"     总支出: {total_cost:,.2f}元 ({total_cost/self.environment.total_wealth*100:.4f}%)")
                print(f"     Government财富: {gov_wealth_before:,.2f} → {gov_wealth_after:,.2f}")
                print(f"     变化百分比: {(gov_wealth_after-gov_wealth_before)/self.environment.total_wealth*100:.4f}%")
                print(f"{'='*80}\n")
            
            # 记录详细的Government accounting
            economic_logger.log_government_accounting(
                iteration=iteration,
                gov_id=str(self.id),
                wealth_before=gov_wealth_before,
                wealth_after=gov_wealth_after,
                healthcare_expense=healthcare_expense_before_reset,
                healthcare_paid=healthcare_cost,
                unemployed_count=len(unemployed),
                unemployed_expenses=unemployed_expenses,
                unemployed_paid=unemployed_cost,
                homeless_count=len(homeless),
                homeless_expenses=homeless_expenses,
                homeless_paid=homeless_cost
            )

        # 重置月度统计
        self.incomes = 0
        self.sales = 0
        self.expenses = 0  # 重置expenses，避免医疗费用无限累积

        self.environment.callback('post_business_accounting', self)

    def update(self):
        if self.environment.callback('on_business_update', self):
            return 
        
        # ✨ 新增：主动招聘机制（每天凌晨0点检查）
        import random
        if hasattr(self, 'environment') and self.environment is not None:
            if self.environment.iteration % 24 == 0:  # 每天凌晨0点（与update调用时机一致）
                # 调试：确认进入了update方法
                if self.environment.iteration == 0 and os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                    print(f"[DEBUG Day 0] Business {self.id} update() called, open={self.open}")
                
                if not hasattr(self, 'initial_employees'):
                    self.initial_employees = 10  # 兜底默认值
                    if self.environment.iteration == 0 and os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                        print(f"[DEBUG Day 0] Business {self.id} using default initial_employees=10")
                
                employee_ratio = len(self.employees) / max(1, self.initial_employees)
                
                # 计算主动招聘概率（调整后的概率，各档位+10%）
                if employee_ratio < 0.5:
                    proactive_prob = 0.9  # 90%（原80%）- 严重缺人
                elif employee_ratio < 0.7:
                    proactive_prob = 0.6  # 60%（原50%）- 中度缺人
                elif employee_ratio < 0.9:
                    proactive_prob = 0.3  # 30%（原20%）- 轻度缺人
                else:
                    proactive_prob = 0.1  # 10%（原0%）- 接近满编也有小概率
                
                # 执行主动招聘
                if random.random() < proactive_prob and self.open:
                    # 使用标准的get_unemployed()，只招聘Asymptomatic失业者
                    unemployed = self.environment.get_unemployed()
                    
                    # 调试：输出失业者数量
                    if self.environment.iteration == 0 and os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                        print(f"[DEBUG Day 0] Business {self.id}: Found {len(unemployed)} unemployed persons (Asymptomatic only)")
                    
                    if unemployed:
                        # 随机选择一个失业者尝试雇佣
                        candidate = random.choice(unemployed)
                        success = self.hire(candidate)
                        
                        # 记录日志（根据debug设置）
                        if success and os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                            print(f"[Day {self.environment.iteration//24}] Business {self.id} proactively hired Person {candidate.id} (ratio={employee_ratio:.1%}, prob={proactive_prob:.0%})")
                        elif self.environment.iteration == 0 and os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                            print(f"[DEBUG Day 0] Business {self.id}: hire() failed for Person {candidate.id}")
                    else:
                        # 调试：没有失业者
                        if self.environment.iteration == 0:  # 只在第一天输出一次
                            if os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                                print(f"[DEBUG Day 0] Business {self.id}: No unemployed persons available for hiring")
                else:
                    # 调试：为什么没有执行招聘
                    if self.environment.iteration == 0:  # 只在第一天输出一次
                        if not self.open:
                            print(f"[Day 0] Business {self.id}: Closed, cannot hire")
                        else:
                            if os.environ.get('ENABLE_HIRING_DEBUG') == 'True':
                                print(f"[Day {self.environment.iteration//24}] Business {self.id}: Hiring probability check failed (prob={proactive_prob:.0%})")
        
        if self.type != AgentType.Government:
            # ✅ 支持经济开放度调节
            # 根据economy_openness参数动态分配资金流向：
            # - 税收（固定1/3）
            # - B2B交易 = (1 - openness) × 2/3
            # - 流出国外 = openness × 2/3
            
            self.cash(-self.fixed_expenses)  # 扣除全部运营成本
            
            # 1. 税收（固定1/3，不受开放度影响）
            tax = self.fixed_expenses / 3
            self.environment.government.cash(tax)
            
            # 2. B2B交易部分 = (1 - openness) × 2/3
            # openness=0.0 (封闭) → 67% B2B
            # openness=1.0 (开放) → 0% B2B
            # ✅ 性能优化：使用预计算的比例
            b2b_ratio = self.environment._business_b2b_ratio
            if b2b_ratio > 0 and len(self.environment.business) > 1:
                # 分配给2个随机Business（模拟供应链内循环）
                # ✅ 边界检查：至少需要2个Business（自己+其他）
                for _ in range(2):
                    ix = np.random.randint(0, len(self.environment.business))
                bus = self.environment.business[ix]
                if bus.id != self.id:
                        bus.cash(self.fixed_expenses * b2b_ratio / 2)
            
            # 3. 流出国外部分 = openness × 2/3（自动流失，无需显式代码）
            
            # 🏭 库存生产机制（新增）
            # Person工作 → Business生产库存
            # 设计理念：员工工作产生商品/服务，补充库存
            if self.type == AgentType.Business:
                # 统计正在工作的员工（活着且无症状）
                working_employees = [
                    emp for emp in self.employees
                    if emp.status != Status.Death 
                    and emp.infected_status == InfectionSeverity.Asymptomatic
                ]
                
                # 生产率：每个员工每小时生产1.5个单位（随机1-2）
                # 这样10个员工每天可以生产：10 × 24 × 1.5 = 360个单位
                # 远超过正常购物消耗（每天约3-5次购物 × 5个单位 = 15-25个单位）
                if len(working_employees) > 0:
                    production_per_worker = np.random.uniform(1.0, 2.0)
                    total_production = len(working_employees) * production_per_worker
                    self.stocks += total_production
                    
                    # 库存上限：避免无限累积（设置为500个单位）
                    MAX_STOCKS = 500
                    if self.stocks > MAX_STOCKS:
                        self.stocks = MAX_STOCKS
            
        else:
            # Government.update()不再包含自动采购行为
            # 公共采购由LLM决策完成（通过PublicProcurementAction）
            pass

        self.environment.callback('post_business_update', self)
    
    # ==================== LLM Decision Methods (Business) ====================
    
    def should_decide(self, current_iteration):
        """
        判断是否需要进行LLM决策 (Business版本)
        
        Business决策频率: 每天决策一次 (与update同步)
        
        Args:
            current_iteration: 当前迭代次数
            
        Returns:
            bool: 是否需要决策
        """
        if not hasattr(self, 'last_decision_time'):
            self.last_decision_time = -999
        
        if not hasattr(self, 'decision_interval'):
            # Business: 每天决策一次 (24小时)
            self.decision_interval = 24
        
        # 检查是否到了决策时间
        return (current_iteration - self.last_decision_time) >= self.decision_interval
    
    def decide(self, status_pool):
        """
        使用LLM进行Business决策
        
        Args:
            status_pool: GraphStatusPool实例
            
        Returns:
            dict: 决策结果 {action, reasoning, params}
            
        Raises:
            RuntimeError: LLM决策失败时抛出异常
        """
        if not hasattr(self, 'backend') or self.backend is None:
            raise RuntimeError(
                f"Business {self.id} has no LLM backend configured. "
                "Cannot make LLM decision."
            )
        
        # 获取决策上下文
        context = status_pool.get_business_context(self)
        
        # 获取Action Registry (GraphSimulation Business)
        from covid_abs.llm.actions import get_action_registry
        action_registry = get_action_registry(register_graph_actions=True)
        
        # 构建LLM Prompt
        prompt = self._build_decision_prompt(context, action_registry)
        
        try:
            # 调用LLM（backend会自动处理重试，包括TPM限制、网络错误等）
            response = self.backend.query(prompt, temperature=0.7)
            
            # 解析LLM响应
            decision = self._parse_llm_response(response, action_registry)
            
            return decision
            
        except Exception as e:
            # Backend的所有重试都失败了，使用Fallback决策
            print(f"[FALLBACK WARNING] Business {self.id} at iteration {context['time']['iteration']}")
            print(f"   Reason: {str(e)[:200]}")
            print(f"   Using rule-based fallback decision")
            
            # 获取fallback决策并标记
            fallback_decision = self._get_business_fallback_decision(context)
            fallback_decision['is_fallback'] = True
            fallback_decision['fallback_reason'] = str(e)[:200]
            
            return fallback_decision
    
    def _get_business_fallback_decision(self, context):
        """
        提供Business的Fallback决策（当LLM调用失败时使用）
        
        使用基于规则的简单逻辑
        """
        # 🔧 FIX: 兼容新旧context结构 (business_info vs financial)
        financial = context.get('business_info', context.get('financial', {}))
        time_ctx = context['time']
        current_hour = time_ctx['hour']
        
        # 规则1：营业时间（8-22点）+ 财务健康 → 开门营业
        # 🔧 FIX: 添加.get()保护，防止wealth缺失
        wealth = financial.get('wealth', 0)
        if 8 <= current_hour < 22 and wealth > 0:
            return {
                'action': 'OpenBusinessAction',
                'reasoning': 'Business hours and financially stable, staying open (fallback decision)',
                'params': {}
            }
        
        # 规则2：非营业时间或财务困难 → 关闭
        return {
            'action': 'CloseBusinessAction',
            'reasoning': 'Outside business hours or financial difficulties (fallback decision)',
            'params': {}
        }
    
    def _format_policy_for_business(self, policy):
        """Format government policy information for Business prompt."""
        policy_lines = []
        if policy.get('stay_home_order', False):
            policy_lines.append("- Stay-at-home order ACTIVE: Reduced customer traffic expected")
        if policy.get('borders_closed', False):
            policy_lines.append("- Border controls: Closed (may affect supply chain)")
        
        return "\n".join(policy_lines) if policy_lines else "- No special restrictions currently in effect"
    
    def _build_decision_prompt(self, context, action_registry, available_actions=None):
        """
        Build LLM decision prompt for Business agents.
        
        Args:
            context: Context returned by get_business_context
            action_registry: ActionRegistry instance
            available_actions: Optional list of action names
            
        Returns:
            str: Prompt text
        """
        basic_info = context['business_info']
        performance = context['performance']
        market = context['market']
        epidemic = context['epidemic']
        economic = context['economic']
        time_ctx = context['time']
        
        # Stratum names
        stratum_names = ['Poverty Level', 'Low Income', 'Middle Class', 'Affluent', 'Wealthy']
        stratum_idx = min(max(0, basic_info['social_stratum']), 4)
        stratum_name = stratum_names[stratum_idx]
        
        # Business performance description
        if performance['profit'] > 0:
            profit_desc = f"Profitable: +{performance['profit']:.1f} (margin {performance['profit_rate']*100:.1f}%)"
        else:
            profit_desc = f"Loss: {performance['profit']:.1f} (margin {performance['profit_rate']*100:.1f}%)"
        
        # Inventory description
        if basic_info['stocks'] < 5:
            stock_desc = f"Low inventory: {basic_info['stocks']}"
        else:
            stock_desc = f"Sufficient inventory: {basic_info['stocks']}"
        
        # Employee description and infection rate analysis
        total_employees = basic_info['num_employees']
        infected_employees = performance['infected_employees']
        if total_employees > 0:
            infection_rate_staff = infected_employees / total_employees
            healthy_employees = total_employees - infected_employees
            employee_desc = f"{total_employees} people ({infected_employees} infected = {infection_rate_staff*100:.1f}% infection rate)"
            
            # 🔧 量化的运营能力评估
            if infection_rate_staff < 0.20:
                capacity_assessment = f"Full capacity - {healthy_employees}/{total_employees} staff available ({(1-infection_rate_staff)*100:.1f}%)"
                operation_recommendation = "Strong workforce → Maintain full operations"
            elif infection_rate_staff < 0.50:
                capacity_assessment = f"Reduced capacity - {healthy_employees}/{total_employees} staff available ({(1-infection_rate_staff)*100:.1f}%)"
                operation_recommendation = "Moderate workforce → Can operate, consider reducing hours if needed"
            elif infection_rate_staff < 0.80:
                capacity_assessment = f"Limited capacity - {healthy_employees}/{total_employees} staff available ({(1-infection_rate_staff)*100:.1f}%)"
                operation_recommendation = "Weak workforce → Difficult to operate normally, consider capacity reduction or temporary closure"
            else:
                capacity_assessment = f"Critical shortage - {healthy_employees}/{total_employees} staff available ({(1-infection_rate_staff)*100:.1f}%)"
                operation_recommendation = "Severe workforce shortage → Weigh closure trade-offs against financial situation"
        else:
            employee_desc = "No employees"
            capacity_assessment = "No workforce"
            operation_recommendation = "Need to hire employees to operate"
        
        # 关闭成本分析
        daily_cost = basic_info.get('fixed_expenses', 0) / 30
        daily_revenue_avg = basic_info.get('sales', 0) * basic_info.get('price', 1.0) / 30
        closure_impact = f"""CAPACITY: {capacity_assessment}
REVENUE: Daily avg ${daily_revenue_avg:.0f}, Fixed costs ${daily_cost:.0f}/day
NOTE: Closing stops revenue but costs continue."""
        
        # ========================================================================
        # Available Actions (根据当前状态直接构建正确的动作列表)
        # ========================================================================
        # 设计原则：
        # 1. 根据Business状态直接构建可执行的动作列表
        # 2. LLM只看到真正可以执行的动作
        # 3. 避免"先创建再删除"的模式，从源头保证列表正确性
        # ========================================================================
        
        if not basic_info['open']:
            # Business已关闭：只能重开或维持关闭
            business_actions = [
                "ReopenBusinessAction",
                "MaintainOperationAction"
            ]
        else:
            # Business营业中：根据员工数量决定可用动作
            business_actions = [
                "HireEmployeeAction",      # 总是可以雇人
                "AdjustPriceAction",       # 总是可以调价
                "MaintainOperationAction", # 总是可以维持
                "CloseBusinessAction"      # 总是可以关闭
            ]
            
            # ✅ 只在有员工时才能解雇
            if basic_info['num_employees'] > 0:
                # 插入到HireEmployeeAction之后，保持逻辑顺序
                business_actions.insert(1, "FireEmployeeAction")
        
        # Get action descriptions
        action_list = action_registry.get_action_list_for_prompt(business_actions)
        
        # Build optimized prompt
        prompt = f"""[COMPUTATIONAL SIMULATION - RESEARCH ONLY]
This is a virtual business entity in a computer-based epidemic simulation model for academic research.
NOT providing advice to real businesses. For research purposes only.

SIMULATED BUSINESS PROFILE: {stratum_name} business owner

BUSINESS STATUS:
- Operations: {"OPEN" if basic_info['open'] else "CLOSED"}
- Financial: Cash ${basic_info['wealth']:.0f}, {profit_desc}
- Inventory: {stock_desc}, Sales: {basic_info['sales']} units
- Workforce: {employee_desc}
- Price: ${basic_info['price']:.1f}/unit

{closure_impact}

MARKET:
- Competitors: {market['competitor_count']} targeting same segment
- Customer base: {market['customer_pool_size']} people
- Economy: {economic['unemployment_rate']*100:.1f}% unemployment, {economic['business_open_rate']*100:.1f}% businesses open

EPIDEMIC: {epidemic['infected_rate']*100:.1f}% infected, {epidemic['healthcare_load']*100:.1f}% hospital load

POLICIES:
{self._format_policy_for_business(context.get('policy', {}))}

TIME: Day {time_ctx['day']}, Hour {time_ctx['hour']}

OPERATING HOURS: Stores operate 08:00-22:00. Night (22-08) = automatically closed.

ACTIONS:
{action_list}

CONTEXT:
1. Workforce: Higher staff infection → harder to operate normally. <50% infected = full capacity; >80% = limited capacity.
2. Demand: High infection rates or stay-home orders typically reduce customer traffic.
3. Costs: Fixed costs continue regardless of open/closed status. Closing stops revenue.

JSON (reasoning: 1-2 sentences, keep it simple and concise, <120 words):
{{"action": "ActionName", "reasoning": "brief reason", "params": {{}}}}"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, action_registry) -> dict:
        """
        Parse LLM response (Business version, shares logic with Person).
        
        Args:
            response: Text returned by LLM
            action_registry: ActionRegistry instance
            
        Returns:
            dict: {action, reasoning, params}
            
        Raises:
            ValueError: 解析失败
        """
        import json
        
        # 尝试直接解析(如果整个响应就是JSON)
        try:
            decision = json.loads(response)
            if 'action' in decision:
                # 设置默认值
                if 'reasoning' not in decision:
                    decision['reasoning'] = "No reasoning provided"
                if 'params' not in decision:
                    decision['params'] = {}
                return decision
        except json.JSONDecodeError:
            pass
        
        # 使用共享的智能JSON提取函数
        json_str = extract_json_from_llm_response(response)
        
        if not json_str:
            raise ValueError(f"Cannot find valid JSON in LLM response: {response}")
        
        try:
            decision = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {json_str}") from e
        
        # 验证必需字段
        if 'action' not in decision:
            raise ValueError(f"Missing 'action' field in decision: {decision}")
        
        # 设置默认值
        if 'reasoning' not in decision:
            decision['reasoning'] = "No reasoning provided"
        if 'params' not in decision:
            decision['params'] = {}
        
        return decision
    
    # ==================== Government专用LLM决策方法 ====================    # ==================== Government专用LLM决策方法 ====================
    
    def should_decide_as_government(self, current_iteration):
        """
        判断Government是否需要进行LLM决策
        
        Government决策频率: 优先读取scenario_config，默认168小时(7天)
        
        Args:
            current_iteration: 当前迭代次数
            
        Returns:
            bool: 是否需要决策
        """
        if not hasattr(self, 'last_gov_decision_time'):
            self.last_gov_decision_time = -999
        
        if not hasattr(self, 'gov_decision_interval'):
            # 优先从environment的scenario_config中获取配置
            if hasattr(self, 'environment') and hasattr(self.environment, 'scenario_config'):
                self.gov_decision_interval = self.environment.scenario_config.get('government_decision_interval', 168)
            else:
                # 默认: 每周决策一次 (7天 * 24小时)
                self.gov_decision_interval = 168
        
        # 检查是否到了决策时间
        return (current_iteration - self.last_gov_decision_time) >= self.gov_decision_interval
    
    def decide_as_government(self, status_pool):
        """
        使用LLM进行Government决策
        
        Args:
            status_pool: GraphStatusPool实例
            
        Returns:
            dict: 决策结果 {action, reasoning, params}
            
        Raises:
            RuntimeError: LLM决策失败时抛出异常
        """
        if not hasattr(self, 'backend') or self.backend is None:
            raise RuntimeError(
                f"Government has no LLM backend configured. "
                "Cannot make LLM decision."
            )
        
        # 获取决策上下文
        context = status_pool.get_government_context()
        
        # 获取Action Registry (GraphSimulation Government)
        from covid_abs.llm.actions import get_action_registry
        action_registry = get_action_registry(register_graph_actions=True)
        
        # 构建LLM Prompt
        prompt = self._build_government_prompt(context, action_registry)
        
        try:
            # 调用LLM（backend会自动处理重试，包括TPM限制、网络错误等）
            response = self.backend.query(prompt, temperature=0.7)
            
            # 解析LLM响应
            decision = self._parse_llm_response(response, action_registry)
            
            return decision
            
        except Exception as e:
            # Backend的所有重试都失败了，使用Fallback决策
            print(f"[FALLBACK WARNING] Government at iteration {context['time']['iteration']}")
            print(f"   Reason: {str(e)[:200]}")
            print(f"   Using rule-based fallback decision")
            
            # 获取fallback决策并标记
            fallback_decision = self._get_government_fallback_decision(context)
            fallback_decision['is_fallback'] = True
            fallback_decision['fallback_reason'] = str(e)[:200]
            
            return fallback_decision
    
    def _get_government_fallback_decision(self, context):
        """
        提供Government的Fallback决策（当LLM调用失败时使用）
        
        使用基于规则的简单逻辑
        """
        # 🔧 [FIX] 使用正确的键名 'epidemic_trend' 而不是 'epidemic'
        epidemic_trend = context.get('epidemic_trend', {})
        infection_rate = epidemic_trend.get('infection_rate', 0.0)
        
        # 规则1：感染率>10% → 启动禁足令
        if infection_rate > 0.10:
            return {
                'action': 'UpdatePolicyAction',
                'reasoning': 'High infection rate, implementing stay-home order (fallback decision)',
                'params': {
                    'stay_home_order': True,
                    'borders_closed': True
                }
            }
        
        # 规则2：感染率>5% → 关闭边境
        elif infection_rate > 0.05:
            return {
                'action': 'UpdatePolicyAction',
                'reasoning': 'Moderate infection rate, closing borders (fallback decision)',
                'params': {
                    'stay_home_order': False,
                    'borders_closed': True
                }
            }
        
        # 规则3：感染率<2% → 放松限制
        else:
            return {
                'action': 'UpdatePolicyAction',
                'reasoning': 'Low infection rate, relaxing restrictions (fallback decision)',
                'params': {
                    'stay_home_order': False,
                    'borders_closed': False
                }
            }
    
    def _build_government_prompt(self, context, action_registry):
        """
        Build Government LLM decision prompt.
        
        Args:
            context: Context returned by get_government_context
            action_registry: ActionRegistry instance
            
        Returns:
            str: Prompt text
        """
        epidemic = context['epidemic_trend']
        economic = context['economic_state']
        policy = context['current_policy']
        time_ctx = context['time']
        
        # Epidemic description
        if epidemic['infection_rate'] > 0.2:
            epidemic_desc = f"Severe epidemic: Infection rate {epidemic['infection_rate']*100:.1f}%, Deaths {epidemic['total_deaths']}"
        elif epidemic['infection_rate'] > 0.05:
            epidemic_desc = f"Epidemic under control: Infection rate {epidemic['infection_rate']*100:.1f}%, Deaths {epidemic['total_deaths']}"
        else:
            epidemic_desc = f"Mild epidemic: Infection rate {epidemic['infection_rate']*100:.1f}%, Deaths {epidemic['total_deaths']}"
        
        # Economic description
        if economic['unemployment_rate'] > 0.3:
            economic_desc = f"Economic recession: Unemployment {economic['unemployment_rate']*100:.1f}%, {economic['closed_business']} businesses closed"
        elif economic['unemployment_rate'] > 0.15:
            economic_desc = f"Economic pressure: Unemployment {economic['unemployment_rate']*100:.1f}%, {economic['closed_business']} businesses closed"
        else:
            economic_desc = f"Healthy economy: Unemployment {economic['unemployment_rate']*100:.1f}%, {economic['closed_business']} businesses closed"
        
        # Fiscal description
        fiscal_ratio = economic['fiscal_sustainability']
        if fiscal_ratio < 0.05:
            fiscal_desc = f"Fiscal strain: Only {economic['government_wealth']:.0f} remaining ({fiscal_ratio*100:.1f}% of total wealth)"
        else:
            fiscal_desc = f"Sufficient fiscal reserves: {economic['government_wealth']:.0f} ({fiscal_ratio*100:.1f}% of total wealth)"
        
        # ========================================================================
        # Available Actions (使用StatusPool过滤后的动作列表)
        # ========================================================================
        # 重要修复：必须使用StatusPool.get_available_actions_for_agent()
        # 这样才能确保场景配置（如baseline禁用封锁）被正确应用
        # ========================================================================
        
        # 从StatusPool获取该政府在当前场景下允许的动作
        from covid_abs.llm.graph_message import GraphStatusPool
        if hasattr(self.environment, 'status_pool') and isinstance(self.environment.status_pool, GraphStatusPool):
            government_actions = self.environment.status_pool.get_available_actions_for_agent(self)
        else:
            # Fallback：如果StatusPool不可用，使用最小动作集
            government_actions = ["AdjustTaxRateAction", "MaintainPolicyAction"]
            print("[WARNING] StatusPool not available for Government, using minimal action set")
        
        # Get action descriptions
        action_list = action_registry.get_action_list_for_prompt(government_actions)
        
        # Calculate week number
        week = time_ctx['day'] // 7 + 1
        day_in_week = time_ctx['day'] % 7 + 1
        
        # Build optimized prompt
        prompt = f"""[COMPUTATIONAL SIMULATION - RESEARCH ONLY]
This is a virtual government entity in a computer-based epidemic simulation model for academic research.
NOT providing policy advice to real governments. For research purposes only.

SIMULATED GOVERNMENT AGENT: Making policy decisions in virtual environment

EPIDEMIC: {epidemic_desc}, Healthcare {epidemic['healthcare_load']*100:.1f}% utilized, Trend: {epidemic['trend']}

ECONOMY: {economic_desc}, Q1 wealth {economic['Q1_wealth']*100:.2f}%, Govt finances: {fiscal_desc}

CURRENT POLICY:
- Stay-home: {"ACTIVE" if policy.get('stay_home_order', False) else "INACTIVE"}
- Borders: {"CLOSED" if policy.get('borders_closed', False) else "OPEN"}
- Tax rate: {self.price:.2f}

TIME: Week {week}, Day {day_in_week} (Total Day {time_ctx['day']})

ACTIONS:
{action_list}

CONTEXT:
1. Government responsibility: Public health protection and epidemic control are core duties. High infection rates threaten:
   - Population mortality risk (even if current deaths are low, severe cases may surge)
   - Healthcare system capacity (sudden overload leads to treatment delays)
   - Economic productivity (widespread illness reduces workforce)
   - Social stability and public confidence
   Consider both health protection and economic sustainability when deciding interventions.
2. Economic stress: High unemployment typically calls for economic support measures.
3. Fiscal balance: Low reserves require careful spending. Tax adjustments affect revenue.
4. Policy trade-offs: Health measures may impact economy short-term but prevent worse long-term damage; premature reopening may cause epidemic rebound.

JSON (reasoning: 1-2 sentences, keep it simple and concise, <120 words):
{{"action": "ActionName", "reasoning": "brief reason", "params": {{}}}}"""
        
        return prompt


class House(Agent):
    """
    The container of Agent's attributes and status
    """

    def __init__(self, **kwargs):
        super(House, self).__init__(**kwargs)
        self.homemates = []
        self.type = AgentType.House
        self.size = 0
        self.incomes = 0
        self.expenses = 0
        self.fixed_expenses = kwargs.get('fixed_expenses',0.0)
        self.type == AgentType.House

    def append_mate(self, agent):
        """
        将Person加入House并转移财富
        
        设计逻辑:
        - Person的财富转移给House统一管理
        - 转移后Person.wealth清零（避免重复统计）
        - Homeless的Person不调用此方法，保留个人财富
        """
        self.homemates.append(agent)
        self.wealth += agent.wealth
        agent.wealth = 0  # ✅ 修复财富重复统计：转移后清零个人账户
        self.size += 1
        agent.house = self
        x, y = np.random.normal(0.0, 0.25, 2)
        agent.x = int(self.x + x)
        agent.y = int(self.y + y)
        # ✅ [FIX] 修复24倍开销Bug
        # 问题: (expenses / 720) * 24 = expenses / 30 (日度开销)
        #      但House.update()每小时调用一次 → 实际月开销 = expenses * 24
        # 修复: 改为小时开销 = expenses / 720
        # 结果: 月开销 = (expenses / 720) * 720 = expenses ✓
        self.fixed_expenses += agent.expenses / 720  # 每小时开销

    def remove_mate(self, agent):
        # 🔒 [健壮性] 确保agent在homemates列表中，否则静默拒绝
        if agent not in self.homemates:
            # 不执行remove操作，数据保持一致
            return
        
        self.homemates.remove(agent)
        self.wealth -= agent.wealth/2
        self.size -= 1
        # ✅ [FIX] 同步修复24倍开销Bug
        self.fixed_expenses -= agent.expenses / 720  # 每小时开销

    def checkin(self, agent):
        if self.environment.callback('on_house_checkin', self):
            return
        # ✅ 优化：完全移除hourly扣款，避免与House.update()重复
        # 原逻辑：每小时扣agent.expenses/720 → 过度消耗
        # House.update()已经扣除fixed_expenses（= agent.expenses/30），无需重复
        # 新逻辑：checkin()不再扣款，只记录回家事件
        pass

        self.environment.callback('post_house_checkin', self)

    def demand(self, value = 0.0):
        """Expense of consuming product/services"""
        if self.environment.callback('on_house_demand', self):
            return
        
        old_wealth = self.wealth
        
        # ✅ 优化：破产保护，财富不能低于0
        if self.wealth - value < 0:
            # 破产：Government兜底（提供最低生活保障）
            deficit = abs(self.wealth - value)
            self.environment.government.cash(-deficit)  # Government支出救济金
            self.wealth = 0  # House财富设为0（破产状态）
            self.expenses += value  # 仍记录expenses
            
            # 记录破产保护
            if deficit > 0:
                try:
                    iteration = getattr(self.environment, 'iteration', -1)
                    day = iteration // 24 if iteration >= 0 else -1
                    hour = iteration % 24 if iteration >= 0 else -1
                    log_wealth_change(iteration, day, hour, "House", str(self.id), 
                                    old_wealth, self.wealth, "House.demand(bankruptcy)", 
                                    f"value={value:.2f} deficit={deficit:.2f} Gov_rescue")
                except:
                    pass
        else:
            self.wealth -= value
            self.expenses += value
            
            # 记录正常支出
            if value > 0:
                try:
                    iteration = getattr(self.environment, 'iteration', -1)
                    day = iteration // 24 if iteration >= 0 else -1
                    hour = iteration % 24 if iteration >= 0 else -1
                    log_wealth_change(iteration, day, hour, "House", str(self.id), 
                                    old_wealth, self.wealth, "House.demand", 
                                    f"value={value:.2f} expenses_now={self.expenses:.2f}")
                except:
                    pass
        
        self.environment.callback('post_house_demand', self)

    def supply(self, value = 0.0):
        """Income of work"""
        # 无条件日志测试
        try:
            iteration = getattr(self.environment, 'iteration', -1)
            day = iteration // 24 if iteration >= 0 else -1
            hour = iteration % 24 if iteration >= 0 else -1
            log_cashflow(iteration, day, hour,
                        f" House.supply() CALLED value={value:.2f} house_id={str(self.id)[:8]}")
        except:
            pass
        
        if self.environment.callback('on_house_supply', self):
            return
        
        old_wealth = self.wealth
        
        # 调试日志：记录House收入（详细追踪）
        if value > 0 and hasattr(self, 'environment'):
            try:
                iteration = getattr(self.environment, 'iteration', -1)
                day = iteration // 24 if iteration >= 0 else -1
                hour = iteration % 24 if iteration >= 0 else -1
                
                log_cashflow(iteration, day, hour,
                            f"House.supply({value:.2f}) house_id={str(self.id)[:8]} "
                            f"wealth_before={old_wealth:.2f}")
            except:
                pass
        
        self.wealth += value
        self.incomes += value
        
        # Log economic transaction
        if value != 0:
            economic_logger.log_transaction(
                iteration=getattr(self.environment, 'iteration', -1),
                source_type="External",
                source_id="",
                target_type="House",
                target_id=str(self.id),
                amount=value,
                transaction_type="house_income",
                details={
                    "old_wealth": old_wealth,
                    "new_wealth": self.wealth,
                    "incomes_total": self.incomes
                }
            )
        
        # 调试日志：记录House财富变化（增强追踪）
        if value != 0 and hasattr(self, 'environment'):
            try:
                iteration = getattr(self.environment, 'iteration', -1)
                day = iteration // 24 if iteration >= 0 else -1
                hour = iteration % 24 if iteration >= 0 else -1
                
                log_wealth_change(iteration, day, hour, "House", str(self.id),
                                old_wealth, self.wealth, "House.supply",
                                f"value={value:.2f} incomes_total={self.incomes:.2f}")
            except:
                pass

        self.environment.callback('post_house_supply', self)

    def accounting(self):
        # 🛡️ 防御性代码：防止同一天内重复调用
        if not hasattr(self, '_last_accounting_day'):
            self._last_accounting_day = -999
        
        current_day = self.environment.iteration // 24
        if current_day == self._last_accounting_day:
            # 同一天内已经调用过，跳过
            try:
                iteration = self.environment.iteration
                day = iteration // 24
                hour = iteration % 24
                log_cashflow(iteration, day, hour,
                            f"⚠️ House.accounting() BLOCKED (already called today) house_id={str(self.id)[:8]}")
            except:
                pass
            return
        
        self._last_accounting_day = current_day
        
        if self.environment.callback('on_house_accounting', self):
            return 
        
        """
        Monthly financial settlement for House
        
        ✅ P0修复：税收公式改为基于incomes（所得税模型）
        原公式（基于expenses）：tax = government.price × homemates + expenses/10
        - 问题：29天累积的巨大expenses导致税收爆炸（LLM系统中expenses可达40万+）
        - 结果：工资日税收>工资，导致Person GDP异常下降
        
        新公式（基于incomes）：tax = government.price × homemates + incomes/10
        - 优点：税收稳定，与月度结算机制完美适配
        - 结果：工资日恢复正常（收入>税收）
        - 经济学依据：个人所得税模型（10%税率）
        """
        # 人头税 + 所得税（10%）
        tax = self.environment.government.price * len(self.homemates) + self.incomes/10
        
        old_wealth = self.wealth
        
        # ✅ P1修复：添加破产保护
        if self.wealth >= tax:
            self.environment.government.cash(tax)
            self.wealth -= tax
            
            # 记录正常税收
            try:
                iteration = self.environment.iteration
                day = iteration // 24
                hour = iteration % 24
                log_wealth_change(iteration, day, hour, "House", str(self.id), 
                                old_wealth, self.wealth, "House.accounting(tax)", 
                                f"tax={tax:.2f} incomes={self.incomes:.2f} homemates={len(self.homemates)}")
            except:
                pass
        else:
            # 只支付能支付的部分，避免House出现负wealth
            actual_tax = max(0, self.wealth)
            self.environment.government.cash(actual_tax)
            self.wealth = 0
            
            # 记录破产税收
            try:
                iteration = self.environment.iteration
                day = iteration // 24
                hour = iteration % 24
                log_wealth_change(iteration, day, hour, "House", str(self.id), 
                                old_wealth, self.wealth, "House.accounting(tax_bankruptcy)", 
                                f"tax_full={tax:.2f} tax_paid={actual_tax:.2f} shortfall={tax-actual_tax:.2f}")
            except:
                pass
        
        # 重置月度统计
        old_incomes = self.incomes
        old_expenses = self.expenses
        self.incomes = 0
        self.expenses = 0
        
        # 记录月度结算
        try:
            iteration = self.environment.iteration
            day = iteration // 24
            hour = iteration % 24
            log_cashflow(iteration, day, hour,
                        f"✅ House.accounting() COMPLETE house_id={str(self.id)[:8]} "
                        f"tax={tax:.2f} reset: incomes={old_incomes:.2f}→0 expenses={old_expenses:.2f}→0")
        except:
            pass

        self.environment.callback('post_house_accounting', self)

    def update(self):
        if self.environment.callback('on_house_update', self):
            return 
        
        # ✅ 支持经济开放度调节
        # 根据economy_openness参数动态分配资金流向：
        # - 税收（固定10%）
        # - 本地循环 = (1 - openness) × 90%
        # - 流出国外 = openness × 90%
        
        if self.wealth >= self.fixed_expenses:
            # House有足够财富，正常支出
            self.wealth -= self.fixed_expenses  # 扣除全部开销
            
            # 1. 税收（固定10%，不受开放度影响）
            tax = self.fixed_expenses * 0.1
            self.environment.government.cash(tax)
            
            # 2. 本地循环部分 = (1 - openness) × 90%
            # openness=0.0 (封闭) → 90%本地循环
            # openness=1.0 (开放) → 0%本地循环
            # ✅ 性能优化：使用预计算的比例
            local_ratio = self.environment._house_local_ratio
            if local_ratio > 0 and len(self.environment.business) > 0:
                # 分配给5个随机Business（模拟本地消费）
                # ✅ 边界检查：确保Business数量 > 0
                for _ in range(5):
                    ix = np.random.randint(0, len(self.environment.business))
                    self.environment.business[ix].cash(self.fixed_expenses * local_ratio / 5)
            
            # 3. 流出国外部分 = openness × 90%（自动流失，无需显式代码）
            
        else:
            # House破产，只能支出剩余财富
            actual_expense = self.wealth
            self.wealth = 0
            
            # 破产时也按比例分配
            tax = actual_expense * 0.1
            self.environment.government.cash(tax)
            
            # ✅ 性能优化：使用预计算的比例
            local_ratio = self.environment._house_local_ratio
            if local_ratio > 0 and len(self.environment.business) > 0:
                # ✅ 边界检查：确保Business数量 > 0
                for _ in range(5):
                    ix = np.random.randint(0, len(self.environment.business))
                    self.environment.business[ix].cash(actual_expense * local_ratio / 5)

        self.environment.callback('post_house_update', self)


class Person(Agent):
    """
    The container of Agent's attributes and status
    """

    def __init__(self, **kwargs):
        super(Person, self).__init__(**kwargs)
        self.employer = kwargs.get("employer", None)
        self.house = kwargs.get("house", None)
        self.type = AgentType.Person
        self.economical_status = EconomicalStatus.Inactive
        self.incomes = kwargs.get("income", 0.0)
        self.expenses = kwargs.get("expense", 0.0)
        
        # 🛒 购物计时器 - 追踪上次购物时间
        self.last_shopping_time = -999  # 初始化为很久以前（确保第一次会提示需要购物）
        '''上次购物的iteration（-999表示从未购物）'''
        
        # 🛒 购物失败追踪 - 记录上次购物失败的时间和原因
        self.last_failed_shopping = -999  # 上次购物失败的iteration
        self.shopping_failure_reason = None  # 失败原因："no_inventory", "no_business", "no_money"
        '''购物失败追踪，用于调整后续决策'''

        if self.age > 16 and self.age <= 65:
            self.economical_status = EconomicalStatus.Active

    def _get_fallback_decision(self, context):
        """
        Person的Fallback决策 (当LLM失败时调用)
        """
        # 默认行为：StayHomeAction（最安全的选择）
        # 这可以防止仿真因为个别Agent的决策失败而崩溃
        return {
            'action': 'StayHomeAction',
            'reasoning': 'LLM decision failed (network/error), defaulting to StayHomeAction for safety.',
            'params': {},
            'is_fallback': True
        }

    def is_unemployed(self):
        return self.employer is None and self.economical_status == EconomicalStatus.Active

    def is_homeless(self):
        return self.house is None

    def demand(self, value = 0.0):
        """Expense for product/services"""
        if self.house is not None:
            self.house.demand(value)
        else:
            old_wealth = self.wealth
            self.wealth -= value
            
            # Log economic transaction
            economic_logger.log_transaction(
                iteration=getattr(self.environment, 'iteration', -1),
                source_type="Person",
                source_id=str(self.id),
                target_type="External",
                target_id="",
                amount=value,
                transaction_type="person_expense",
                details={"old_wealth": old_wealth, "new_wealth": self.wealth, "has_house": False}
            )

    def supply(self, value = 0.0):
        """Income for work"""
        # ⚠️ 调试日志：记录Person收入（详细追踪）
        if value > 0:
            try:
                iteration = getattr(self.environment, 'iteration', -1)
                day = iteration // 24 if iteration >= 0 else -1
                hour = iteration % 24 if iteration >= 0 else -1
                
                import traceback
                stack = traceback.extract_stack()
                caller = f"{stack[-2].name}:{stack[-2].lineno}"
                
                old_wealth = self.wealth if self.house is None else self.house.wealth
                
                log_cashflow(iteration, day, hour,
                            f"Person.supply({value:.2f}) person_id={str(self.id)[:8]} "
                            f"has_house={self.house is not None} wealth_before={old_wealth:.2f} caller={caller}")
                
                # Log to economic logger
                economic_logger.log_transaction(
                    iteration=iteration,
                    source_type="Caller",
                    source_id=caller,
                    target_type="Person",
                    target_id=str(self.id),
                    amount=value,
                    transaction_type="person_income",
                    details={
                        "has_house": self.house is not None,
                        "old_wealth": old_wealth,
                        "person_wealth": self.wealth
                    }
                )
            except:
                pass
        
        if self.house is not None:
            self.house.supply(value)
        else:
            old_wealth = self.wealth
            self.wealth += value
            # 记录无house Person的财富变化
            if value > 0:
                try:
                    iteration = getattr(self.environment, 'iteration', -1)
                    day = iteration // 24 if iteration >= 0 else -1
                    hour = iteration % 24 if iteration >= 0 else -1
                    log_wealth_change(iteration, day, hour, "Person(NoHouse)", str(self.id), 
                                    old_wealth, self.wealth, "Person.supply", f"value={value:.2f}")
                except:
                    pass

    def move_to_work(self):
        if self.environment.callback('on_person_move', self) or \
                self.environment.callback('on_person_move_to_work', self):
            return
        
        if self.infected_status != InfectionSeverity.Asymptomatic:
            return

        if self.economical_status == EconomicalStatus.Active:
            if self.employer is not None and self.employer.open:
                x, y = np.random.normal(0.0, 0.25, 2)
                self.x = int(self.employer.x + x)
                self.y = int(self.employer.y + y)
                self.employer.checkin(self)
            elif self.employer is None:
                self.move_freely()

        self.environment.callback('post_person_move', self)
        self.environment.callback('post_person_move_to_work', self)

    def move_to_home(self):
        if self.environment.callback('on_person_move_to_home', self):
            return

        if self.infected_status != InfectionSeverity.Asymptomatic:
            return

        if self.house is not None:
            self.house.checkin(self)
            x, y = np.random.normal(0.0, 0.25, 2)
            self.x = int(self.house.x + x)
            self.y = int(self.house.y + y)
        else:
            self.wealth -= self.incomes / 720
            self.move_freely()

        self.environment.callback('post_person_move_to_home', self)

    def move_freely(self):
        if self.environment.callback('on_person_move_freely', self):
            return

        if self.infected_status != InfectionSeverity.Asymptomatic:
            return

        x,y = np.random.normal(0, self.environment.amplitudes[self.status], 2)
        self.x = int(self.x + x)
        self.y = int(self.y + y)

        self.environment.callback('post_person_move_freely', self)

    def move_to(self, agent):
        if self.environment.callback('on_person_move_to', self, agent):
            return

        # 随机偏移：与原ABS系统保持一致
        # std=0.25适用于低密度环境（1.0-1.2人/千平方单位，如500/1000人规模实验）
        # 注意：在高密度环境（>5人/千平方单位，如100人规模测试）中，需要增大std以避免超级传播
        x, y = np.random.normal(0.0, 0.25, 2)
        self.x = int(agent.x + x)
        self.y = int(agent.y + y)

        agent.checkin(self)

        self.environment.callback('post_person_move_to', self)

    def check_balance(self, value):
        if self.house is not None:
            return value <= self.house.wealth
        else:
            return value <= self.wealth

    def update(self):
        """
        Update the status of the agent

        :param agent: an instance of agents.Agent
        """

        if self.environment.callback('on_person_update', self):
            return

        if self.status == Status.Death:
            return

        if self.status == Status.Infected:
            self.infected_time += 1

            ix = get_age_group_index(self.age)

            test_sub = np.random.random()

            if self.infected_status == InfectionSeverity.Asymptomatic:
                if age_hospitalization_probs[ix] > test_sub:
                    self.infected_status = InfectionSeverity.Hospitalization
                    self.move_to(self.environment.healthcare)
            elif self.infected_status == InfectionSeverity.Hospitalization:
                if age_severe_probs[ix] > test_sub:
                    self.infected_status = InfectionSeverity.Severe
                    stats = self.environment.get_statistics(kind='info')
                    if stats['Severe'] + stats['Hospitalization'] >= self.environment.critical_limit:
                        self.status = Status.Death
                        self.infected_status = InfectionSeverity.Asymptomatic
                        if self.house is not None:
                            self.house.remove_mate(self)
                        else:
                            self.environment.government.cash(-self.expenses)

                        if self.employer is not None:
                            self.employer.fire(self)
                        else:
                            self.environment.government.cash(-self.expenses)

            death_test = np.random.random()
            if age_death_probs[ix] > death_test:
                self.status = Status.Death
                self.infected_status = InfectionSeverity.Asymptomatic
                
                # ✅ 修复: 处理雇佣关系（与Severe死亡逻辑保持一致）
                if self.house is not None:
                    self.house.remove_mate(self)
                else:
                    self.environment.government.cash(-self.expenses)
                
                if self.employer is not None:
                    self.employer.fire(self)
                else:
                    self.environment.government.cash(-self.expenses)
                
                self.move_to_home()
                return

            if self.infected_time > self.environment.recovering_time:
                self.infected_time = 0
                self.status = Status.Recovered_Immune
                self.infected_status = InfectionSeverity.Asymptomatic

        self.environment.callback('post_person_update', self)
    
    # ==================== LLM Decision Methods ====================
    
    def should_decide(self, current_iteration):
        """
        判断是否需要进行LLM决策
        
        Args:
            current_iteration: 当前迭代次数
            
        Returns:
            bool: 是否需要决策
        """
        # 🔧 [FIX] 死亡的Person不需要进行决策
        # 避免尝试为已死亡的agent生成LLM决策（可能导致决策失败）
        if hasattr(self, 'status') and self.status == Status.Death:
            return False
        
        if not hasattr(self, 'last_decision_time'):
            self.last_decision_time = -999
        
        if not hasattr(self, 'decision_interval'):
            # GraphSimulation: 每6小时决策一次 (一天4次)
            self.decision_interval = 6
        
        # 检查是否到了决策时间
        return (current_iteration - self.last_decision_time) >= self.decision_interval
    
    def decide(self, status_pool):
        """
        使用LLM进行决策
        
        Args:
            status_pool: GraphStatusPool实例
            
        Returns:
            dict: 决策结果 {action, reasoning, params}
            
        Raises:
            RuntimeError: LLM决策失败时抛出异常
        """
        if not hasattr(self, 'backend') or self.backend is None:
            raise RuntimeError(
                f"Person {self.id} has no LLM backend configured. "
                "Cannot make LLM decision."
            )
        
        # 获取决策上下文
        context = status_pool.get_person_context(self)
        
        # 获取Action Registry (GraphSimulation Person)
        from covid_abs.llm.actions import get_action_registry
        action_registry = get_action_registry(register_graph_actions=True)
        
        # 构建LLM Prompt
        prompt = self._build_decision_prompt(context, action_registry)
        
        try:
            # 调用LLM（backend会自动处理重试，包括TPM限制、网络错误等）
            # max_retries已在backend配置，这里不需要额外重试
            response = self.backend.query(prompt, temperature=0.7)
            
            # 解析LLM响应
            decision = self._parse_llm_response(response, action_registry)
            
            return decision
            
        except Exception as e:
            # Backend的所有重试都失败了，使用Fallback决策
            print(f"[FALLBACK WARNING] Person {self.id} at iteration {context['time']['iteration']}")
            print(f"   Reason: {str(e)[:200]}")
            print(f"   Using rule-based fallback decision")
            
            # 获取fallback决策并标记
            fallback_decision = self._get_fallback_decision(context, action_registry)
            fallback_decision['is_fallback'] = True  # 标记这是fallback决策
            fallback_decision['fallback_reason'] = str(e)[:200]
            
            return fallback_decision
    
    def _get_fallback_decision(self, context, action_registry):
        """
        提供Fallback决策（当LLM调用失败时使用）
        
        使用基于规则的简单逻辑
        """
        personal = context['personal']
        employment = context['employment']
        household = context['household']
        time_ctx = context['time']
        current_hour = time_ctx['hour']
        
        # 规则1：有症状 → 待在家休息
        if personal['has_symptom']:
            return {
                'action': 'StayHomeAction',
                'reasoning': 'Feeling unwell, staying home to rest (fallback decision)',
                'params': {}
            }
        
        # 规则2：工作时间 + 有工作 + 公司开门 → 去上班
        if 9 <= current_hour < 17 and employment['employed'] and employment['employer_open']:
            return {
                'action': 'GoToWorkAction',
                'reasoning': 'Work hours, going to work (fallback decision)',
                'params': {}
            }
        
        # 规则3：商店营业时间 + 资金充足 → 购物
        if 8 <= current_hour < 22 and household['days_sustainable'] > 3:
            shopping_history = context.get('shopping_history', {})
            if shopping_history.get('shopping_urgency') in ['HIGH', 'CRITICAL']:
                return {
                    'action': 'ShoppingAction',
                    'reasoning': 'Store hours, need supplies (fallback decision)',
                    'params': {}
                }
        
        # 规则4：没工作 + 活跃 → 找工作
        if not employment['employed'] and personal['economical_status'] == 'Active' and 9 <= current_hour < 17:
            return {
                'action': 'SeekJobAction',
                'reasoning': 'Unemployed, seeking job (fallback decision)',
                'params': {}
            }
        
        # 默认：待在家
        return {
            'action': 'StayHomeAction',
            'reasoning': 'No specific task, staying home (fallback decision)',
            'params': {}
        }
    
    def _build_decision_prompt(self, visible_info, action_registry, available_actions=None):
        """
        Build LLM decision prompt (GraphSimulation version).
        
        Args:
            visible_info: Context returned by get_person_context (complete context in GraphSimulation)
            action_registry: ActionRegistry instance
            available_actions: Optional list of action names
            
        Returns:
            str: Prompt text
        """
        # In GraphSimulation, visible_info is actually the complete context
        context = visible_info
        personal = context['personal']
        employment = context['employment']
        household = context['household']
        epidemic = context['epidemic']
        economic = context['economic']
        time_ctx = context['time']
        
        # Health status description
        # 🔧 信息不对称原则：无症状感染者不知道自己被感染
        # 只有有症状时才告知感染状态，符合现实世界
        if personal['has_symptom']:
            health_desc = f"You have {personal['infected_status']} symptoms"
        elif personal['status'] == 'Recovered_Immune':
            health_desc = "You are currently Recovered_Immune"
        else:
            # 无症状（无论Susceptible还是Infected）都显示为健康
            health_desc = "You are currently healthy"
        
        # Employment status description
        if employment['employed']:
            if employment['employer_open']:
                employment_desc = f"You work at {employment['employer_name']}, monthly income {employment['monthly_income']:.1f}"
                # ✨ 新增：远程办公提示
                if employment.get('can_work_from_home', False):
                    employment_desc += "\nREMOTE WORK OPTION: You can choose 'WorkFromHomeAction' to work safely from home for full salary."
            else:
                employment_desc = f"Your employer {employment['employer_name']} is closed"
        else:
            # 强化失业者的求职引导
            days_unemployed = employment.get('days_unemployed', 0)
            if days_unemployed > 7:
                employment_desc = f"⚠️ UNEMPLOYED for {days_unemployed} days - URGENT: Seek employment immediately!"
            elif days_unemployed > 3:
                employment_desc = f"UNEMPLOYED for {days_unemployed} days - Should actively seek employment"
            else:
                employment_desc = "Recently unemployed - Start looking for new employment opportunities"
        
        # Wealth and consumption capacity description
        days = household['days_sustainable']
        wealth = household['house_wealth']
        
        if days < 3:
            wealth_desc = f"CRITICAL: Financial Crisis! Only {days:.1f} days of funds remaining (${wealth:.0f})"
            consumption_note = "URGENT: Cannot afford regular shopping, seek employment immediately"
        elif days < 7:
            wealth_desc = f"LOW FUNDS: {days:.1f} days sustainable (${wealth:.0f})"
            consumption_note = "LIMITED: Shopping capacity limited, prioritize essentials only"
        else:
            wealth_desc = f"Household wealth: ${wealth:.0f} ({days:.1f} days sustainable)"
            # 失业者特殊消费提示
            if not employment['employed']:
                if days > 30:
                    consumption_note = "Unemployed but have savings - limit shopping to essentials, focus on finding work"
                else:
                    consumption_note = "Unemployed with limited funds - minimize shopping, prioritize job seeking"
            elif days > 30:
                consumption_note = "Strong purchasing power - can afford regular shopping for household needs"
            else:
                consumption_note = "Adequate funds for normal consumption and shopping"
        
        # Epidemic situation description
        epidemic_desc = (
            f"Infection rate {epidemic['infected_rate']*100:.1f}%, "
            f"Deaths {epidemic['total_deaths']}, "
            f"Healthcare load {epidemic['healthcare_load']*100:.1f}%"
        )
        
        # 优化：移除冗余的时间描述函数（LLM能从hour推断）
        # 保留核心决策信息即可
        
        # ✅ 优化：使用StatusPool的Action过滤逻辑
        # 根据agent的感染状态、经济状态等过滤可用Action
        from covid_abs.llm.actions import get_action_registry
        registry = get_action_registry(register_graph_actions=True)
        
        # 从simulation获取status_pool（如果可用）
        try:
            status_pool = self.environment.status_pool
            available_actions = status_pool.get_available_actions_for_agent(self)
            
            # 获取政府政策信息
            policy = status_pool.government_policy
            policy_lines = []
            if policy.get('stay_home_order', False):
                # 禁足令：强制性但明确允许例外
                policy_lines.append("STAY-HOME ORDER (Mandatory): MUST stay home EXCEPT essential work, essential shopping (food/medicine), or medical care. All other activities PROHIBITED.")
            
            # ✅ 检查是否有更强烈的强制封锁消息 (from GraphStatusPool)
            # 如果有，覆盖普通的policy_lines，放在最显眼的位置
            mandatory_msg = context.get('policy', {}).get('mandatory_lockdown_message')
            if mandatory_msg:
                policy_lines.insert(0, mandatory_msg)
                
            if policy.get('borders_closed', False):
                policy_lines.append("Border controls: Closed")
            
            policy_info = "\n".join(policy_lines) if policy_lines else "No special restrictions"
        except AttributeError:
            # 如果没有status_pool，使用旧的手动逻辑（向后兼容）
            available_actions = []
            if employment['employed'] and employment['employer_open']:
                available_actions.append("GoToWorkAction")
                available_actions.append("WorkFromHomeAction")
            available_actions.append("StayHomeAction")
            if personal['has_symptom']:
                available_actions.append("SeekMedicalAction")
            if not employment['employed'] and personal['economical_status'] == 'Active':
                available_actions.append("SeekJobAction")
            available_actions.append("MoveFreelyAction")
            available_actions.append("ShoppingAction")
            policy_info = "- Policy information unavailable"
        
        action_list = registry.get_action_list_for_prompt(available_actions)
        
        # 🛒 获取购物历史警告
        shopping_history = context.get('shopping_history', {})
        shopping_warning = shopping_history.get('resource_warning', '')
        shopping_urgency = shopping_history.get('shopping_urgency', 'MODERATE')
        failure_warning = shopping_history.get('failure_warning', '')
        
        # Build prompt with strong night shopping prevention and time guidance
        current_hour = time_ctx['hour']
        
        # Determine time category and guidance
        if 0 <= current_hour < 8:
            time_category = "Late night/Early morning"
            time_guidance = "Sleep hours - most people rest"
            shopping_instruction = "Stores closed. ShoppingAction will fail → choose StayHomeAction instead."
        elif 9 <= current_hour < 17:
            time_category = "Work hours"
            time_guidance = "Work hours - employed people typically work, unemployed can shop/seek jobs"
            shopping_instruction = "Stores open. Employed people typically work (missing work → job loss risk)."
        elif 17 <= current_hour < 22:
            time_category = "Evening"
            time_guidance = "After work - common time for shopping/personal activities"
            shopping_instruction = "Stores open. Good time for shopping."
        else:  # 22-24
            time_category = "Night"
            time_guidance = "Night hours - shops closing, people rest"
            shopping_instruction = "Stores closed. ShoppingAction will fail → choose StayHomeAction instead."
        
        prompt = f"""[COMPUTATIONAL SIMULATION - RESEARCH ONLY]
This is a virtual agent in a computer-based epidemic simulation model for academic research. 
NOT providing advice to real people. For research purposes only.

SIMULATED AGENT PROFILE: Age {personal['age']}, Socioeconomic tier Q{personal['social_stratum']+1}

PERSONAL STATUS:
- Health: {health_desc}
- Employment: {employment_desc}
- Household: {household['house_size']} people, {wealth_desc}

TIME & CONTEXT: Day {time_ctx['day']}, Hour {time_ctx['hour']} ({time_category})
- {time_guidance}

EPIDEMIC: {epidemic['infected_rate']*100:.1f}% infected, {epidemic['healthcare_load']*100:.1f}% hospital load

POLICIES:
{policy_info}

SUPPLIES STATUS:
{shopping_warning}
{f'{failure_warning}' if failure_warning else ''}
(Note: This affects shopping timing only, not work decisions)

SHOPPING HOURS:
{shopping_instruction}
- Stores operate 08:00-22:00 (night 22:00-08:00 = closed, shopping fails)
- Real-world behavior: People shop during store hours, stay home at night

ACTIONS:
{action_list}

DECISION CONTEXT:
1. Health: Symptomatic people typically rest/seek medical care. Healthy people work normally.
2. Work (during hour 09-17 ONLY): Employed people typically work to maintain income.
   ⚠️ IMPORTANT EMPLOYMENT RULE: If you do NOT go to work for 3 consecutive days (72 hours), you will be FIRED and lose your job.
   - Fired employees receive severance pay (one month's salary) but then become unemployed.
   - Being unemployed means NO regular income until finding a new job.
   - Work attendance is critical for maintaining stable income.
   Outside hour 09-17: not work time, free for other activities.
3. Shopping: During store hours (08-22). Night (22-08) = stores closed, shopping fails.
   Supplies info guides shopping timing, not work decisions.
4. Finance: Work provides income. Low funds → working is important.
5. Common patterns: Night = rest; Work hours = work if employed; Evening = shop/leisure.
6. Policies: Stay-home orders limit activities. Balance safety with essential needs.

JSON (reasoning: 1-2 sentences, keep it simple and concise, <80 words):
{{"action": "ActionName", "reasoning": "brief reason", "params": {{}}}}"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, action_registry) -> dict:
        """
        解析LLM响应 (GraphSimulation版本)
        
        Args:
            response: LLM返回的文本
            action_registry: ActionRegistry实例 (基类接口要求,但Graph版本暂不使用)
            
        Returns:
            dict: {action, reasoning, params}
            
        Raises:
            ValueError: 解析失败
        """
        import json
        
        # 尝试直接解析(如果整个响应就是JSON)
        try:
            decision = json.loads(response)
            if 'action' in decision:
                # 设置默认值
                if 'reasoning' not in decision:
                    decision['reasoning'] = "No reasoning provided"
                if 'params' not in decision:
                    decision['params'] = {}
                return decision
        except json.JSONDecodeError:
            pass
        
        # 使用共享的智能JSON提取函数
        json_str = extract_json_from_llm_response(response)
        
        if not json_str:
            raise ValueError(f"Cannot find valid JSON in LLM response: {response}")
        
        try:
            decision = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {json_str}") from e
        
        # 验证必需字段
        if 'action' not in decision:
            raise ValueError(f"Missing 'action' field in decision: {decision}")
        
        # 设置默认值
        if 'reasoning' not in decision:
            decision['reasoning'] = "No reasoning provided"
        if 'params' not in decision:
            decision['params'] = {}
        
        return decision
