"""
Graph induced
"""

import numpy as np
from covid_abs.abs import *
from covid_abs.agents import AgentType, Status, InfectionSeverity
from covid_abs.graphics import color1 as color
from covid_abs.network.agents import Business, House, Person, EconomicalStatus
from covid_abs.economic_logger import economic_logger
from covid_abs.network.util import new_day, work_day, new_month, bed_time, work_time, lunch_time, free_time


class GraphSimulation(Simulation):
    def __init__(self, **kwargs):
        super(GraphSimulation, self).__init__(**kwargs)
        self.total_population = kwargs.get('total_population', 0)
        self.total_business = kwargs.get('total_business', 10)
        self.business_distance = kwargs.get('business_distance', 10)
        self.government = None
        self.business = []
        self.houses = []
        self.healthcare = None
        self.homeless_rate = kwargs.get("homeless_rate", 0.0005)  # ✅ 0.05%无家可归率 [45]
        self.unemployment_rate = kwargs.get("unemployment_rate", 0.12)  # ✅ 12%失业率 [54]
        self.homemates_avg = kwargs.get("homemates_avg", 3)
        self.homemates_std = kwargs.get("homemates_std", 1)
        self.iteration = -1
        self.callbacks = kwargs.get('callbacks', {})
        self.public_gdp_share = kwargs.get('public_gdp_share', 0.1)      # ✅ 10% (论文代码实际值)
        self.business_gdp_share = kwargs.get('business_gdp_share', 0.4)  # ✅ 40% (调整后推荐值)
        # ========================================================================
        # 疾病时间参数（单位：天）
        # ========================================================================
        # infected_time 在 agent.update() 中每天+1（new_dy时调用）
        # 所以这些参数的单位就是天，不需要转换
        # ========================================================================
        self.incubation_time = kwargs.get('incubation_time', 5)     # 5天潜伏期
        self.contagion_time = kwargs.get('contagion_time', 10)     # 10天传染期
        self.recovering_time = kwargs.get('recovering_time', 20)   # 20天康复期
        
        # 🔧 经济开放度参数 (0.0=完全封闭, 1.0=完全开放)
        self.economy_openness = kwargs.get('economy_openness', 0.3)  # ✅ 0.3适度开放（推荐值）
        '''Economy openness level: 
        - 0.0 = Closed economy (no capital outflow, all money circulates internally)
        - 1.0 = Fully open economy (maximum capital outflow to foreign markets)
        - 0.3-0.5 = Moderate openness (balanced between local circulation and outflow)
        '''
        
        # ✅ 参数验证
        if not isinstance(self.economy_openness, (int, float)):
            raise TypeError(f"economy_openness must be a number, got {type(self.economy_openness)}")
        if not 0.0 <= self.economy_openness <= 1.0:
            raise ValueError(f"economy_openness must be in [0.0, 1.0], got {self.economy_openness}")
        
        # ✅ 性能优化：预计算开放度相关比例（避免每次update重复计算）
        self._house_local_ratio = (1 - self.economy_openness) * 0.9
        self._business_b2b_ratio = (1 - self.economy_openness) * (2.0 / 3.0)
        '''
        预计算的比例缓存：
        - _house_local_ratio: House本地循环比例
        - _business_b2b_ratio: Business B2B交易比例
        在每天的update()中复用，避免重复计算（50个House + 10个Business = 每天60次）
        '''
        
        # 🔧 Business运营成本参数
        self.business_base_cost = kwargs.get('business_base_cost', 200)
        '''Business基础运营成本（元/员工/月）'''
        self.business_stratum_multipliers = kwargs.get('business_stratum_multipliers', 
                                                       [1.0, 2.0, 3.25, 5.0, 13.75])
        '''Business各阶层成本倍数（Q1-Q5）'''
        
        # 🎬 Scenario配置 - 控制Government政策系统
        self.scenario_config = kwargs.get('scenario_config', {})
        '''Scenario configuration for government policy system:
        - government_decision_interval: How often government makes decisions (hours)
        - enable_policy_recommendation: Whether to provide dynamic policy recommendations to LLM
        - policy_recommendation_mode: 'aggressive', 'balanced', or 'conservative'
        - infection rate thresholds for recommendations
        - economic_weight: Balance between health and economy in recommendations
        '''
        
        # LLM相关配置 - 统一使用与Basic/MultiPopulation相同的参数名
        self.enable_llm_decision = kwargs.get('enable_llm_decision', False)
        '''Whether to enable LLM-based decision making'''
        self.backend = kwargs.get('backend', None)
        '''LLM backend for agent decision making (None = rule-based only)'''
        
        # 决策间隔配置
        self.decision_interval = kwargs.get('decision_interval', 6)
        '''Default decision interval in hours (can be overridden per agent type)'''
        self.llm_decision_interval = kwargs.get('llm_decision_interval', self.decision_interval)
        '''Legacy parameter name for backward compatibility'''
        
        self.status_pool = None  # GraphStatusPool实例
        
        # 向后兼容旧参数名
        if 'use_llm' in kwargs:
            self.enable_llm_decision = kwargs.get('use_llm', False)
        if 'llm_backend' in kwargs:
            self.backend = kwargs.get('llm_backend', None)

    def register_callback(self, event, action):
        self.callbacks[event] = action

    def callback(self, event, *args):
        if event in self.callbacks:
            return self.callbacks[event](*args)

        return False

    def get_unemployed(self):
        # 保持原逻辑：只有Asymptomatic的失业者才能领救济金（控制Government支出）
        return [p for p in self.population if p.is_unemployed()
                and p.status != Status.Death and p.infected_status == InfectionSeverity.Asymptomatic]

    def get_homeless(self):
        return [p for p in self.population if p.is_homeless()
                and p.status != Status.Death and p.infected_status == InfectionSeverity.Asymptomatic]
    
    def _log_wealth_snapshot(self, event: str = ""):
        """Log a snapshot of current wealth distribution"""
        try:
            # Collect wealth data
            wealth_data = {
                'Government': self.government.wealth if self.government else 0,
                'Healthcare': self.healthcare.wealth if self.healthcare else 0,
                'Business_total': sum(b.wealth for b in self.business),
                'House_total': sum(h.wealth for h in self.houses),
                'Homeless_total': sum(p.wealth for p in self.population if p.house is None)
            }
            
            # Add wealth by social stratum
            for stratum in range(5):
                stratum_wealth = sum(h.wealth for h in self.houses if h.social_stratum == stratum)
                wealth_data[f'Q{stratum+1}'] = stratum_wealth
            
            # Log the snapshot
            economic_logger.log_wealth_snapshot(
                iteration=self.iteration,
                wealth_data=wealth_data,
                event=event
            )
        except Exception as e:
            pass  # Silently fail to not disrupt simulation

    def create_business(self, social_stratum=None):
        x, y = self.random_position()
        if social_stratum is None:
            social_stratum = int(np.random.rand(1) * 100 // 20)
        self.business.append(Business(x=x, y=y, status=Status.Susceptible, social_stratum=social_stratum,
                                      #fixed_expenses=(social_stratum+1)*self.minimum_expense
                                      #fixed_expenses=self.minimum_expense / (5 - social_stratum)
                                      environment=self
                                      ))

    def create_house(self, social_stratum=None):
        x, y = self.random_position()
        if social_stratum is None:
            social_stratum = int(np.random.rand(1) * 100 // 20)
        house = House(x=x, y=y, status=Status.Susceptible, social_stratum=social_stratum,
                                 #fixed_expenses=(social_stratum+1)*self.minimum_expense/(self.homemates_avg*10
                      environment=self)
        self.callback('on_create_house', house)
        self.houses.append(house)

    def create_agent(self, status, social_stratum=None, infected_time=0):
        """
        Create a new agent with the given status

        :param infected_time:
        :param social_stratum:
        :param status: a value of agents.Status enum
        :return: the newly created agent
        """

        age = int(np.random.beta(2, 4, 1) * 100)
        if social_stratum is None:
            social_stratum = int(np.random.rand(1) * 100 // 20)
        person = Person(age=age, status=status, social_stratum=social_stratum, infected_time=infected_time,
                        environment=self)
        self.callback('on_create_person', person)
        self.population.append(person)

    def initialize(self):
        """
        Initializate the Simulation by creating its population of agents
        """

        self.callback('on_initialize', self)

        x, y = self.random_position()
        self.healthcare = Business(x=x, y=y, status=Status.Susceptible, type=AgentType.Healthcare, environment=self)
        self.healthcare.fixed_expenses += self.minimum_expense * 3
        x, y = self.random_position()
        self.government = Business(x=x, y=y, status=Status.Susceptible, type=AgentType.Government,
                                   social_stratum=4, price=1.0, environment=self)
        self.government.fixed_expenses += self.population_size * (self.minimum_expense*0.05)
        
        # 初始化政府政策状态
        self.government.policy = {
            'stay_home_order': False,
            'borders_closed': False,
            'tax_rate': 1.0,
            'stimulus_active': False,
            'medical_budget_increased': False
        }

        #number of houses
        for i in np.arange(0, int(self.population_size // self.homemates_avg)):
            self.create_house(social_stratum=i % 5)

        # number of business
        for i in np.arange(0, self.total_business):
            self.create_business(social_stratum=i % 5)

        # ========================================================================
        # [FIX] 问题1: 为所有按比例初始化的参数添加最小值保护（至少1个agent）
        # ========================================================================
        # Initial infected population - 确保至少1人感染（如果比例>0）
        infected_count = max(1, int(self.population_size * self.initial_infected_perc)) if self.initial_infected_perc > 0 else 0
        for i in np.arange(0, infected_count):
            self.create_agent(Status.Infected, infected_time=5)

        # Initial immune population - 确保至少1人免疫（如果比例>0）
        immune_count = max(1, int(self.population_size * self.initial_immune_perc)) if self.initial_immune_perc > 0 else 0
        for i in np.arange(0, immune_count):
            self.create_agent(Status.Recovered_Immune)

        # Initial susceptible population
        for i in np.arange(0, self.population_size - len(self.population)):
            self.create_agent(Status.Susceptible, social_stratum=i % 5)

        # Share the common wealth of 10^4 among the population, according each agent social stratum

        self.government.wealth = self.total_wealth * self.public_gdp_share

        for quintile in [0, 1, 2, 3, 4]:

            _houses = [x for x in filter(lambda x: x.social_stratum == quintile, self.houses)]
            nhouses = len(_houses)

            if nhouses == 0:
                self.create_house(social_stratum=quintile)
                _houses = [self.houses[-1]]
                nhouses = 1

            # ========================================================================
            # [FIX] 问题3: Business财富分配Bug修复
            # 问题: 当business数量较少时，按quintile分配会导致部分quintile无business
            #       这些quintile的财富池就被浪费了
            # 解决: 统一使用全局分配策略，将Business GDP份额平均分给所有business
            # ========================================================================
            if self.total_business > 5:
                # 大量business: 按Lorenz曲线分配给每个quintile
                btotal = lorenz_curve[quintile] * (self.total_wealth * self.business_gdp_share)
                businesses_in_quintile = [a for a in self.business if a.social_stratum == quintile]
                bqty = max(1.0, len(businesses_in_quintile))
                ag_share = btotal / bqty
                for bus in businesses_in_quintile:
                    bus.wealth = ag_share
            else:
                # 少量business: 平均分配总Business财富（只在quintile=0时执行一次）
                if quintile == 0:
                    total_business_wealth = self.total_wealth * self.business_gdp_share
                    ag_share = total_business_wealth / max(1, self.total_business)
                    for bus in self.business:
                        bus.wealth = ag_share

            ptotal = lorenz_curve[quintile] * self.total_wealth * (1 - (self.public_gdp_share + self.business_gdp_share))

            pqty = max(1.0, np.sum([1 for a in self.population if
                                   a.social_stratum == quintile and a.economical_status == EconomicalStatus.Active]))
            ag_share = ptotal / pqty

            for agent in filter(lambda x: x.social_stratum == quintile, self.population):

                # distribute wealth

                if agent.economical_status == EconomicalStatus.Active:
                    agent.wealth = ag_share
                    agent.incomes = basic_income[agent.social_stratum] * self.minimum_income

                    # distribute employ

                    unemployed_test = np.random.rand()

                    if unemployed_test >= self.unemployment_rate:
                        ix = np.random.randint(0, self.total_business)
                        self.business[ix].hire(agent)

                agent.expenses = basic_income[agent.social_stratum] * self.minimum_expense

                #distribute habitation

                homeless_test = np.random.rand()

                if not (quintile == 0 and homeless_test <= self.homeless_rate):
                    for kp in range(0, 5):
                        ix = np.random.randint(0, nhouses)
                        house = _houses[ix]
                        if house.size < self.homemates_avg + self.homemates_std:
                            house.append_mate(agent)
                            continue
                    if agent.house is None:
                        ix = np.random.randint(0, nhouses)
                        self.houses[ix].append_mate(agent)
        
        # ✨ 新增：记录各Business的初始员工数
        for business in self.business:
            business.initial_employees = len(business.employees)
            # 防止除零，设置最小值
            if business.initial_employees == 0:
                business.initial_employees = 10
        
        # 可选：输出调试信息
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"Business initial employees: {[b.initial_employees for b in self.business]}")

        # LLM初始化 - 为Person agents配置LLM决策能力
        if self.enable_llm_decision:
            self._initialize_llm()

        self.callback('post_initialize', self)
    
    def _initialize_llm(self):
        """
        初始化LLM相关组件
        - 创建GraphStatusPool
        - 为每个Person配置LLM backend和决策参数
        """
        # 导入GraphStatusPool
        try:
            from covid_abs.llm.graph_message import GraphStatusPool
        except ImportError as e:
            raise RuntimeError(
                "Cannot import GraphStatusPool. Make sure graph_message.py exists."
            ) from e
        
        # 创建StatusPool（传入scenario配置）
        self.status_pool = GraphStatusPool(
            simulation=self,
            scenario_config=self.scenario_config
        )
        
        if self.backend is None:
            raise RuntimeError(
                "GraphSimulation.enable_llm_decision=True but backend is None. "
                "Please provide a valid LLM backend instance."
            )
        
        # 为每个Person配置LLM属性
        person_count = 0
        # 🎬 Person决策频率：优先使用scenario_config，其次使用decision_interval参数
        person_interval = self.scenario_config.get('person_decision_interval', self.llm_decision_interval)
        
        for agent in self.population:
            if isinstance(agent, Person):
                agent.backend = self.backend
                agent.decision_interval = person_interval
                agent.last_decision_time = -999  # 确保第一轮就决策
                
                # 生成角色描述
                agent.role_desc = self._generate_person_role_description(agent)
                
                # 初始化absence_count (StayHomeAction需要)
                agent.absence_count = 0
                
                person_count += 1
        
        # 为每个Business配置LLM属性
        business_count = 0
        # 🎬 Business决策频率：优先使用scenario_config，默认24小时（每天一次）
        business_interval = self.scenario_config.get('business_decision_interval', 24)
        
        for bus in self.business:
            # 跳过Government和Healthcare (它们单独配置)
            if bus == self.government or bus == self.healthcare:
                continue
            
            bus.backend = self.backend
            bus.decision_interval = business_interval
            bus.last_decision_time = -999  # 确保第一天就决策
            
            # 生成角色描述
            bus.role_desc = self._generate_business_role_description(bus)
            
            business_count += 1
        
        # 为Government配置LLM属性
        if self.government:
            self.government.backend = self.backend
            # 🎬 使用scenario_config中的government_decision_interval（默认6小时）
            gov_interval = self.scenario_config.get('government_decision_interval', 24)
            self.government.gov_decision_interval = gov_interval
            self.government.last_gov_decision_time = -999  # Ensure decision in first iteration
            self.government.role_desc = "You are the national government responsible for formulating epidemic prevention and economic policies, balancing public health and economic development."
            
            print(f"[LLM Init] Government decision interval: {gov_interval} hours " +
                  f"({gov_interval/24:.1f} days)")
            if self.scenario_config.get('enable_policy_recommendation'):
                mode = self.scenario_config.get('policy_recommendation_mode', 'balanced')
                print(f"[LLM Init] Policy recommendation: ENABLED (mode={mode})")
            else:
                print(f"[LLM Init] Policy recommendation: DISABLED")
        
        print(f"[LLM Init] Configured {person_count} Person agents with LLM decision-making")
        print(f"[LLM Init] Configured {business_count} Business agents with LLM decision-making")
        print(f"[LLM Init] Configured Government with LLM decision-making")
        
        # ✅ 打印实际的决策频率（从scenario_config或参数读取）
        print(f"[LLM Init] Person decision interval: {person_interval} iterations ({person_interval/24:.2f} days)")
        print(f"[LLM Init] Business decision interval: {business_interval} iterations ({business_interval/24:.2f} days)")
        if self.government:
            actual_gov_interval = self.government.gov_decision_interval
            print(f"[LLM Init] Government decision interval: {actual_gov_interval} iterations ({actual_gov_interval/24:.2f} days)")
    
    def _generate_business_role_description(self, business: Business) -> str:
        """
        Generate role description for a Business agent.
        
        Args:
            business: Business instance
            
        Returns:
            str: Role description
        """
        stratum_names = ['Poverty-Level Business', 'Low-Income Business', 'Middle-Class Business', 'Affluent Business', 'Wealthy Business']
        # Ensure social_stratum is within valid range
        stratum_idx = min(max(0, business.social_stratum), 4)
        stratum_name = stratum_names[stratum_idx]
        
        employee_desc = f"employing {len(business.employees)} people" if business.employees else "currently no employees"
        
        return (
            f"You are the owner of a {stratum_name}, "
            f"{employee_desc}. "
            f"During the pandemic, you must balance business profits, employee welfare, and social responsibility."
        )
    
    def _generate_person_role_description(self, person: Person) -> str:
        """
        Generate role description for a Person agent.
        
        Args:
            person: Person instance
            
        Returns:
            str: Role description
        """
        stratum_names = ['Poverty Level', 'Low Income', 'Middle Class', 'Affluent', 'Wealthy']
        stratum_name = stratum_names[person.social_stratum]
        
        employment_desc = "employed" if person.employer else "unemployed"
        housing_desc = "with housing" if person.house else "homeless"
        
        return (
            f"You are a {person.age}-year-old {stratum_name} resident, "
            f"currently {employment_desc} and {housing_desc}. "
            f"During the pandemic, you must balance health, work, and life."
        )

    def execute(self):

        self.iteration += 1

        if self.callback('on_execute', self):
            return

        #print(self.iteration)

        bed = bed_time(self.iteration)
        work = work_time(self.iteration)
        free = free_time(self.iteration)
        lunch = lunch_time(self.iteration)
        new_dy = new_day(self.iteration)
        work_dy = work_day(self.iteration)
        new_mth = new_month(self.iteration)
        
        # ========================================
        # 紧急封锁机制 (Health Priority Scenario)
        # ========================================
        # 在health_priority场景下，当感染率超过5%时立即触发强制封锁 (原15% -> 5%以增强差异)
        # 不需要等待政府的下一次决策周期
        if self.scenario_config.get('name') == 'health_priority':
            # 计算当前感染率
            infected_count = sum(1 for a in self.population if a.status == Status.Infected)
            infection_rate = infected_count / max(self.population_size, 1)
            
            # 检查是否需要紧急封锁 (Threshold reduced to 0.05)
            if infection_rate > 0.05 and not self.government.policy.get('stay_home_order', False):
                print(f"\n{'='*80}")
                print(f"[EMERGENCY LOCKDOWN] Infection rate {infection_rate*100:.1f}% exceeds 5% threshold!")
                print(f"  Scenario: health_priority")
                print(f"  Iteration: {self.iteration} (Day {self.iteration//24})")
                print(f"  Activating mandatory stay-home order immediately")
                print(f"{'='*80}\n")
                
                # 立即更新政府政策
                self.government.policy['stay_home_order'] = True
                self.government.policy['borders_closed'] = True
                # 添加强制封锁标记（用于生成更强硬的提示）
                self.government.policy['mandatory_lockdown'] = True
                
                # 更新StatusPool中的政府政策（确保所有agent立即感知）
                if hasattr(self, 'status_pool') and self.status_pool:
                    self.status_pool.government_policy = self.government.policy.copy()
                    
                    # 记录紧急决策到StatusPool
                    from covid_abs.llm.message import Decision
                    emergency_decision = Decision(
                        agent_id=self.government.id,
                        iteration=self.iteration,
                        action='EmergencyLockdownAction',
                        params={'stay_home_order': True, 'borders_closed': True},
                        reasoning=f'EMERGENCY: Infection rate {infection_rate*100:.1f}% exceeds 5% threshold - immediate lockdown required',
                        is_fallback=False,
                        fallback_reason=''
                    )
                    self.status_pool.append_decision(emergency_decision)
                    
                    # 立即通知所有Person agents政策变化
                    print(f"[EMERGENCY] Notifying all {len(self.population)} agents about lockdown...")
                    
            # 检查是否可以解除封锁（感染率降到2%以下，原5%）
            elif infection_rate < 0.02 and self.government.policy.get('stay_home_order', False):
                # 这个由政府正常决策处理，不自动解除
                pass  # 保留给政府LLM决策

        #if new_dy:
        #    print("Day {}".format(self.iteration // 24))

        # ==================== LLM Concurrent Decision Phase ====================
        if self.enable_llm_decision:
            # 初始化StatusPool (如果是第一轮)
            if self.status_pool is None:
                raise RuntimeError(
                    "GraphSimulation.enable_llm_decision=True but status_pool is None. "
                    "Did you call initialize()?"
                )
            
            # 初始化DecisionBufferManager和ConcurrentExecutor (第一次执行时)
            if not hasattr(self, 'decision_buffer'):
                from covid_abs.llm.decision_buffer import DecisionBufferManager, ConcurrentDecisionExecutor
                self.decision_buffer = DecisionBufferManager(self.status_pool)
                self.decision_executor = ConcurrentDecisionExecutor(
                    max_workers=self.max_concurrent_llm
                )
                print(f"[GraphSimulation LLM Concurrent Mode] Initialized with max_concurrent_llm={self.max_concurrent_llm}")
            
            # 更新StatusPool统计信息 (来自上一个iteration)
            stats = self.get_statistics(kind='info')
            self.status_pool.update_statistics(stats)
            
            # 获取Action Registry (GraphSimulation专用)
            from covid_abs.llm.actions import get_action_registry
            action_registry = get_action_registry(register_graph_actions=True)
            
            # ========================================
            # Phase 1: Person Agents - 并发决策
            # ========================================
            
            # 启动新iteration的缓冲区
            self.decision_buffer.start_iteration(self.iteration)
            
            # 收集需要决策的Person agents
            deciding_persons = [
                agent for agent in self.population
                if isinstance(agent, Person) 
                and agent.status != Status.Death
                and agent.should_decide(self.iteration)
            ]
            
            if deciding_persons:
                # 🔥 并发执行所有Person的LLM决策!
                decision_results = self.decision_executor.execute_concurrent_decisions(
                    agents=deciding_persons,
                    status_pool=self.status_pool,  # ✅ 只读!所有agent看到相同状态
                    iteration=self.iteration,
                    experiment_id=self.experiment_id if hasattr(self, 'experiment_id') else 1
                )
                
                # 处理决策结果
                from covid_abs.llm.message import Decision
                successful_decisions = 0
                failed_decisions = []
                
                for result in decision_results:
                    if result['success']:
                        decision = result['decision']
                        agent = next(a for a in deciding_persons if a.id == result['agent_id'])
                        
                        # 创建决策记录（包含fallback标记）
                        decision_record = Decision(
                            agent_id=agent.id,
                            iteration=self.iteration,
                            action=decision['action'],
                            params=decision.get('params', {}),
                            reasoning=decision.get('reasoning', ''),
                            is_fallback=decision.get('is_fallback', False),
                            fallback_reason=decision.get('fallback_reason', '')
                        )
                        
                        # ✅ 写入临时缓冲区 (不是statuspool!)
                        self.decision_buffer.add_decision(decision_record)
                        
                        # 更新agent的last_decision_time
                        agent.last_decision_time = self.iteration
                        
                        successful_decisions += 1
                    else:
                        # 记录错误（保存完整信息用于诊断）
                        failed_decisions.append({
                            'agent_id': result['agent_id'],
                            'agent_type': result.get('agent_type', 'Person'),
                            'error': result['error'],
                            'error_type': result['error_type'],
                            'full_traceback': result.get('full_traceback', 'No traceback available')
                        })
                
                # 错误处理: 任何失败都立即中止实验（确保数据质量）
                if failed_decisions:
                    print(f"\n{'='*80}")
                    print(f"[SIMULATION ERROR] {len(failed_decisions)} Person LLM Decision(s) Failed")
                    print(f"{'='*80}")
                    for fail in failed_decisions:
                        agent = next(a for a in deciding_persons if a.id == fail['agent_id'])
                        print(f"  Person {fail['agent_id']}: [{fail['error_type']}] {fail['error']}")
                        print(f"    Age: {agent.age}, Status: {agent.status.name}, Wealth: {agent.wealth:.2f}")
                        if fail.get('used_fallback'):
                            print(f"    (Fallback decision was generated but will not be used)")
                    print(f"{'='*80}\n")
                    
                    # 🔧 [ENHANCED] 保存详细的失败报告到文件
                    self._save_decision_failure_report(failed_decisions, deciding_persons)
                    
                    # ❌ 立即中止实验，避免使用fallback决策导致数据失真
                    # 🔧 [ENHANCED] 将详细错误信息附加到异常中，以便记录到diagnostics
                    error = RuntimeError(
                        f"{len(failed_decisions)} Person agent(s) failed to make decisions at iteration {self.iteration}. "
                        f"Aborting iteration to ensure data quality."
                    )
                    # ✅ 将failed_decisions附加为异常属性，供experiments.py记录
                    error.failed_decisions = failed_decisions
                    raise error
                
                # ✅ 所有决策成功,统一提交到statuspool!
                committed_count = self.decision_buffer.flush_to_statuspool()
            
            # ========================================
            # Phase 2: 执行Person的decisions (actions)
            # ========================================
            
            # 执行所有Person agents的action (包括刚决策的和复用历史决策的)
            for agent in filter(lambda x: x.status != Status.Death, self.population):
                if not isinstance(agent, Person):
                    continue
                
                # 获取最新决策 (刚才并发生成的或历史决策)
                latest_decision = self.status_pool.get_latest_decision(agent.id)
                
                if latest_decision is None:
                    # 第一次执行且agent未决策 - 这不应该发生
                    raise RuntimeError(
                        f"[CRITICAL] Person {agent.id} has no decision history! "
                        f"last_decision_time={agent.last_decision_time}, iteration={self.iteration}"
                    )
                
                try:
                    # ✅ 验证action合法性：检查是否在当前可用actions中
                    # 防止LLM"幻觉"出被过滤的action（如购物冷却期内的ShoppingAction）
                    available_actions = self.status_pool.get_available_actions_for_agent(agent)
                    
                    if latest_decision.action not in available_actions:
                        # Action不可用，使用fallback（StayHomeAction）
                        fallback_action = 'StayHomeAction'
                        action = action_registry.get(fallback_action)
                        if action is None:
                            raise ValueError(f"Fallback action not found: {fallback_action}")
                        action.execute(agent, self, {})
                    else:
                        # Action可用，正常执行
                        action = action_registry.get(latest_decision.action)
                        if action is None:
                            raise ValueError(f"Unknown action: {latest_decision.action}")
                        action.execute(agent, self, latest_decision.params)
                    
                except Exception as e:
                    error_msg = (
                        f"[ERROR] Action execution failed for Person {agent.id} "
                        f"at iteration {self.iteration}.\n"
                        f"Action: {latest_decision.action}\n"
                        f"Params: {latest_decision.params}\n"
                        f"Error: {str(e)}"
                    )
                    print(error_msg)
                    raise RuntimeError(error_msg) from e
            
            # ========================================
            # Phase 3: Person疾病进展和消费行为
            # ========================================
            
            # 疾病进展 (每天更新一次)
            if new_dy:
                for agent in filter(lambda x: x.status != Status.Death, self.population):
                    if isinstance(agent, Person):
                        agent.update()
            
            # ✅ 已移除自动消费规则（BasicSimulation残留）
            # 原逻辑：Person靠近Business自动触发消费 → 违背LLM驱动理念
            # 新设计：完全由LLM通过ShoppingAction主动决策购物
            # 理由：
            #   1. 符合"完全LLM驱动"的项目初衷
            #   2. 符合现实：人路过商店不会自动购物
            #   3. Agent有自主决策权
            #   4. ShoppingAction是完整的行为单元（移动+交易）
            
            # ========================================
            # Phase 4: Business Agents - 并发决策
            # ========================================
            
            # 收集需要决策的Business agents
            deciding_businesses = [
                bus for bus in self.business
                if bus != self.government and bus != self.healthcare
                and bus.should_decide(self.iteration)
            ]
            
            if deciding_businesses:
                # 启动新的缓冲区 (Business单独一轮)
                self.decision_buffer.start_iteration(self.iteration)
                
                # 🔥 并发执行所有Business的LLM决策!
                decision_results = self.decision_executor.execute_concurrent_decisions(
                    agents=deciding_businesses,
                    status_pool=self.status_pool,  # ✅ 只读
                    iteration=self.iteration
                )
                
                # 处理决策结果
                from covid_abs.llm.message import Decision
                failed_decisions = []
                
                for result in decision_results:
                    if result['success']:
                        decision = result['decision']
                        bus = next(b for b in deciding_businesses if b.id == result['agent_id'])
                        
                        # 创建决策记录（包含fallback标记）
                        decision_record = Decision(
                            agent_id=bus.id,
                            iteration=self.iteration,
                            action=decision['action'],
                            params=decision.get('params', {}),
                            reasoning=decision.get('reasoning', ''),
                            is_fallback=decision.get('is_fallback', False),
                            fallback_reason=decision.get('fallback_reason', '')
                        )
                        
                        # ✅ 写入临时缓冲区
                        self.decision_buffer.add_decision(decision_record)
                        bus.last_decision_time = self.iteration
                    else:
                        failed_decisions.append({
                            'agent_id': result['agent_id'],
                            'error': result['error'],
                            'error_type': result['error_type']
                        })
                
                # 错误处理
                if failed_decisions:
                    print(f"\n{'='*80}")
                    print(f"[SIMULATION ERROR] {len(failed_decisions)} Business LLM Decision(s) Failed")
                    print(f"{'='*80}")
                    for fail in failed_decisions:
                        bus = next(b for b in deciding_businesses if b.id == fail['agent_id'])
                        print(f"  Business {fail['agent_id']}: [{fail['error_type']}] {fail['error']}")
                        print(f"    Stratum: {bus.social_stratum}, Wealth: {bus.wealth:.2f}, Employees: {len(bus.employees)}")
                    print(f"{'='*80}\n")
                    
                    raise RuntimeError(
                        f"{len(failed_decisions)} Business agent(s) failed at iteration {self.iteration}."
                    )
                
                # ✅ 统一提交
                self.decision_buffer.flush_to_statuspool()
                
                # 执行Business的actions
                for bus in deciding_businesses:
                    latest_decision = self.status_pool.get_latest_decision(bus.id)
                    if latest_decision:
                        # 验证action是否在允许列表中
                        available_actions = self.status_pool.get_available_actions_for_agent(bus)
                        if latest_decision.action not in available_actions:
                            print(f"[WARNING] Business {bus.id} attempted unavailable action '{latest_decision.action}'. Using MaintainOperationAction instead.")
                            # 使用fallback动作
                            action = action_registry.get('MaintainOperationAction')
                            if action:
                                try:
                                    action.execute(bus, self, {})
                                except Exception as e:
                                    print(f"[ERROR] Fallback action failed: {e}")
                        else:
                            action = action_registry.get(latest_decision.action)
                            if action:
                                try:
                                    action.execute(bus, self, latest_decision.params)
                                except Exception as e:
                                    # 🔒 [数据完整性] Business Action执行失败，立即中止实验
                                    error_msg = (
                                        f"[ERROR] Action execution failed for Business {bus.id} "
                                        f"at iteration {self.iteration}.\n"
                                        f"Action: {latest_decision.action}\n"
                                        f"Params: {latest_decision.params}\n"
                                        f"Error: {str(e)}"
                                    )
                                    print(error_msg)
                                    raise RuntimeError(error_msg) from e
            
            # ========================================
            # Phase 5: Government Agent - 决策 (不并发,只有一个)
            # ========================================
            
            if self.government and self.government.should_decide_as_government(self.iteration):
                try:
                    # Government决策 (单个agent,不需要并发)
                    decision = self.government.decide_as_government(self.status_pool)
                    
                    from covid_abs.llm.message import Decision
                    # 创建决策记录（包含fallback标记）
                    decision_record = Decision(
                        agent_id=self.government.id,
                        iteration=self.iteration,
                        action=decision['action'],
                        params=decision.get('params', {}),
                        reasoning=decision.get('reasoning', ''),
                        is_fallback=decision.get('is_fallback', False),
                        fallback_reason=decision.get('fallback_reason', '')
                    )
                    self.status_pool.append_decision(decision_record)
                    self.government.last_gov_decision_time = self.iteration
                    
                    # 执行Government action (检查是否在允许列表中)
                    # 获取政府允许的动作列表
                    allowed_actions = self.status_pool.get_available_actions_for_agent(self.government)
                    
                    # 检查决策的动作是否在允许列表中
                    if decision['action'] in allowed_actions:
                        action = action_registry.get(decision['action'])
                        if action:
                            action.execute(self.government, self, decision.get('params', {}))
                    else:
                        # 动作被场景配置禁止，记录警告但不执行
                        print(f"[WARNING] Government attempted forbidden action '{decision['action']}' in scenario '{self.scenario_config.get('name', 'unknown')}'. Action blocked.")
                        
                except Exception as e:
                    error_msg = (
                        f"\n{'='*80}\n"
                        f"[CRITICAL ERROR] Government LLM Decision Failed\n"
                        f"{'='*80}\n"
                        f"  Iteration: {self.iteration} (Day {self.iteration//24})\n"
                        f"  Error: {str(e)}\n"
                        f"{'='*80}\n"
                    )
                    print(error_msg)
                    raise RuntimeError(error_msg) from e

        for bus in filter(lambda b: b.open, self.business):
            if new_dy:
                bus.update()

            if self.iteration > 1 and new_mth:
                bus.accounting()

        for house in filter(lambda h: h.size > 0, self.houses):
            if new_dy:
                house.update()

            if self.iteration > 1 and new_mth:
                house.accounting()

        if new_dy:
            self.government.update()
            self.healthcare.update()

        if self.iteration > 1 and new_mth:
            # Log wealth snapshot before Government accounting
            self._log_wealth_snapshot("Before Government accounting")
            
            self.government.accounting()
            
            # Log wealth snapshot after Government accounting
            self._log_wealth_snapshot("After Government accounting")

        contacts = []

        for i in np.arange(0, self.population_size):
            for j in np.arange(i + 1, self.population_size):
                ai = self.population[i]
                aj = self.population[j]
                if ai.status == Status.Death or aj.status == Status.Death:
                    continue

                if distance(ai, aj) <= self.contagion_distance:
                    contacts.append((i, j))

        for pair in contacts:
            ai = self.population[pair[0]]
            aj = self.population[pair[1]]
            self.contact(ai, aj)
            self.contact(aj, ai)

        self.statistics = None

        self.callback('post_execute', self)

    def contact(self, agent1, agent2):
        """
        Performs the actions needed when two agents get in touch.

        :param agent1: an instance of agents.Agent
        :param agent2: an instance of agents.Agent
        """

        if self.callback('on_contact', agent1, agent2):
            return

        if agent1.status == Status.Susceptible and agent2.status == Status.Infected:
            low = np.random.randint(-1, 1)
            up = np.random.randint(-1, 1)
            if agent2.infected_time >= self.incubation_time + low \
                    and agent2.infected_time <= self.contagion_time + up:
                contagion_test = np.random.random()
                #agent1.infection_status = InfectionSeverity.Exposed
                if contagion_test <= self.contagion_rate:
                    agent1.status = Status.Infected
                    agent1.infection_status = InfectionSeverity.Asymptomatic

        self.callback('post_contact', agent1, agent2)

    def get_statistics(self, kind='all'):
        """
        ✅ 优化：统一使用百分比计算（人数占比 或 财富占比）
        确保所有数据归一化的严谨性和一致性
        """
        if self.statistics is None:
            self.statistics = {}
            
            # ===== 经济数据统计（财富占比，百分比） =====
            # ✅ 确保total_wealth > 0，避免除零错误
            safe_total_wealth = max(abs(self.total_wealth), 1.0)  # 使用绝对值，至少为1
            
            for quintile in [0, 1, 2, 3, 4]:
                quintile_wealth = np.sum(
                    h.wealth for h in self.houses if h.social_stratum == quintile
                )
                # ✅ 统一归一化：财富占比（可以为负，表示负债）
                self.statistics['Q{}'.format(quintile + 1)] = quintile_wealth / safe_total_wealth
            
            business_wealth = np.sum([b.wealth for b in self.business])
            self.statistics['Business'] = business_wealth / safe_total_wealth
            self.statistics['Government'] = self.government.wealth / safe_total_wealth

            # ===== 疫情数据统计（人数占比，百分比） =====
            # ✅ 确保population_size > 0
            safe_population_size = max(self.population_size, 1)
            
            for status in Status:
                count = np.sum([1 for a in self.population if a.status == status])
                # ✅ 统一归一化：人数占比百分比
                self.statistics[status.name] = count / safe_population_size

            for infected_status in filter(lambda x: x != InfectionSeverity.Exposed, InfectionSeverity):
                count = np.sum([1 for a in self.population if
                               a.infected_status == infected_status and
                               a.status != Status.Death])
                # ✅ 统一归一化：人数占比百分比
                self.statistics[infected_status.name] = count / safe_population_size

        return self.filter_stats(kind)
    
    def get_llm_logs(self):
        """
        获取所有LLM决策日志
        从GraphStatusPool中提取决策记录并转换为标准格式
        
        Returns:
            list: LLM决策日志列表
        """
        if not self.enable_llm_decision or self.status_pool is None:
            return []
        
        # 从status_pool获取所有决策
        all_decisions = self.status_pool.get_all_decisions()
        
        # 创建agent_id到agent_type的映射
        agent_type_map = {}
        for person in self.population:
            agent_type_map[person.id] = 'Person'
        for business in self.business:
            agent_type_map[business.id] = 'Business'
        if self.government:
            agent_type_map[self.government.id] = 'Government'
        
        # 转换为标准格式
        # 时间系统: 每个iteration = 1小时
        logs = []
        for decision in all_decisions:
            agent_type = agent_type_map.get(decision.agent_id, 'Unknown')
            log_entry = {
                'iteration': decision.iteration,
                'day': decision.iteration // 24,  # 每天24小时
                'hour': decision.iteration % 24,  # 当前小时
                'agent_id': str(decision.agent_id),
                'agent_type': agent_type,
                'action': decision.action,
                'reasoning': decision.reasoning,
                'parameters': decision.params,  # 使用params而不是parameters
                'timestamp': getattr(decision, 'timestamp', None)
            }
            logs.append(log_entry)
        
        return logs
    
    def save_llm_logs(self, filename):
        """
        保存所有LLM决策日志到JSON文件
        
        Args:
            filename: 输出文件路径 (例如: "output/graph_llm_decisions.json")
        
        Returns:
            str: 保存的文件路径
        """
        import json
        import os
        from datetime import datetime
        
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        logs = self.get_llm_logs()
        
        # 统计信息
        agent_type_counts = {}
        action_counts = {}
        for log in logs:
            agent_type = log['agent_type']
            action = log['action']
            agent_type_counts[agent_type] = agent_type_counts.get(agent_type, 0) + 1
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # 获取最终统计
        final_stats = self.get_statistics(kind='info')
        
        output = {
            'metadata': {
                'simulation_type': 'GraphSimulation',
                'timestamp': datetime.now().isoformat(),
                'total_iterations': self.iteration,
                'total_days': self.iteration // 24,
                'population_size': self.population_size,
                'total_businesses': len(self.business),
                'total_houses': len(self.houses),
                'llm_enabled': self.enable_llm_decision,
                'llm_model': self.backend.model_name if self.backend else None,
                'decision_interval': self.llm_decision_interval,
                'total_decisions': len(logs)
            },
            'statistics': {
                'decisions_by_agent_type': agent_type_counts,
                'decisions_by_action': action_counts,
                'final_state': {
                    'susceptible': final_stats.get('Susceptible', 0),
                    'infected': final_stats.get('Infected', 0),
                    'recovered': final_stats.get('Recovered_Immune', 0),
                    'deaths': final_stats.get('Death', 0)
                }
            },
            'decisions': logs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def _save_decision_failure_report(self, failed_decisions, deciding_agents):
        """
        保存详细的决策失败报告到文件
        
        Args:
            failed_decisions: 失败的决策列表
            deciding_agents: 正在决策的agent列表
        """
        import json
        from datetime import datetime
        
        filename = f'decision_failure_iter{self.iteration}_day{self.iteration//24}_hour{self.iteration%24}.json'
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'iteration': self.iteration,
            'day': self.iteration // 24,
            'hour': self.iteration % 24,
            'total_agents_deciding': len(deciding_agents),
            'failed_count': len(failed_decisions),
            'success_rate': 1 - (len(failed_decisions) / len(deciding_agents)) if deciding_agents else 0,
            'failed_decisions': [],
            'simulation_state': {
                'total_population': len(self.population),
                'total_businesses': len(self.business),
                'susceptible': sum(1 for a in self.population if a.status == Status.Susceptible),
                'infected': sum(1 for a in self.population if a.status == Status.Infected),
                'deaths': sum(1 for a in self.population if a.status == Status.Death),
            },
            'deciding_agents_sample': []
        }
        
        # 添加失败决策的详细信息
        for fail in failed_decisions:
            agent = next((a for a in deciding_agents if a.id == fail['agent_id']), None)
            if agent:
                fail_detail = {
                    'agent_id': fail['agent_id'],
                    'agent_type': fail['agent_type'],
                    'error_type': fail['error_type'],
                    'error_message': fail['error'],
                    'full_traceback': fail.get('full_traceback', 'No traceback'),
                    'agent_state': {
                        'age': agent.age if hasattr(agent, 'age') else None,
                        'status': agent.status.name if hasattr(agent, 'status') else 'Unknown',
                        'wealth': agent.wealth if hasattr(agent, 'wealth') else None,
                        'employer': agent.employer.id if hasattr(agent, 'employer') and agent.employer else None,
                        'house': agent.house.id if hasattr(agent, 'house') and agent.house else None,
                        'infection_status': agent.infected_status.name if hasattr(agent, 'infected_status') else None,
                    }
                }
                report['failed_decisions'].append(fail_detail)
        
        # 添加正在决策的agent样本（前20个）
        for agent in deciding_agents[:20]:
            report['deciding_agents_sample'].append({
                'agent_id': agent.id,
                'age': agent.age if hasattr(agent, 'age') else None,
                'status': agent.status.name if hasattr(agent, 'status') else 'Unknown',
                'wealth': agent.wealth if hasattr(agent, 'wealth') else None,
            })
        
        # 保存到文件
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"📁 Decision failure report saved to: {filename}")
        except Exception as e:
            print(f"⚠️  Failed to save decision failure report: {e}")

